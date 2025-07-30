import streamlit as st
import pandas as pd
import numpy as np
import requests
import json
import time
from datetime import datetime, timedelta
import sqlite3
import hashlib
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import plotly.express as px
from fpdf import FPDF
import base64
import feedparser
import re

# 페이지 설정
st.set_page_config(
    page_title="SmartInvestor Pro",
    page_icon="📈",
    layout="wide",
    initial_sidebar_state="expanded"
)

# CSS 스타일
st.markdown("""
<style>
    .main-header {
        font-size: 2.5rem;
        font-weight: bold;
        text-align: center;
        color: #1f77b4;
        margin-bottom: 2rem;
    }
    .metric-card {
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        padding: 1rem;
        border-radius: 10px;
        color: white;
        margin: 0.5rem 0;
    }
    .buy-signal {
        background: linear-gradient(135deg, #11998e 0%, #38ef7d 100%);
        padding: 1rem;
        border-radius: 10px;
        color: white;
        text-align: center;
        margin: 1rem 0;
    }
    .warning-signal {
        background: linear-gradient(135deg, #ff9a9e 0%, #fecfef 100%);
        padding: 1rem;
        border-radius: 10px;
        color: #333;
        text-align: center;
        margin: 1rem 0;
    }
</style>
""", unsafe_allow_html=True)

# 데이터베이스 초기화
def init_database():
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
    
    # 관리자 계정 생성
    admin_email = "admin@smartinvestor.com"
    admin_password = hashlib.bcrypt.hashpw("admin123".encode('utf-8'), hashlib.bcrypt.gensalt())
    
    try:
        c.execute("INSERT INTO users (email, password_hash, is_admin) VALUES (?, ?, ?)",
                 (admin_email, admin_password.decode('utf-8'), True))
    except sqlite3.IntegrityError:
        pass
    
    conn.commit()
    conn.close()

# Alpha Vantage API 클래스
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
            
            response = requests.get(self.base_url, params=params, timeout=10)
            data = response.json()
            
            if 'Error Message' in data:
                st.error(f"심볼 오류: {symbol}")
                return None
                
            if 'Note' in data:
                st.warning("API 호출 제한에 도달했습니다.")
                return None
                
            time_series = data.get('Time Series (Daily)', {})
            if not time_series:
                return None
                
            # DataFrame 변환
            df_data = []
            for date_str, values in time_series.items():
                df_data.append({
                    'Date': pd.to_datetime(date_str),
                    'Open': float(values['1. open']),
                    'High': float(values['2. high']),
                    'Low': float(values['3. low']),
                    'Close': float(values['4. close']),
                    'Volume': int(values['5. volume'])
                })
            
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
            
            response = requests.get(self.base_url, params=params, timeout=10)
            data = response.json()
            
            quote = data.get('Global Quote', {})
            if not quote:
                return None
                
            return {
                'symbol': quote.get('01. symbol'),
                'price': float(quote.get('05. price', 0)),
                'change': float(quote.get('09. change', 0)),
                'change_percent': quote.get('10. change percent', '0%').replace('%', ''),
                'volume': int(quote.get('06. volume', 0))
            }
            
        except Exception as e:
            return None

# 기술적 지표 계산
def calculate_rsi(data, period=14):
    """RSI 계산"""
    if len(data) < period:
        return pd.Series([50] * len(data), index=data.index)
    
    delta = data['Close'].diff()
    gain = delta.where(delta > 0, 0)
    loss = -delta.where(delta < 0, 0)
    
    avg_gain = gain.rolling(window=period).mean()
    avg_loss = loss.rolling(window=period).mean()
    
    rs = avg_gain / avg_loss
    rsi = 100 - (100 / (1 + rs))
    return rsi.fillna(50)

def calculate_macd(data, fast=12, slow=26, signal=9):
    """MACD 계산"""
    if len(data) < slow:
        return {
            'macd': pd.Series([0] * len(data), index=data.index),
            'signal': pd.Series([0] * len(data), index=data.index),
            'histogram': pd.Series([0] * len(data), index=data.index)
        }
    
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

def calculate_cci(data, period=20):
    """CCI 계산"""
    if len(data) < period:
        return pd.Series([0] * len(data), index=data.index)
    
    tp = (data['High'] + data['Low'] + data['Close']) / 3
    sma = tp.rolling(window=period).mean()
    mad = tp.rolling(window=period).apply(lambda x: abs(x - x.mean()).mean())
    cci = (tp - sma) / (0.015 * mad)
    return cci.fillna(0)

def calculate_mfi(data, period=14):
    """MFI 계산"""
    if len(data) < period + 1:
        return pd.Series([50] * len(data), index=data.index)
    
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

def calculate_stoch_rsi(data, period=14):
    """Stochastic RSI 계산"""
    if len(data) < period:
        return pd.Series([0.5] * len(data), index=data.index)
    
    rsi = calculate_rsi(data, period)
    stoch_rsi = (rsi - rsi.rolling(window=period).min()) / (rsi.rolling(window=period).max() - rsi.rolling(window=period).min())
    return stoch_rsi.fillna(0.5)

# 매수 신호 분석
def analyze_buy_signals(data):
    """매수 신호 분석"""
    if data is None or len(data) < 30:
        return {'score': 0, 'signals': {}, 'indicators': {}}
    
    # 기술적 지표 계산
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
    
    # 매수 신호 판단
    signals = {
        'rsi_oversold': latest_rsi < 30,
        'macd_golden_cross': latest_macd > latest_signal,
        'cci_oversold': latest_cci < -100,
        'mfi_oversold': latest_mfi < 20,
        'stoch_rsi_oversold': latest_stoch_rsi < 0.2
    }
    
    # 점수 계산
    score = sum(signals.values())
    
    return {
        'score': score,
        'signals': signals,
        'indicators': {
            'rsi': round(latest_rsi, 2),
            'macd': round(latest_macd, 4),
            'cci': round(latest_cci, 2),
            'mfi': round(latest_mfi, 2),
            'stoch_rsi': round(latest_stoch_rsi, 3)
        }
    }

# 메인 분석 함수
def get_stock_analysis(symbols, api_key):
    """주식 분석 실행"""
    av_api = AlphaVantageAPI(api_key)
    results = []
    
    progress_bar = st.progress(0)
    status_text = st.empty()
    
    for i, symbol in enumerate(symbols):
        status_text.text(f'분석 중: {symbol} ({i+1}/{len(symbols)})')
        
        # 데이터 가져오기
        data = av_api.get_stock_data(symbol)
        quote = av_api.get_real_time_quote(symbol)
        
        if data is not None and len(data) > 0:
            # 분석 실행
            analysis = analyze_buy_signals(data)
            
            current_price = quote['price'] if quote else data['Close'].iloc[-1]
            
            result = {
                'symbol': symbol,
                'current_price': current_price,
                'score': analysis['score'],
                'signals': analysis['signals'],
                'indicators': analysis['indicators'],
                'change_percent': quote['change_percent'] if quote else '0'
            }
            
            results.append(result)
        
        # API 호출 제한 (분당 5회)
        if i < len(symbols) - 1:
            time.sleep(12)
        
        progress_bar.progress((i + 1) / len(symbols))
    
    progress_bar.empty()
    status_text.empty()
    
    return results

# 차트 생성
def create_stock_chart(symbol, data, indicators):
    """주식 차트 생성"""
    if data is None or len(data) == 0:
        return None
    
    # 서브플롯 생성
    fig = make_subplots(
        rows=3, cols=1,
        shared_xaxes=True,
        vertical_spacing=0.05,
        subplot_titles=[f'{symbol} 주가', 'RSI', 'MACD'],
        row_heights=[0.6, 0.2, 0.2]
    )
    
    # 캔들스틱 차트
    fig.add_trace(
        go.Candlestick(
            x=data.index,
            open=data['Open'],
            high=data['High'],
            low=data['Low'],
            close=data['Close'],
            name=symbol
        ),
        row=1, col=1
    )
    
    # RSI
    rsi = calculate_rsi(data)
    fig.add_trace(
        go.Scatter(x=data.index, y=rsi, name='RSI', line=dict(color='purple')),
        row=2, col=1
    )
    fig.add_hline(y=70, line_dash="dash", line_color="red", row=2, col=1)
    fig.add_hline(y=30, line_dash="dash", line_color="green", row=2, col=1)
    
    # MACD
    macd_data = calculate_macd(data)
    fig.add_trace(
        go.Scatter(x=data.index, y=macd_data['macd'], name='MACD', line=dict(color='blue')),
        row=3, col=1
    )
    fig.add_trace(
        go.Scatter(x=data.index, y=macd_data['signal'], name='Signal', line=dict(color='red')),
        row=3, col=1
    )
    
    fig.update_layout(
        title=f'{symbol} 기술적 분석',
        xaxis_rangeslider_visible=False,
        height=800
    )
    
    return fig

# 뉴스 가져오기
def get_investment_news():
    """투자 뉴스 가져오기"""
    try:
        # Investing.com RSS 피드
        feed_url = "https://www.investing.com/rss/news.rss"
        feed = feedparser.parse(feed_url)
        
        news_items = []
        for entry in feed.entries[:10]:
            news_items.append({
                'title': entry.title,
                'link': entry.link,
                'published': entry.published,
                'summary': entry.get('summary', '')[:200] + '...'
            })
        
        return news_items
    except:
        return []

# PDF 리포트 생성
def generate_pdf_report(analysis_results):
    """PDF 투자 리포트 생성"""
    pdf = FPDF()
    pdf.add_page()
    pdf.set_font('Arial', 'B', 16)
    
    # 제목
    pdf.cell(0, 10, 'SmartInvestor Pro - Investment Report', 0, 1, 'C')
    pdf.ln(10)
    
    # 생성 날짜
    pdf.set_font('Arial', '', 10)
    pdf.cell(0, 10, f'Generated on: {datetime.now().strftime("%Y-%m-%d %H:%M")}', 0, 1)
    pdf.ln(5)
    
    # 분석 결과
    pdf.set_font('Arial', 'B', 12)
    pdf.cell(0, 10, 'Analysis Results:', 0, 1)
    pdf.ln(5)
    
    for result in analysis_results:
        pdf.set_font('Arial', 'B', 10)
        pdf.cell(0, 8, f"{result['symbol']} - Score: {result['score']}/5", 0, 1)
        
        pdf.set_font('Arial', '', 9)
        pdf.cell(0, 6, f"Current Price: ${result['current_price']:.2f}", 0, 1)
        pdf.cell(0, 6, f"RSI: {result['indicators']['rsi']}", 0, 1)
        pdf.cell(0, 6, f"MACD: {result['indicators']['macd']}", 0, 1)
        pdf.ln(3)
    
    return pdf.output(dest='S').encode('latin1')

# 메인 애플리케이션
def main():
    # 데이터베이스 초기화
    init_database()
    
    # 사이드바
    st.sidebar.title("🚀 SmartInvestor Pro")
    
    # API 키 확인
    api_key = st.secrets.get("ALPHA_VANTAGE_API_KEY", "")
    if not api_key:
        st.error("⚠️ Alpha Vantage API 키가 설정되지 않았습니다.")
        st.info("Streamlit Cloud의 Secrets에 ALPHA_VANTAGE_API_KEY를 추가해주세요.")
        st.stop()
    
    # 페이지 선택
    page = st.sidebar.selectbox(
        "페이지 선택",
        ["🏠 홈", "📈 실시간 분석", "📊 개별 종목 분석", "📰 투자 뉴스", "📋 리포트"]
    )
    
    if page == "🏠 홈":
        st.markdown('<div class="main-header">🚀 SmartInvestor Pro</div>', unsafe_allow_html=True)
        st.markdown("### AI와 기술적 분석을 활용한 스마트 투자 분석 도구")
        
        col1, col2, col3 = st.columns(3)
        
        with col1:
            st.markdown("""
            **📈 주요 기능**
            - 5가지 기술적 지표 분석
            - 점수 기반 매수 신호
            - 실시간 시장 데이터
            """)
        
        with col2:
            st.markdown("""
            **🎯 분석 지표**
            - RSI (상대강도지수)
            - MACD (이동평균수렴확산)
            - CCI (상품채널지수)
            - MFI (자금흐름지수)
            - Stochastic RSI
            """)
        
        with col3:
            st.markdown("""
            **⚠️ 주의사항**
            - 투자 참고용 도구입니다
            - 실제 투자는 신중히 결정하세요
            - 분산 투자를 권장합니다
            """)
    
    elif page == "📈 실시간 분석":
        st.title("📈 실시간 주식 분석")
        
        # 기본 종목 설정
        default_symbols = ['AAPL', 'MSFT', 'GOOGL', 'TSLA', 'AMZN', 'NVDA', 'META', 'NFLX']
        
        selected_symbols = st.multiselect(
            "분석할 종목을 선택하세요:",
            default_symbols,
            default=['AAPL', 'MSFT', 'GOOGL']
        )
        
        if st.button("🔍 분석 시작", type="primary"):
            if selected_symbols:
                with st.spinner("분석 중입니다..."):
                    results = get_stock_analysis(selected_symbols, api_key)
                
                if results:
                    # 점수순 정렬
                    results.sort(key=lambda x: x['score'], reverse=True)
                    
                    st.success(f"✅ {len(results)}개 종목 분석 완료!")
                    
                    # 결과 표시
                    for result in results:
                        with st.expander(f"📊 {result['symbol']} - 점수: {result['score']}/5"):
                            col1, col2 = st.columns(2)
                            
                            with col1:
                                st.metric(
                                    "현재가",
                                    f"${result['current_price']:.2f}",
                                    f"{result['change_percent']}%"
                                )
                                
                                # 신호 상태
                                st.write("**📍 매수 신호:**")
                                for signal_name, signal_value in result['signals'].items():
                                    emoji = "✅" if signal_value else "❌"
                                    signal_korean = {
                                        'rsi_oversold': 'RSI 과매도',
                                        'macd_golden_cross': 'MACD 골든크로스',
                                        'cci_oversold': 'CCI 과매도',
                                        'mfi_oversold': 'MFI 과매도',
                                        'stoch_rsi_oversold': 'StochRSI 과매도'
                                    }
                                    st.write(f"{emoji} {signal_korean.get(signal_name, signal_name)}")
                            
                            with col2:
                                st.write("**📊 기술적 지표:**")
                                indicators = result['indicators']
                                st.write(f"RSI: {indicators['rsi']}")
                                st.write(f"MACD: {indicators['macd']}")
                                st.write(f"CCI: {indicators['cci']}")
                                st.write(f"MFI: {indicators['mfi']}")
                                st.write(f"Stoch RSI: {indicators['stoch_rsi']}")
                            
                            # 매수 신호 평가
                            if result['score'] >= 4:
                                st.markdown('<div class="buy-signal">🚀 강력한 매수 신호!</div>', unsafe_allow_html=True)
                            elif result['score'] >= 3:
                                st.markdown('<div class="buy-signal">📈 매수 신호</div>', unsafe_allow_html=True)
                            else:
                                st.markdown('<div class="warning-signal">⚠️ 관망 권장</div>', unsafe_allow_html=True)
                else:
                    st.error("분석 결과를 가져올 수 없습니다.")
            else:
                st.warning("분석할 종목을 선택해주세요.")
    
    elif page == "📊 개별 종목 분석":
        st.title("📊 개별 종목 심층 분석")
        
        symbol = st.text_input("종목 심볼을 입력하세요 (예: AAPL)", value="AAPL").upper()
        
        if st.button("분석하기"):
            if symbol:
                av_api = AlphaVantageAPI(api_key)
                
                with st.spinner(f"{symbol} 데이터를 가져오는 중..."):
                    data = av_api.get_stock_data(symbol)
                    quote = av_api.get_real_time_quote(symbol)
                
                if data is not None:
                    analysis = analyze_buy_signals(data)
                    
                    # 기본 정보
                    col1, col2, col3 = st.columns(3)
                    
                    with col1:
                        current_price = quote['price'] if quote else data['Close'].iloc[-1]
                        change_percent = quote['change_percent'] if quote else '0'
                        st.metric("현재가", f"${current_price:.2f}", f"{change_percent}%")
                    
                    with col2:
                        st.metric("매수 신호 점수", f"{analysis['score']}/5")
                    
                    with col3:
                        volume = quote['volume'] if quote else data['Volume'].iloc[-1]
                        st.metric("거래량", f"{volume:,}")
                    
                    # 차트
                    chart = create_stock_chart(symbol, data.tail(60), analysis['indicators'])
                    if chart:
                        st.plotly_chart(chart, use_container_width=True)
                    
                    # 상세 분석
                    st.subheader("📈 기술적 분석 상세")
                    
                    col1, col2 = st.columns(2)
                    
                    with col1:
                        st.write("**지표 값:**")
                        for indicator, value in analysis['indicators'].items():
                            st.write(f"• {indicator.upper()}: {value}")
                    
                    with col2:
                        st.write("**신호 분석:**")
                        for signal, status in analysis['signals'].items():
                            status_text = "활성" if status else "비활성"
                            emoji = "🟢" if status else "🔴"
                            st.write(f"{emoji} {signal}: {status_text}")
                
                else:
                    st.error(f"{symbol} 데이터를 가져올 수 없습니다.")
    
    elif page == "📰 투자 뉴스":
        st.title("📰 투자 뉴스")
        
        with st.spinner("최신 뉴스를 가져오는 중..."):
            news_items = get_investment_news()
        
        if news_items:
            for news in news_items:
                with st.expander(news['title']):
                    st.write(f"**발행일:** {news['published']}")
                    st.write(news['summary'])
                    st.markdown(f"[전체 기사 보기]({news['link']})")
        else:
            st.info("뉴스를 가져올 수 없습니다.")
    
    elif page == "📋 리포트":
        st.title("📋 투자 리포트 생성")
        
        st.info("실시간 분석 페이지에서 분석을 먼저 실행해주세요.")
        
        # 세션 상태에 분석 결과가 있다면 PDF 생성 버튼 표시
        if st.button("📄 PDF 리포트 생성"):
            st.info("PDF 리포트 기능은 현재 개발 중입니다.")

if __name__ == "__main__":
    main()