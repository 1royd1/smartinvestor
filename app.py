import streamlit as st
import pandas as pd
import numpy as np
import requests
import json
import time
from datetime import datetime, timedelta
import sqlite3
import hashlib
import base64
import feedparser
import re
import io
from fpdf import FPDF

# 페이지 설정
st.set_page_config(
    page_title="SmartInvestor Pro",
    page_icon="📈",
    layout="wide",
    initial_sidebar_state="expanded"
)

# CSS 스타일 (완전 복원)
st.markdown("""
<style>
    .main-header {
        font-size: 3rem;
        font-weight: bold;
        text-align: center;
        background: linear-gradient(90deg, #667eea 0%, #764ba2 100%);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        margin-bottom: 2rem;
        padding: 1rem 0;
    }
    .metric-card {
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        padding: 1.5rem;
        border-radius: 15px;
        color: white;
        margin: 1rem 0;
        box-shadow: 0 4px 15px rgba(0,0,0,0.1);
    }
    .buy-signal {
        background: linear-gradient(135deg, #11998e 0%, #38ef7d 100%);
        padding: 1.5rem;
        border-radius: 15px;
        color: white;
        text-align: center;
        margin: 1rem 0;
        box-shadow: 0 8px 25px rgba(17, 153, 142, 0.3);
        animation: glow 2s ease-in-out infinite alternate;
    }
    .warning-signal {
        background: linear-gradient(135deg, #ff9a9e 0%, #fecfef 100%);
        padding: 1.5rem;
        border-radius: 15px;
        color: #333;
        text-align: center;
        margin: 1rem 0;
        box-shadow: 0 4px 15px rgba(255, 154, 158, 0.3);
    }
    .neutral-signal {
        background: linear-gradient(135deg, #a8edea 0%, #fed6e3 100%);
        padding: 1.5rem;
        border-radius: 15px;
        color: #333;
        text-align: center;
        margin: 1rem 0;
        box-shadow: 0 4px 15px rgba(168, 237, 234, 0.3);
    }
    .strong-buy {
        background: linear-gradient(135deg, #fa709a 0%, #fee140 100%);
        padding: 2rem;
        border-radius: 20px;
        color: #333;
        text-align: center;
        margin: 1rem 0;
        font-size: 1.2rem;
        font-weight: bold;
        box-shadow: 0 10px 30px rgba(250, 112, 154, 0.4);
        animation: pulse 2s ease-in-out infinite;
    }
    .sidebar-section {
        background: linear-gradient(135deg, #f093fb 0%, #f5576c 100%);
        padding: 1rem;
        border-radius: 10px;
        margin: 1rem 0;
        color: white;
    }
    .market-heatmap {
        background: linear-gradient(135deg, #4facfe 0%, #00f2fe 100%);
        padding: 1rem;
        border-radius: 10px;
        color: white;
        text-align: center;
        margin: 1rem 0;
    }
    .news-item {
        background: #f8f9fa;
        border-left: 4px solid #667eea;
        padding: 1rem;
        margin: 1rem 0;
        border-radius: 5px;
    }
    @keyframes glow {
        from { box-shadow: 0 8px 25px rgba(17, 153, 142, 0.3); }
        to { box-shadow: 0 8px 35px rgba(17, 153, 142, 0.6); }
    }
    @keyframes pulse {
        0% { transform: scale(1); }
        50% { transform: scale(1.05); }
        100% { transform: scale(1); }
    }
    .stButton > button {
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        color: white;
        border: none;
        border-radius: 10px;
        padding: 0.5rem 1rem;
        font-weight: bold;
        transition: all 0.3s ease;
    }
    .stButton > button:hover {
        transform: translateY(-2px);
        box-shadow: 0 4px 15px rgba(102, 126, 234, 0.3);
    }
</style>
""", unsafe_allow_html=True)

# 세션 상태 초기화
if 'analysis_results' not in st.session_state:
    st.session_state.analysis_results = []
if 'user_authenticated' not in st.session_state:
    st.session_state.user_authenticated = False
if 'current_user' not in st.session_state:
    st.session_state.current_user = None

# 데이터베이스 초기화 (간단한 버전)
def init_database():
    try:
        conn = sqlite3.connect('smartinvestor.db')
        c = conn.cursor()
        
        # 사용자 테이블
        c.execute('''
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                email TEXT UNIQUE NOT NULL,
                password_hash TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                is_admin BOOLEAN DEFAULT FALSE
            )
        ''')
        
        # 분석 히스토리 테이블
        c.execute('''
            CREATE TABLE IF NOT EXISTS analysis_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                symbol TEXT,
                score INTEGER,
                analysis_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users (id)
            )
        ''')
        
        # 관리자 계정 생성
        admin_email = "admin@smartinvestor.com"
        admin_password = hashlib.sha256("admin123".encode()).hexdigest()
        
        try:
            c.execute("INSERT INTO users (email, password_hash, is_admin) VALUES (?, ?, ?)",
                     (admin_email, admin_password, True))
        except sqlite3.IntegrityError:
            pass
        
        conn.commit()
        conn.close()
        return True
    except Exception as e:
        st.error(f"데이터베이스 초기화 오류: {e}")
        return False

# Alpha Vantage API 클래스 (완전 복원)
class AlphaVantageAPI:
    def __init__(self, api_key):
        self.api_key = api_key
        self.base_url = "https://www.alphavantage.co/query"
        
    def get_stock_data(self, symbol, period="3month"):
        """주식 데이터 가져오기"""
        try:
            params = {
                'function': 'TIME_SERIES_DAILY',
                'symbol': symbol,
                'outputsize': 'compact',
                'apikey': self.api_key
            }
            
            response = requests.get(self.base_url, params=params, timeout=15)
            data = response.json()
            
            if 'Error Message' in data:
                st.error(f"❌ 잘못된 심볼: {symbol}")
                return None
                
            if 'Note' in data:
                st.warning("⚠️ API 호출 제한에 도달했습니다.")
                return None
                
            time_series = data.get('Time Series (Daily)', {})
            if not time_series:
                return None
                
            # DataFrame 변환
            df_data = []
            for date_str, values in time_series.items():
                try:
                    df_data.append({
                        'Date': pd.to_datetime(date_str),
                        'Open': float(values['1. open']),
                        'High': float(values['2. high']),
                        'Low': float(values['3. low']),
                        'Close': float(values['4. close']),
                        'Volume': int(values['5. volume'])
                    })
                except (ValueError, KeyError):
                    continue
            
            if not df_data:
                return None
                
            df = pd.DataFrame(df_data)
            df.set_index('Date', inplace=True)
            df.sort_index(inplace=True)
            
            return df
            
        except Exception as e:
            st.error(f"데이터 가져오기 실패 ({symbol}): {str(e)}")
            return None
    
    def get_real_time_quote(self, symbol):
        """실시간 시세"""
        try:
            params = {
                'function': 'GLOBAL_QUOTE',
                'symbol': symbol,
                'apikey': self.api_key
            }
            
            response = requests.get(self.base_url, params=params, timeout=15)
            data = response.json()
            
            quote = data.get('Global Quote', {})
            if not quote:
                return None
                
            return {
                'symbol': quote.get('01. symbol', symbol),
                'price': float(quote.get('05. price', 0)),
                'change': float(quote.get('09. change', 0)),
                'change_percent': quote.get('10. change percent', '0%').replace('%', ''),
                'volume': int(quote.get('06. volume', 0))
            }
            
        except Exception:
            return None

    def get_company_overview(self, symbol):
        """회사 개요 정보"""
        try:
            params = {
                'function': 'OVERVIEW',
                'symbol': symbol,
                'apikey': self.api_key
            }
            
            response = requests.get(self.base_url, params=params, timeout=15)
            data = response.json()
            
            if 'Symbol' in data:
                return {
                    'name': data.get('Name', symbol),
                    'sector': data.get('Sector', 'N/A'),
                    'industry': data.get('Industry', 'N/A'),
                    'market_cap': data.get('MarketCapitalization', 'N/A'),
                    'pe_ratio': data.get('PERatio', 'N/A'),
                    'description': data.get('Description', 'N/A')[:200] + '...' if data.get('Description') else 'N/A'
                }
            return None
        except:
            return None

# 기술적 지표 계산 (완전 복원)
def calculate_rsi(data, period=14):
    """RSI 계산"""
    if len(data) < period + 1:
        return pd.Series([50] * len(data), index=data.index)
    
    try:
        delta = data['Close'].diff()
        gain = delta.where(delta > 0, 0)
        loss = -delta.where(delta < 0, 0)
        
        avg_gain = gain.rolling(window=period).mean()
        avg_loss = loss.rolling(window=period).mean()
        
        rs = avg_gain / avg_loss
        rsi = 100 - (100 / (1 + rs))
        return rsi.fillna(50)
    except:
        return pd.Series([50] * len(data), index=data.index)

def calculate_macd(data, fast=12, slow=26, signal=9):
    """MACD 계산"""
    if len(data) < slow:
        return {
            'macd': pd.Series([0] * len(data), index=data.index),
            'signal': pd.Series([0] * len(data), index=data.index),
            'histogram': pd.Series([0] * len(data), index=data.index)
        }
    
    try:
        exp1 = data['Close'].ewm(span=fast).mean()
        exp2 = data['Close'].ewm(span=slow).mean()
        macd_line = exp1 - exp2
        signal_line = macd_line.ewm(span=signal).mean()
        histogram = macd_line - signal_line
        
        return {
            'macd': macd_line.fillna(0),
            'signal': signal_line.fillna(0),
            'histogram': histogram.fillna(0)
        }
    except:
        return {
            'macd': pd.Series([0] * len(data), index=data.index),
            'signal': pd.Series([0] * len(data), index=data.index),
            'histogram': pd.Series([0] * len(data), index=data.index)
        }

def calculate_cci(data, period=20):
    """CCI 계산"""
    if len(data) < period:
        return pd.Series([0] * len(data), index=data.index)
    
    try:
        tp = (data['High'] + data['Low'] + data['Close']) / 3
        sma = tp.rolling(window=period).mean()
        mad = tp.rolling(window=period).apply(lambda x: abs(x - x.mean()).mean())
        cci = (tp - sma) / (0.015 * mad)
        return cci.fillna(0)
    except:
        return pd.Series([0] * len(data), index=data.index)

def calculate_mfi(data, period=14):
    """MFI 계산"""
    if len(data) < period + 1:
        return pd.Series([50] * len(data), index=data.index)
    
    try:
        typical_price = (data['High'] + data['Low'] + data['Close']) / 3
        money_flow = typical_price * data['Volume']
        
        positive_flow = []
        negative_flow = []
        
        for i in range(1, len(data)):
            if typical_price.iloc[i] > typical_price.iloc[i-1]:
                positive_flow.append(money_flow.iloc[i])
                negative_flow.append(0)
            elif typical_price.iloc[i] < typical_price.iloc[i-1]:
                positive_flow.append(0)
                negative_flow.append(money_flow.iloc[i])
            else:
                positive_flow.append(0)
                negative_flow.append(0)
        
        positive_flow = [0] + positive_flow
        negative_flow = [0] + negative_flow
        
        positive_mf = pd.Series(positive_flow, index=data.index).rolling(window=period).sum()
        negative_mf = pd.Series(negative_flow, index=data.index).rolling(window=period).sum()
        
        mfi = 100 - (100 / (1 + (positive_mf / negative_mf.replace(0, 1))))
        return mfi.fillna(50)
    except:
        return pd.Series([50] * len(data), index=data.index)

def calculate_stoch_rsi(data, period=14):
    """Stochastic RSI 계산"""
    if len(data) < period:
        return pd.Series([0.5] * len(data), index=data.index)
    
    try:
        rsi = calculate_rsi(data, period)
        stoch_rsi = (rsi - rsi.rolling(window=period).min()) / (rsi.rolling(window=period).max() - rsi.rolling(window=period).min())
        return stoch_rsi.fillna(0.5)
    except:
        return pd.Series([0.5] * len(data), index=data.index)

def calculate_bollinger_bands(data, period=20, std_dev=2):
    """볼린저 밴드 계산"""
    if len(data) < period:
        return None
    
    try:
        middle_band = data['Close'].rolling(window=period).mean()
        std = data['Close'].rolling(window=period).std()
        upper_band = middle_band + (std * std_dev)
        lower_band = middle_band - (std * std_dev)
        
        return {
            'upper': upper_band,
            'middle': middle_band,
            'lower': lower_band
        }
    except:
        return None

# 고급 매수 신호 분석 (5개 지표 모두 포함)
def analyze_buy_signals(data):
    """5가지 기술적 지표 종합 분석"""
    if data is None or len(data) < 30:
        return {
            'score': 0,
            'signals': {},
            'indicators': {},
            'recommendation': 'Insufficient Data',
            'confidence': 0
        }
    
    try:
        # 모든 기술적 지표 계산
        rsi = calculate_rsi(data)
        macd_data = calculate_macd(data)
        cci = calculate_cci(data)
        mfi = calculate_mfi(data)
        stoch_rsi = calculate_stoch_rsi(data)
        
        # 최신 값들
        latest_rsi = rsi.iloc[-1]
        latest_macd = macd_data['macd'].iloc[-1]
        latest_signal = macd_data['signal'].iloc[-1]
        latest_cci = cci.iloc[-1]
        latest_mfi = mfi.iloc[-1]
        latest_stoch_rsi = stoch_rsi.iloc[-1]
        
        # 5가지 매수 신호 판단 (원래 조건)
        signals = {
            'rsi_oversold': latest_rsi < 30,
            'macd_golden_cross': latest_macd > latest_signal,
            'cci_oversold': latest_cci < -100,
            'mfi_oversold': latest_mfi < 20,
            'stoch_rsi_oversold': latest_stoch_rsi < 0.2
        }
        
        # 점수 계산 (5점 만점)
        score = sum(signals.values())
        
        # 신뢰도 계산
        confidence = (score / 5.0) * 100
        
        # 추천 등급
        if score >= 4:
            recommendation = "Strong Buy"
        elif score >= 3:
            recommendation = "Buy"
        elif score >= 2:
            recommendation = "Hold"
        else:
            recommendation = "Wait"
        
        return {
            'score': score,
            'signals': signals,
            'indicators': {
                'rsi': round(latest_rsi, 2),
                'macd': round(latest_macd, 4),
                'macd_signal': round(latest_signal, 4),
                'cci': round(latest_cci, 2),
                'mfi': round(latest_mfi, 2),
                'stoch_rsi': round(latest_stoch_rsi, 3)
            },
            'recommendation': recommendation,
            'confidence': round(confidence, 1)
        }
        
    except Exception as e:
        return {
            'score': 0,
            'signals': {},
            'indicators': {},
            'recommendation': 'Analysis Error',
            'confidence': 0
        }

# 메인 분석 함수
def get_stock_analysis(symbols, api_key):
    """주식 분석 실행"""
    av_api = AlphaVantageAPI(api_key)
    results = []
    
    progress_bar = st.progress(0)
    status_text = st.empty()
    
    for i, symbol in enumerate(symbols):
        status_text.text(f'📊 분석 중: {symbol} ({i+1}/{len(symbols)}) - 예상 대기시간: {(len(symbols) - i - 1) * 12}초')
        
        # 데이터 가져오기
        data = av_api.get_stock_data(symbol)
        quote = av_api.get_real_time_quote(symbol)
        overview = av_api.get_company_overview(symbol)
        
        if data is not None and len(data) > 0:
            # 5개 지표 종합 분석
            analysis = analyze_buy_signals(data)
            
            current_price = quote['price'] if quote else data['Close'].iloc[-1]
            change_percent = quote['change_percent'] if quote else '0'
            
            result = {
                'symbol': symbol,
                'company_name': overview['name'] if overview else symbol,
                'sector': overview['sector'] if overview else 'N/A',
                'current_price': current_price,
                'change_percent': change_percent,
                'score': analysis['score'],
                'signals': analysis['signals'],
                'indicators': analysis['indicators'],
                'recommendation': analysis['recommendation'],
                'confidence': analysis['confidence'],
                'volume': quote['volume'] if quote else data['Volume'].iloc[-1],
                'analysis_time': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            }
            
            results.append(result)
        
        # API 호출 제한 (분당 5회)
        if i < len(symbols) - 1:
            time.sleep(12)
        
        progress_bar.progress((i + 1) / len(symbols))
    
    progress_bar.empty()
    status_text.empty()
    
    # 세션에 결과 저장
    st.session_state.analysis_results = results
    
    return results

# 차트 생성 함수 (Plotly 없이도 작동)
def create_simple_chart(data, symbol):
    """간단한 차트 생성"""
    if data is None or len(data) == 0:
        return None
    
    try:
        # Streamlit 내장 차트 사용
        chart_data = data[['Open', 'High', 'Low', 'Close']].tail(30)
        return chart_data
    except:
        return None

# 뉴스 가져오기
def get_investment_news():
    """투자 뉴스 가져오기"""
    try:
        # 여러 RSS 피드에서 뉴스 수집
        feeds = [
            "https://feeds.finance.yahoo.com/rss/2.0/headline",
            "https://www.investing.com/rss/news.rss",
            "https://www.marketwatch.com/rss/topstories"
        ]
        
        all_news = []
        
        for feed_url in feeds:
            try:
                feed = feedparser.parse(feed_url)
                for entry in feed.entries[:5]:  # 각 피드에서 5개씩
                    all_news.append({
                        'title': entry.title,
                        'link': entry.link,
                        'published': entry.published if hasattr(entry, 'published') else 'Recent',
                        'summary': entry.get('summary', entry.get('description', ''))[:150] + '...',
                        'source': feed_url.split('/')[2]
                    })
            except:
                continue
        
        return all_news[:15]  # 최대 15개 뉴스
    except:
        return []

# AI 뉴스 요약 (OpenAI API)
def summarize_news_with_ai(news_items):
    """AI로 뉴스 요약"""
    try:
        openai_key = st.secrets.get("OPENAI_API_KEY", "")
        if not openai_key:
            return None
        
        # OpenAI API 호출 (간단한 버전)
        headers = {"Authorization": f"Bearer {openai_key}"}
        
        news_text = "\n".join([f"- {news['title']}" for news in news_items[:5]])
        
        data = {
            "model": "gpt-3.5-turbo",
            "messages": [
                {"role": "system", "content": "투자 뉴스를 3줄로 요약해주세요."},
                {"role": "user", "content": news_text}
            ],
            "max_tokens": 150
        }
        
        response = requests.post("https://api.openai.com/v1/chat/completions", 
                               headers=headers, json=data, timeout=10)
        
        if response.status_code == 200:
            return response.json()['choices'][0]['message']['content']
        
    except:
        pass
    
    return None

# PDF 리포트 생성
def generate_pdf_report(analysis_results):
    """PDF 투자 리포트 생성"""
    try:
        pdf = FPDF()
        pdf.add_page()
        pdf.set_font('Arial', 'B', 20)
        
        # 제목
        pdf.cell(0, 15, 'SmartInvestor Pro - Investment Analysis Report', 0, 1, 'C')
        pdf.ln(10)
        
        # 생성 정보
        pdf.set_font('Arial', '', 12)
        pdf.cell(0, 8, f'Generated: {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}', 0, 1)
        pdf.cell(0, 8, f'Total Analyzed Stocks: {len(analysis_results)}', 0, 1)
        pdf.ln(10)
        
        # 요약
        pdf.set_font('Arial', 'B', 14)
        pdf.cell(0, 10, 'Executive Summary:', 0, 1)
        pdf.set_font('Arial', '', 10)
        
        strong_buys = [r for r in analysis_results if r['score'] >= 4]
        buys = [r for r in analysis_results if r['score'] == 3]
        
        pdf.cell(0, 6, f'Strong Buy Signals: {len(strong_buys)} stocks', 0, 1)
        pdf.cell(0, 6, f'Buy Signals: {len(buys)} stocks', 0, 1)
        pdf.ln(5)
        
        # 상세 분석
        pdf.set_font('Arial', 'B', 14)
        pdf.cell(0, 10, 'Detailed Analysis:', 0, 1)
        pdf.ln(5)
        
        for result in sorted(analysis_results, key=lambda x: x['score'], reverse=True):
            pdf.set_font('Arial', 'B', 12)
            pdf.cell(0, 8, f"{result['symbol']} - Score: {result['score']}/5", 0, 1)
            
            pdf.set_font('Arial', '', 9)
            pdf.cell(0, 6, f"Company: {result.get('company_name', result['symbol'])}", 0, 1)
            pdf.cell(0, 6, f"Current Price: ${result['current_price']:.2f} ({result['change_percent']}%)", 0, 1)
            pdf.cell(0, 6, f"Recommendation: {result['recommendation']} (Confidence: {result['confidence']}%)", 0, 1)
            
            # 기술적 지표
            indicators = result['indicators']
            pdf.cell(0, 6, f"RSI: {indicators['rsi']} | MACD: {indicators['macd']} | CCI: {indicators['cci']}", 0, 1)
            pdf.cell(0, 6, f"MFI: {indicators['mfi']} | Stoch RSI: {indicators['stoch_rsi']}", 0, 1)
            
            # 신호 상태
            signals = result['signals']
            active_signals = [k for k, v in signals.items() if v]
            pdf.cell(0, 6, f"Active Signals: {', '.join(active_signals) if active_signals else 'None'}", 0, 1)
            pdf.ln(3)
        
        # 면책사항
        pdf.ln(10)
        pdf.set_font('Arial', 'B', 12)
        pdf.cell(0, 8, 'Disclaimer:', 0, 1)
        pdf.set_font('Arial', '', 8)
        pdf.multi_cell(0, 5, 'This report is for informational purposes only and should not be considered as financial advice. Past performance does not guarantee future results. Always consult with a qualified financial advisor before making investment decisions.')
        
        return pdf.output(dest='S').encode('latin1')
        
    except Exception as e:
        st.error(f"PDF 생성 오류: {e}")
        return None

# 시장 히트맵 URL 생성
def get_market_heatmap_url():
    """Finviz 히트맵 URL"""
    return "https://finviz.com/map.ashx?t=sec_all"

# 인증 함수들
def authenticate_user(email, password):
    """사용자 인증"""
    try:
        conn = sqlite3.connect('smartinvestor.db')
        c = conn.cursor()
        
        password_hash = hashlib.sha256(password.encode()).hexdigest()
        c.execute("SELECT * FROM users WHERE email = ? AND password_hash = ?", (email, password_hash))
        user = c.fetchone()
        
        conn.close()
        return user
    except:
        return None

def register_user(email, password):
    """사용자 등록"""
    try:
        conn = sqlite3.connect('smartinvestor.db')
        c = conn.cursor()
        
        password_hash = hashlib.sha256(password.encode()).hexdigest()
        c.execute("INSERT INTO users (email, password_hash) VALUES (?, ?)", (email, password_hash))
        
        conn.commit()
        conn.close()
        return True
    except:
        return False

# 메인 애플리케이션
def main():
    # 데이터베이스 초기화
    init_database()
    
    # 사이드바 설정
    with st.sidebar:
        st.markdown('<div class="sidebar-section"><h2>🚀 SmartInvestor Pro</h2></div>', unsafe_allow_html=True)
        
        # API 키 상태 확인
        api_key = st.secrets.get("ALPHA_VANTAGE_API_KEY", "")
        if api_key:
            st.success("✅ API 연결됨")
        else:
            st.error("❌ API 키 필요")
            api_key = st.text_input("API 키 입력:", type="password")
        
        # 현재 시간
        st.markdown(f"**🕒 현재 시간**  \n{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        
        # 시장 상태 (간단한 표시)
        st.markdown("**📊 시장 상태**")
        col1, col2 = st.columns(2)
        with col1:
            st.metric("S&P 500", "5,800", "0.5%")
        with col2:
            st.metric("NASDAQ", "18,500", "0.8%")
        
        # 시장 히트맵 링크
        st.markdown('<div class="market-heatmap">📈 <a href="https://finviz.com/map.ashx?t=sec_all" target="_blank" style="color: white;">시장 히트맵 보기</a></div>', unsafe_allow_html=True)
        
        # 로그인/등록 섹션
        st.markdown("---")
        auth_option = st.selectbox("인증", ["로그인", "회원가입", "게스트"])
        
        if auth_option == "로그인":
            email = st.text_input("이메일")
            password = st.text_input("비밀번호", type="password")
            if st.button("로그인"):
                user = authenticate_user(email, password)
                if user:
                    st.session_state.user_authenticated = True
                    st.session_state.current_user = user
                    st.success("로그인 성공!")
                    st.rerun()
                else:
                    st.error("로그인 실패")
        
        elif auth_option == "회원가입":
            email = st.text_input("이메일")
            password = st.text_input("비밀번호", type="password")
            confirm_password = st.text_input("비밀번호 확인", type="password")
            if st.button("회원가입"):
                if password == confirm_password:
                    if register_user(email, password):
                        st.success("회원가입 성공!")
                    else:
                        st.error("회원가입 실패")
                else:
                    st.error("비밀번호가 일치하지 않습니다")
    
    # 메인 페이지 네비게이션
    page = st.selectbox(
        "페이지 선택",
        ["🏠 홈", "📈 실시간 분석", "📊 개별 종목 분석", "📰 투자 뉴스", "📋 리포트", "⚙️ 시스템 진단", "📚 투자 가이드"]
    )
    
    # 홈 페이지
    if page == "🏠 홈":
        st.markdown('<div class="main-header">🚀 SmartInvestor Pro</div>', unsafe_allow_html=True)
        st.markdown("### AI와 기술적 분석을 활용한 스마트 투자 분석 도구")
        
        # 주요 기능 소개
        col1, col2, col3 = st.columns(3)
        
        with col1:
            st.markdown("""
            <div class="metric-card">
                <h3>📈 5가지 기술적 지표</h3>
                <ul>
                    <li>RSI (상대강도지수)</li>
                    <li>MACD (이동평균수렴확산)</li>
                    <li>CCI (상품채널지수)</li>
                    <li>MFI (자금흐름지수)</li>
                    <li>Stochastic RSI</li>
                </ul>
            </div>
            """, unsafe_allow_html=True)
        
        with col2:
            st.markdown("""
            <div class="metric-card">
                <h3>🎯 점수 기반 시스템</h3>
                <ul>
                    <li>5점 만점 매수 신호</li>
                    <li>실시간 데이터 분석</li>
                    <li>신뢰도 백분율 표시</li>
                    <li>과매도 구간 탐지</li>
                </ul>
            </div>
            """, unsafe_allow_html=True)
        
        with col3:
            st.markdown("""
            <div class="metric-card">
                <h3>🛠️ 고급 기능</h3>
                <ul>
                    <li>AI 뉴스 요약</li>
                    <li>PDF 리포트 생성</li>
                    <li>시장 히트맵 연동</li>
                    <li>개인화된 분석</li>
                </ul>
            </div>
            """, unsafe_allow_html=True)
        
        # 빠른 분석
        st.markdown("---")
        st.subheader("⚡ 빠른 분석")
        
        quick_symbols = st.multiselect(
            "관심 종목 선택:",
            ["AAPL", "MSFT", "GOOGL", "TSLA", "AMZN", "NVDA", "META"],
            default=["AAPL", "MSFT"]
        )
        
        if st.button("🚀 빠른 분석 시작", type="primary") and api_key:
            if quick_symbols:
                with st.spinner("분석 중..."):
                    results = get_stock_analysis(quick_symbols, api_key)
                
                if results:
                    for result in sorted(results, key=lambda x: x['score'], reverse=True):
                        score = result['score']
                        if score >= 4:
                            st.markdown(f'<div class="strong-buy">🚀 {result["symbol"]} - 강력 매수 신호! ({score}/5점)</div>', unsafe_allow_html=True)
                        elif score >= 3:
                            st.markdown(f'<div class="buy-signal">📈 {result["symbol"]} - 매수 신호 ({score}/5점)</div>', unsafe_allow_html=True)
                        else:
                            st.markdown(f'<div class="neutral-signal">📊 {result["symbol"]} - 관망 ({score}/5점)</div>', unsafe_allow_html=True)
    
    # 실시간 분석 페이지
    elif page == "📈 실시간 분석":
        st.title("📈 실시간 주식 분석")
        st.markdown("### 5가지 기술적 지표 종합 분석")
        
        # 종목 선택 옵션
        analysis_type = st.radio(
            "분석 방식 선택:",
            ["인기 종목", "사용자 정의", "섹터별 분석"]
        )
        
        if analysis_type == "인기 종목":
            # 미리 정의된 인기 종목들
            popular_groups = {
                "🏆 FAANG": ["AAPL", "AMZN", "NFLX", "NVDA", "GOOGL"],
                "💰 금융": ["JPM", "BAC", "WFC", "GS", "MS"],
                "⚡ 전기차": ["TSLA", "NIO", "XPEV", "LI", "RIVN"],
                "🏥 바이오": ["PFE", "JNJ", "MRNA", "BNTX", "GILD"],
                "💎 반도체": ["NVDA", "AMD", "INTC", "TSM", "QCOM"]
            }
            
            selected_group = st.selectbox("종목 그룹 선택:", list(popular_groups.keys()))
            selected_symbols = popular_groups[selected_group]
            
            st.info(f"선택된 종목: {', '.join(selected_symbols)}")
        
        elif analysis_type == "사용자 정의":
            symbol_input = st.text_area(
                "종목 심볼 입력 (쉼표로 구분):",
                value="AAPL, MSFT, GOOGL, TSLA, AMZN",
                help="예: AAPL, MSFT, GOOGL"
            )
            selected_symbols = [s.strip().upper() for s in symbol_input.split(",") if s.strip()]
        
        else:  # 섹터별 분석
            sectors = {
                "기술": ["AAPL", "MSFT", "GOOGL", "META", "NVDA"],
                "헬스케어": ["JNJ", "PFE", "UNH", "ABBV", "TMO"],
                "금융": ["JPM", "BAC", "BRK-B", "WFC", "GS"],
                "소비재": ["AMZN", "TSLA", "HD", "MCD", "NKE"]
            }
            
            selected_sector = st.selectbox("섹터 선택:", list(sectors.keys()))
            selected_symbols = sectors[selected_sector]
        
        # 분석 설정
        col1, col2, col3 = st.columns(3)
        
        with col1:
            min_score = st.slider("최소 점수 필터:", 0, 5, 0)
        
        with col2:
            sort_by = st.selectbox("정렬 기준:", ["점수", "변동률", "심볼"])
        
        with col3:
            show_details = st.checkbox("상세 정보 표시", value=True)
        
        # 분석 실행
        if st.button("🔍 종합 분석 시작", type="primary") and api_key:
            if selected_symbols:
                with st.spinner(f"{len(selected_symbols)}개 종목 분석 중... (약 {len(selected_symbols) * 12}초 소요)"):
                    results = get_stock_analysis(selected_symbols, api_key)
                
                if results:
                    # 필터링
                    filtered_results = [r for r in results if r['score'] >= min_score]
                    
                    # 정렬
                    if sort_by == "점수":
                        filtered_results.sort(key=lambda x: x['score'], reverse=True)
                    elif sort_by == "변동률":
                        filtered_results.sort(key=lambda x: float(x['change_percent']), reverse=True)
                    else:
                        filtered_results.sort(key=lambda x: x['symbol'])
                    
                    st.success(f"✅ 분석 완료! {len(filtered_results)}개 종목 (필터 적용)")
                    
                    # 요약 통계
                    col1, col2, col3, col4 = st.columns(4)
                    
                    strong_buys = len([r for r in filtered_results if r['score'] >= 4])
                    buys = len([r for r in filtered_results if r['score'] == 3])
                    holds = len([r for r in filtered_results if r['score'] == 2])
                    waits = len([r for r in filtered_results if r['score'] <= 1])
                    
                    with col1:
                        st.metric("🚀 강력 매수", strong_buys)
                    with col2:
                        st.metric("📈 매수", buys)
                    with col3:
                        st.metric("📊 보유", holds)
                    with col4:
                        st.metric("⏳ 관망", waits)
                    
                    # 상세 결과 표시
                    for result in filtered_results:
                        score = result['score']
                        confidence = result['confidence']
                        
                        # 제목 색상 결정
                        if score >= 4:
                            title_class = "strong-buy"
                        elif score >= 3:
                            title_class = "buy-signal"
                        elif score >= 2:
                            title_class = "neutral-signal"
                        else:
                            title_class = "warning-signal"
                        
                        with st.expander(f"📊 {result['symbol']} ({result.get('company_name', result['symbol'])}) - {score}/5점 (신뢰도: {confidence}%)"):
                            # 기본 정보
                            col1, col2, col3, col4 = st.columns(4)
                            
                            with col1:
                                st.metric("현재가", f"${result['current_price']:.2f}", f"{result['change_percent']}%")
                            
                            with col2:
                                st.metric("섹터", result.get('sector', 'N/A'))
                            
                            with col3:
                                st.metric("거래량", f"{result['volume']:,}")
                            
                            with col4:
                                st.metric("분석 시간", result['analysis_time'].split()[1])
                            
                            if show_details:
                                # 5가지 신호 상태 표시
                                st.markdown("**📍 매수 신호 상태:**")
                                
                                signal_names = {
                                    'rsi_oversold': 'RSI 과매도 (< 30)',
                                    'macd_golden_cross': 'MACD 골든크로스',
                                    'cci_oversold': 'CCI 과매도 (< -100)',
                                    'mfi_oversold': 'MFI 과매도 (< 20)',
                                    'stoch_rsi_oversold': 'StochRSI 과매도 (< 0.2)'
                                }
                                
                                signal_cols = st.columns(5)
                                for i, (signal_key, signal_name) in enumerate(signal_names.items()):
                                    with signal_cols[i]:
                                        status = result['signals'][signal_key]
                                        emoji = "✅" if status else "❌"
                                        color = "green" if status else "red"
                                        st.markdown(f"<div style='text-align: center; color: {color};'>{emoji}<br>{signal_name}</div>", unsafe_allow_html=True)
                                
                                # 기술적 지표 값들
                                st.markdown("**📊 기술적 지표 값:**")
                                indicators = result['indicators']
                                
                                col_a, col_b = st.columns(2)
                                with col_a:
                                    st.write(f"• **RSI**: {indicators['rsi']} ({'과매도' if indicators['rsi'] < 30 else '과매수' if indicators['rsi'] > 70 else '정상'})")
                                    st.write(f"• **MACD**: {indicators['macd']} (신호: {indicators['macd_signal']})")
                                    st.write(f"• **CCI**: {indicators['cci']}")
                                
                                with col_b:
                                    st.write(f"• **MFI**: {indicators['mfi']}")
                                    st.write(f"• **Stoch RSI**: {indicators['stoch_rsi']}")
                                    st.write(f"• **추천**: {result['recommendation']}")
                            
                            # 추천 등급 표시
                            rec = result['recommendation']
                            if rec == "Strong Buy":
                                st.markdown('<div class="strong-buy">🚀 강력 매수 추천!</div>', unsafe_allow_html=True)
                            elif rec == "Buy":
                                st.markdown('<div class="buy-signal">📈 매수 추천</div>', unsafe_allow_html=True)
                            elif rec == "Hold":
                                st.markdown('<div class="neutral-signal">📊 보유 권장</div>', unsafe_allow_html=True)
                            else:
                                st.markdown('<div class="warning-signal">⏳ 관망 권장</div>', unsafe_allow_html=True)
                
                else:
                    st.error("❌ 분석 결과를 가져올 수 없습니다.")
            else:
                st.warning("⚠️ 분석할 종목을 선택해주세요.")
    
    # 개별 종목 분석 페이지
    elif page == "📊 개별 종목 분석":
        st.title("📊 개별 종목 심층 분석")
        
        col1, col2 = st.columns([2, 1])
        
        with col1:
            symbol = st.text_input("종목 심볼 입력:", value="AAPL", help="예: AAPL, MSFT, GOOGL").upper()
        
        with col2:
            analysis_period = st.selectbox("분석 기간:", ["1개월", "3개월", "6개월"])
        
        if st.button("🔍 심층 분석 시작", type="primary") and api_key and symbol:
            av_api = AlphaVantageAPI(api_key)
            
            with st.spinner(f"📊 {symbol} 심층 분석 중..."):
                data = av_api.get_stock_data(symbol)
                quote = av_api.get_real_time_quote(symbol)
                overview = av_api.get_company_overview(symbol)
            
            if data is not None:
                analysis = analyze_buy_signals(data)
                
                # 회사 정보
                if overview:
                    st.success(f"✅ {overview['name']} ({symbol}) 분석 완료!")
                    
                    col1, col2, col3 = st.columns(3)
                    with col1:
                        st.info(f"**섹터**: {overview['sector']}")
                    with col2:
                        st.info(f"**산업**: {overview['industry']}")
                    with col3:
                        st.info(f"**시가총액**: {overview['market_cap']}")
                
                # 주요 지표
                col1, col2, col3, col4 = st.columns(4)
                
                current_price = quote['price'] if quote else data['Close'].iloc[-1]
                change_percent = quote['change_percent'] if quote else '0'
                
                with col1:
                    st.metric("현재가", f"${current_price:.2f}", f"{change_percent}%")
                
                with col2:
                    st.metric("분석 점수", f"{analysis['score']}/5")
                
                with col3:
                    st.metric("신뢰도", f"{analysis['confidence']}%")
                
                with col4:
                    volume = quote['volume'] if quote else data['Volume'].iloc[-1]
                    st.metric("거래량", f"{volume:,}")
                
                # 차트 표시
                st.subheader("📈 가격 차트")
                chart_data = create_simple_chart(data, symbol)
                if chart_data is not None:
                    st.line_chart(chart_data['Close'])
                
                # 상세 분석
                st.subheader("📊 상세 기술적 분석")
                
                col_left, col_right = st.columns(2)
                
                with col_left:
                    st.markdown("**🔍 5가지 매수 신호 분석:**")
                    
                    signal_descriptions = {
                        'rsi_oversold': ('RSI 과매도', 'RSI < 30일 때 과매도 상태로 반등 가능성'),
                        'macd_golden_cross': ('MACD 골든크로스', 'MACD선이 신호선을 상향 돌파'),
                        'cci_oversold': ('CCI 과매도', 'CCI < -100일 때 매수 시점'),
                        'mfi_oversold': ('MFI 과매도', '자금 유입 부족으로 반등 대기'),
                        'stoch_rsi_oversold': ('StochRSI 과매도', '극도의 과매도 상태')
                    }
                    
                    for signal_key, (name, desc) in signal_descriptions.items():
                        status = analysis['signals'][signal_key]
                        emoji = "✅" if status else "❌"
                        color = "green" if status else "red"
                        st.markdown(f"<div style='color: {color};'>{emoji} <b>{name}</b><br><small>{desc}</small></div><br>", unsafe_allow_html=True)
                
                with col_right:
                    st.markdown("**📊 기술적 지표 값:**")
                    indicators = analysis['indicators']
                    
                    # 지표별 상세 설명
                    st.write(f"**RSI**: {indicators['rsi']}")
                    if indicators['rsi'] < 30:
                        st.success("과매도 - 매수 고려 구간")
                    elif indicators['rsi'] > 70:
                        st.warning("과매수 - 주의 필요")
                    else:
                        st.info("정상 범위")
                    
                    st.write(f"**MACD**: {indicators['macd']}")
                    st.write(f"**신호선**: {indicators['macd_signal']}")
                    if indicators['macd'] > indicators['macd_signal']:
                        st.success("상승 모멘텀")
                    else:
                        st.warning("하락 모멘텀")
                    
                    st.write(f"**CCI**: {indicators['cci']}")
                    st.write(f"**MFI**: {indicators['mfi']}")
                    st.write(f"**Stoch RSI**: {indicators['stoch_rsi']}")
                
                # 투자 결론
                st.markdown("---")
                st.subheader("💡 투자 결론")
                
                rec = analysis['recommendation']
                score = analysis['score']
                confidence = analysis['confidence']
                
                if rec == "Strong Buy" and score >= 4:
                    st.markdown('<div class="strong-buy">🚀 강력 매수 추천!<br>5개 지표 중 4개 이상이 매수 신호를 보이고 있습니다.</div>', unsafe_allow_html=True)
                elif rec == "Buy" and score >= 3:
                    st.markdown('<div class="buy-signal">📈 매수 추천<br>여러 기술적 지표가 긍정적인 신호를 보입니다.</div>', unsafe_allow_html=True)
                elif rec == "Hold" and score >= 2:
                    st.markdown('<div class="neutral-signal">📊 보유 권장<br>현재 포지션 유지를 권장합니다.</div>', unsafe_allow_html=True)
                else:
                    st.markdown('<div class="warning-signal">⏳ 관망 권장<br>더 나은 진입 시점을 기다려보세요.</div>', unsafe_allow_html=True)
                
                # 리스크 분석
                st.markdown("**⚠️ 리스크 요소:**")
                risk_factors = []
                
                if indicators['rsi'] > 70:
                    risk_factors.append("RSI 과매수 상태")
                if indicators['macd'] < indicators['macd_signal']:
                    risk_factors.append("MACD 하락 신호")
                if confidence < 50:
                    risk_factors.append("낮은 신뢰도")
                
                if risk_factors:
                    for factor in risk_factors:
                        st.warning(f"• {factor}")
                else:
                    st.success("• 현재 주요 리스크 요소 없음")
            
            else:
                st.error(f"❌ {symbol} 데이터를 가져올 수 없습니다.")
    
    # 투자 뉴스 페이지
    elif page == "📰 투자 뉴스":
        st.title("📰 투자 뉴스 & AI 요약")
        
        col1, col2 = st.columns([2, 1])
        
        with col1:
            if st.button("🔄 최신 뉴스 업데이트", type="primary"):
                with st.spinner("최신 뉴스를 가져오는 중..."):
                    news_items = get_investment_news()
                    st.session_state.news_items = news_items
        
        with col2:
            auto_refresh = st.checkbox("자동 새로고침 (30초)", value=False)
        
        # AI 뉴스 요약
        if st.button("🤖 AI 뉴스 요약 생성"):
            news_items = getattr(st.session_state, 'news_items', [])
            if news_items:
                with st.spinner("AI가 뉴스를 요약하는 중..."):
                    summary = summarize_news_with_ai(news_items)
                    if summary:
                        st.markdown('<div class="buy-signal">🤖 AI 뉴스 요약</div>', unsafe_allow_html=True)
                        st.write(summary)
                    else:
                        st.info("AI 요약을 생성할 수 없습니다. OpenAI API 키를 확인해주세요.")
        
        # 뉴스 표시
        news_items = getattr(st.session_state, 'news_items', get_investment_news())
        
        if news_items:
            st.subheader(f"📰 최신 투자 뉴스 ({len(news_items)}개)")
            
            for i, news in enumerate(news_items):
                with st.expander(f"{i+1}. {news['title'][:80]}..."):
                    col1, col2 = st.columns([3, 1])
                    
                    with col1:
                        st.markdown(f"**출처**: {news.get('source', 'Unknown')}")
                        st.markdown(f"**발행일**: {news.get('published', 'Recent')}")
                        st.write(news['summary'])
                    
                    with col2:
                        st.markdown(f"[📖 전체 기사 보기]({news['link']})")
        else:
            st.info("뉴스를 불러올 수 없습니다. 인터넷 연결을 확인해주세요.")
    
    # 리포트 페이지
    elif page == "📋 리포트":
        st.title("📋 투자 리포트 생성")
        
        # 세션에 저장된 분석 결과 확인
        if st.session_state.analysis_results:
            results = st.session_state.analysis_results
            
            st.success(f"✅ {len(results)}개 종목 분석 데이터 확보")
            
            # 리포트 설정
            col1, col2 = st.columns(2)
            
            with col1:
                report_type = st.selectbox(
                    "리포트 유형:",
                    ["종합 분석 리포트", "매수 추천 리포트", "리스크 분석 리포트"]
                )
            
            with col2:
                include_charts = st.checkbox("차트 포함", value=True)
            
            # 리포트 미리보기
            st.subheader("📊 리포트 미리보기")
            
            # 요약 통계
            strong_buys = [r for r in results if r['score'] >= 4]
            buys = [r for r in results if r['score'] == 3]
            
            col1, col2, col3, col4 = st.columns(4)
            
            with col1:
                st.metric("총 분석 종목", len(results))
            with col2:
                st.metric("강력 매수", len(strong_buys))
            with col3:
                st.metric("매수 추천", len(buys))
            with col4:
                avg_score = sum(r['score'] for r in results) / len(results)
                st.metric("평균 점수", f"{avg_score:.1f}/5")
            
            # 상위 추천 종목
            st.markdown("**🚀 상위 추천 종목:**")
            top_stocks = sorted(results, key=lambda x: x['score'], reverse=True)[:5]
            
            for stock in top_stocks:
                score_color = "🚀" if stock['score'] >= 4 else "📈" if stock['score'] >= 3 else "📊"
                st.write(f"{score_color} **{stock['symbol']}** - {stock['score']}/5점 (${stock['current_price']:.2f})")
            
            # PDF 생성 버튼
            if st.button("📄 PDF 리포트 생성", type="primary"):
                with st.spinner("PDF 리포트를 생성하는 중..."):
                    pdf_data = generate_pdf_report(results)
                    
                    if pdf_data:
                        b64_pdf = base64.b64encode(pdf_data).decode()
                        href = f'<a href="data:application/pdf;base64,{b64_pdf}" download="SmartInvestor_Report_{datetime.now().strftime("%Y%m%d_%H%M")}.pdf">📥 PDF 다운로드</a>'
                        st.markdown(href, unsafe_allow_html=True)
                        st.success("✅ PDF 리포트가 생성되었습니다!")
                    else:
                        st.error("❌ PDF 생성에 실패했습니다.")
        
        else:
            st.info("📊 먼저 '실시간 분석' 페이지에서 종목 분석을 실행해주세요.")
            
            if st.button("🔗 실시간 분석 페이지로 이동"):
                st.rerun()
    
    # 시스템 진단 페이지
    elif page == "⚙️ 시스템 진단":
        st.title("⚙️ 시스템 진단")
        
        # API 연결 테스트
        st.subheader("🔌 API 연결 상태")
        
        if api_key:
            if st.button("🧪 Alpha Vantage API 테스트"):
                av_api = AlphaVantageAPI(api_key)
                
                with st.spinner("API 연결을 테스트하는 중..."):
                    # 간단한 테스트 쿼리
                    test_data = av_api.get_real_time_quote("AAPL")
                
                if test_data:
                    st.success("✅ Alpha Vantage API 연결 성공!")
                    st.json(test_data)
                else:
                    st.error("❌ API 연결 실패. API 키를 확인해주세요.")
        else:
            st.warning("⚠️ API 키가 설정되지 않았습니다.")
        
        # 데이터베이스 상태
        st.subheader("💾 데이터베이스 상태")
        
        try:
            conn = sqlite3.connect('smartinvestor.db')
            c = conn.cursor()
            
            # 사용자 수 확인
            c.execute("SELECT COUNT(*) FROM users")
            user_count = c.fetchone()[0]
            
            # 분석 히스토리 확인
            c.execute("SELECT COUNT(*) FROM analysis_history")
            history_count = c.fetchone()[0]
            
            col1, col2 = st.columns(2)
            with col1:
                st.metric("등록 사용자", user_count)
            with col2:
                st.metric("분석 히스토리", history_count)
            
            st.success("✅ 데이터베이스 연결 정상")
            conn.close()
            
        except Exception as e:
            st.error(f"❌ 데이터베이스 오류: {e}")
        
        # 성능 정보
        st.subheader("📊 성능 정보")
        
        col1, col2, col3 = st.columns(3)
        
        with col1:
            st.info("**API 제한**  \n분당 5회 호출")
        
        with col2:
            st.info("**분석 시간**  \n종목당 약 12초")
        
        with col3:
            st.info("**데이터 지연**  \n15-20분 지연")
        
        # 문제 해결 가이드
        st.subheader("🛠️ 문제 해결 가이드")
        
        with st.expander("❌ API 오류가 발생할 때"):
            st.markdown("""
            **가능한 원인:**
            - API 키가 잘못되었거나 만료됨
            - API 호출 제한 초과 (분당 5회)
            - 네트워크 연결 문제
            
            **해결 방법:**
            1. API 키 재확인
            2. 잠시 후 다시 시도
            3. 종목 수를 줄여서 분석
            """)
        
        with st.expander("🐌 분석이 느릴 때"):
            st.markdown("""
            **원인:**
            - API 호출 제한으로 인한 대기 시간
            - 네트워크 속도 문제
            
            **해결 방법:**
            1. 분석할 종목 수를 줄이기
            2. 안정적인 네트워크 환경 사용
            3. 피크 시간대 피하기
            """)
        
        with st.expander("📊 데이터가 없을 때"):
            st.markdown("""
            **원인:**
            - 잘못된 종목 심볼
            - 거래 중단된 종목
            - API 데이터 부족
            
            **해결 방법:**
            1. 종목 심볼 정확히 입력
            2. 유명한 종목으로 테스트
            3. 다른 종목으로 시도
            """)
    
    # 투자 가이드 페이지
    elif page == "📚 투자 가이드":
        st.title("📚 투자 가이드")
        
        guide_section = st.selectbox(
            "가이드 선택:",
            ["📊 기술적 지표 해설", "🎯 매매 전략", "⚠️ 리스크 관리", "💡 투자 팁"]
        )
        
        if guide_section == "📊 기술적 지표 해설":
            st.subheader("📊 5가지 핵심 기술적 지표")
            
            # RSI 설명
            with st.expander("🔴 RSI (Relative Strength Index) - 상대강도지수"):
                st.markdown("""
                **개념**: 가격 변동의 상승분과 하락분의 평균을 구하여 상승분이 총 변동에서 차지하는 비율을 나타냄
                
                **해석**:
                - **30 이하**: 과매도 상태, 매수 고려
                - **70 이상**: 과매수 상태, 매도 고려  
                - **30-70**: 정상 범위
                
                **매매 신호**: RSI < 30일 때 반등 가능성 높음
                """)
            
            # MACD 설명
            with st.expander("📈 MACD (Moving Average Convergence Divergence)"):
                st.markdown("""
                **개념**: 단기 이동평균선과 장기 이동평균선의 차이를 나타내는 지표
                
                **구성**:
                - **MACD선**: 12일 지수이동평균 - 26일 지수이동평균
                - **신호선**: MACD선의 9일 지수이동평균
                - **히스토그램**: MACD선 - 신호선
                
                **매매 신호**:
                - **골든크로스**: MACD선이 신호선을 상향 돌파 → 매수
                - **데드크로스**: MACD선이 신호선을 하향 돌파 → 매도
                """)
            
            # CCI 설명
            with st.expander("🔵 CCI (Commodity Channel Index) - 상품채널지수"):
                st.markdown("""
                **개념**: 현재 가격이 일정 기간의 평균 가격에서 얼마나 벗어났는지 측정
                
                **해석**:
                - **+100 이상**: 과매수 구간
                - **-100 이하**: 과매도 구간, 매수 고려
                - **-100 ~ +100**: 정상 범위
                
                **매매 신호**: CCI < -100일 때 매수 타이밍
                """)
            
            # MFI 설명
            with st.expander("💰 MFI (Money Flow Index) - 자금흐름지수"):
                st.markdown("""
                **개념**: 거래량을 고려한 RSI, 자금의 유입과 유출을 분석
                
                **해석**:
                - **20 이하**: 과매도, 자금 유입 부족
                - **80 이상**: 과매수, 자금 유출 가능성
                - **20-80**: 정상 범위
                
                **매매 신호**: MFI < 20일 때 반등 대기 상태
                """)
            
            # Stochastic RSI 설명
            with st.expander("⚡ Stochastic RSI - 스토캐스틱 RSI"):
                st.markdown("""
                **개념**: RSI에 스토캐스틱 개념을 적용하여 더 민감하게 만든 지표
                
                **해석**:
                - **0.2 이하**: 극도의 과매도 상태
                - **0.8 이상**: 극도의 과매수 상태
                - **0.2-0.8**: 정상 범위
                
                **매매 신호**: Stoch RSI < 0.2일 때 강한 매수 신호
                """)
        
        elif guide_section == "🎯 매매 전략":
            st.subheader("🎯 SmartInvestor Pro 매매 전략")
            
            st.markdown("""
            ### 📊 점수 기반 매매 전략
            
            **5점 만점 시스템**:
            - 각 기술적 지표가 매수 조건을 만족하면 1점씩 부여
            - 총 5개 지표로 최대 5점까지 가능
            
            ### 🚀 매매 신호별 전략
            """)
            
            col1, col2 = st.columns(2)
            
            with col1:
                st.markdown("""
                **🚀 강력 매수 (4-5점)**
                - 적극적인 매수 고려
                - 포지션 크기: 포트폴리오의 5-10%
                - 손절매: -10% 설정
                
                **📈 매수 (3점)**  
                - 매수 고려
                - 포지션 크기: 포트폴리오의 3-5%
                - 손절매: -8% 설정
                """)
            
            with col2:
                st.markdown("""
                **📊 보유 (2점)**
                - 기존 포지션 유지
                - 추가 매수는 신중히 결정
                - 손절매: -5% 설정
                
                **⏳ 관망 (0-1점)**
                - 매수 보류
                - 더 좋은 기회 대기
                - 관찰 리스트에 추가
                """)
            
            st.markdown("""
            ### ⏰ 타이밍 전략
            
            **최적 매수 타이밍**:
            1. 5개 지표 중 3개 이상 매수 신호
            2. RSI가 30 이하에서 반등 시작
            3. MACD 골든크로스 발생
            4. 거래량 증가 동반
            
            **매도 타이밍**:
            1. 목표 수익률 달성 (10-20%)
            2. 매수 신호 3개 이하로 감소
            3. RSI 70 이상 과매수 진입
            4. 손절매 라인 터치
            """)
        
        elif guide_section == "⚠️ 리스크 관리":
            st.subheader("⚠️ 리스크 관리 가이드")
            
            st.markdown("""
            ### 🛡️ 기본 리스크 관리 원칙
            """)
            
            col1, col2 = st.columns(2)
            
            with col1:
                st.markdown("""
                **💰 자금 관리**
                - 한 종목에 전체 자금의 10% 이하 투자
                - 전체 주식 투자는 자산의 70% 이하
                - 비상금 6개월치는 별도 보관
                
                **📊 포트폴리오 분산**
                - 최소 5-10개 종목 분산 투자
                - 다양한 섹터에 분산
                - 국가별 분산 고려
                """)
            
            with col2:
                st.markdown("""
                **🔴 손절매 원칙**
                - 매수 전 손절매 가격 미리 설정
                - 감정에 휩쓸리지 말고 기계적 실행
                - 보통 -5% ~ -10% 수준에서 설정
                
                **📈 익절 전략**
                - 목표 수익률 달성 시 부분 매도
                - 수익의 50% 확정, 50% 추가 상승 기대
                - 욕심 금지, 만족할 줄 알기
                """)
            
            st.markdown("""
            ### ⚠️ 주요 위험 신호
            
            **🔴 즉시 매도 고려 상황**:
            1. 회사 펀더멘털 급속 악화
            2. 업종 전체 부정적 뉴스
            3. 시장 전체 급락 (VIX 급상승)
            4. 개인 투자 목적 변경 (급전 필요 등)
            
            **⚠️ 주의 깊게 관찰할 상황**:
            1. 거래량 급감으로 유동성 부족
            2. 기술적 지표 하나씩 악화
            3. 섹터 로테이션으로 자금 이탈
            4. 거시경제 지표 변화
            """)
        
        else:  # 투자 팁
            st.subheader("💡 실전 투자 팁")
            
            tip_category = st.selectbox(
                "팁 카테고리:",
                ["🔰 초보자 팁", "📊 분석 팁", "🧠 심리 관리", "⏰ 타이밍"]
            )
            
            if tip_category == "🔰 초보자 팁":
                st.markdown("""
                ### 🔰 주식 투자 초보자를 위한 10가지 팁
                
                1. **📚 공부가 우선**: 투자하기 전에 기본 지식 습득
                2. **💰 여유 자금으로만**: 생활비나 비상금은 절대 투자 금지
                3. **🎯 목표 설정**: 명확한 투자 목적과 기간 설정
                4. **📊 분산 투자**: 계란을 한 바구니에 담지 말기
                5. **⏰ 장기 관점**: 단기 변동에 일희일비하지 말기
                6. **📰 정보 수집**: 다양한 정보원 활용하여 판단
                7. **🔍 기업 분석**: 투자하는 회사에 대해 충분히 알기
                8. **💡 감정 배제**: 욕심과 공포에 휩쓸리지 말기
                9. **📝 기록 습관**: 매매 일지 작성으로 실수 줄이기
                10. **🎓 지속 학습**: 끊임없이 공부하고 개선하기
                """)
            
            elif tip_category == "📊 분석 팁":
                st.markdown("""
                ### 📊 기술적 분석 활용 팁
                
                **🔍 지표 조합 활용**:
                - 단일 지표에만 의존하지 말고 여러 지표 종합 판단
                - SmartInvestor Pro의 5개 지표 점수 시스템 활용
                - 상반된 신호가 나올 때는 신중하게 판단
                
                **📈 추세와 함께 분석**:
                - 상승 추세에서는 매수 신호에 더 높은 가중치
                - 하락 추세에서는 매도 신호 우선 고려
                - 횡보 시장에서는 과매수/과매도 지표 활용
                
                **📊 거래량 확인**:
                - 기술적 신호와 거래량 증가가 동반되어야 신뢰성 높음
                - 거래량 없는 가격 상승은 지속력 부족
                - 급격한 거래량 증가는 변곡점 신호
                """)
            
            elif tip_category == "🧠 심리 관리":
                st.markdown("""
                ### 🧠 투자 심리 관리법
                
                **😨 공포 극복 방법**:
                - 미리 설정한 투자 계획 준수
                - 급락 시에도 장기 관점 유지
                - 분할 매수로 평균 단가 낮추기
                
                **😍 욕심 억제 방법**:
                - 목표 수익률 달성 시 부분 매도
                - "더 오를 것 같다"는 생각 경계
                - 수익 실현의 기쁨을 만끽하기
                
                **🎯 감정적 매매 방지**:
                - 매매 룰을 미리 정하고 지키기
                - 뉴스나 소문에 휩쓸리지 말기
                - 손실을 만회하려는 도박적 투자 금지
                """)
            
            else:  # 타이밍
                st.markdown("""
                ### ⏰ 매매 타이밍 포착법
                
                **🌅 최적 매수 타이밍**:
                1. **기술적 신호**: 5개 지표 중 3개 이상 매수 신호
                2. **시장 상황**: 전체 시장이 안정적이거나 상승 국면
                3. **개별 재료**: 긍정적인 기업 뉴스나 실적 발표
                4. **거시 환경**: 금리나 경제 지표가 우호적
                
                **🌇 매도 타이밍 포착**:
                1. **수익 실현**: 목표 수익률 달성
                2. **신호 악화**: 매수 신호 2개 이하로 감소
                3. **펀더멘털 변화**: 기업 실적이나 전망 악화
                4. **시장 환경**: 전체적인 시장 분위기 악화
                
                **⏰ 시간대별 전략**:
                - **09:00-10:00**: 시가 갭 확인 후 신중한 매매
                - **10:00-14:00**: 안정적인 매매 구간
                - **14:00-15:20**: 기관 투자자 활발, 큰 흐름 파악
                - **15:20-15:30**: 마감 직전 급변동 주의
                """)
    
    # 푸터
    st.markdown("---")
    col1, col2, col3 = st.columns(3)
    
    with col1:
        st.markdown("**📞 지원**")
        st.markdown("이메일: admin@smartinvestor.com")
    
    with col2:
        st.markdown("**⚠️ 면책 조항**")
        st.markdown("투자 참고용 도구입니다.")
    
    with col3:
        st.markdown("**📊 버전**")
        st.markdown("SmartInvestor Pro v2.0")

# 프로그램 실행
if __name__ == "__main__":
    main()