import streamlit as st
import yfinance as yf
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import plotly.graph_objects as go
import ta
import sqlite3
import bcrypt
from fpdf import FPDF
import feedparser
from streamlit_option_menu import option_menu
import requests
import json

# 번역 관련 - 제거 (의존성 충돌)
TRANSLATION_ENABLED = False

# OpenAI 관련 선택적 import
try:
    import openai
    OPENAI_AVAILABLE = True
except ImportError:
    OPENAI_AVAILABLE = False

# 페이지 설정
st.set_page_config(
    page_title="SmartInvestor Pro",
    page_icon="📈",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Streamlit Secrets에서 API 키 가져오기 (선택적)
AI_ENABLED = False
try:
    if OPENAI_AVAILABLE and 'OPENAI_API_KEY' in st.secrets:
        # 새로운 OpenAI API 방식
        try:
            from openai import OpenAI
            client = OpenAI(api_key=st.secrets['OPENAI_API_KEY'])
            AI_ENABLED = True
        except:
            # 구버전 OpenAI API 방식
            openai.api_key = st.secrets['OPENAI_API_KEY']
            client = None
            AI_ENABLED = True
except:
    AI_ENABLED = False

# CSS 스타일
st.markdown("""
<style>
    .main-header {
        text-align: center;
        color: #1E88E5;
        margin-bottom: 30px;
        font-size: 2.5em;
    }
    .metric-card {
        background-color: #f0f2f6;
        padding: 20px;
        border-radius: 10px;
        box-shadow: 0 2px 4px rgba(0,0,0,0.1);
        text-align: center;
    }
    .recommendation-card {
        background-color: #e8f5e9;
        padding: 15px;
        border-radius: 8px;
        margin-bottom: 10px;
        border-left: 4px solid #4caf50;
    }
    .warning-card {
        background-color: #fff3e0;
        padding: 15px;
        border-radius: 8px;
        margin-bottom: 10px;
        border-left: 4px solid #ff9800;
    }
    .news-card {
        background-color: #e3f2fd;
        padding: 15px;
        border-radius: 8px;
        margin-bottom: 10px;
        border-left: 4px solid #2196f3;
    }
    .crypto-card {
        background-color: #f3e5f5;
        padding: 15px;
        border-radius: 8px;
        margin-bottom: 10px;
        border-left: 4px solid #9c27b0;
    }
    .market-button {
        background-color: #1976d2;
        color: white;
        padding: 10px 20px;
        text-align: center;
        text-decoration: none;
        display: inline-block;
        font-size: 16px;
        margin: 4px 2px;
        cursor: pointer;
        border-radius: 8px;
        border: none;
    }
    .market-button:hover {
        background-color: #1565c0;
    }
    .stTabs [data-baseweb="tab-list"] {
        gap: 24px;
    }
    .stTabs [data-baseweb="tab"] {
        height: 50px;
        padding-left: 20px;
        padding-right: 20px;
    }
</style>
""", unsafe_allow_html=True)

# 데이터베이스 초기화
def init_database():
    conn = sqlite3.connect('smartinvestor.db')
    c = conn.cursor()
    
    # 사용자 테이블
    c.execute('''CREATE TABLE IF NOT EXISTS users
                 (id INTEGER PRIMARY KEY AUTOINCREMENT,
                  username TEXT UNIQUE NOT NULL,
                  email TEXT UNIQUE NOT NULL,
                  password TEXT NOT NULL,
                  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                  is_admin INTEGER DEFAULT 0)''')
    
    # 분석 기록 테이블 (asset_type 컬럼 추가)
    c.execute('''CREATE TABLE IF NOT EXISTS analysis_history
                 (id INTEGER PRIMARY KEY AUTOINCREMENT,
                  user_id INTEGER,
                  symbol TEXT,
                  asset_type TEXT DEFAULT 'stock',
                  analysis_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                  score REAL,
                  recommendation TEXT,
                  FOREIGN KEY (user_id) REFERENCES users (id))''')
    
    # 관리자 계정 생성 (없으면)
    admin_password = bcrypt.hashpw("admin123".encode('utf-8'), bcrypt.gensalt())
    try:
        c.execute("INSERT INTO users (username, email, password, is_admin) VALUES (?, ?, ?, ?)",
                  ("admin", "admin@smartinvestor.com", admin_password, 1))
    except sqlite3.IntegrityError:
        pass
    
    conn.commit()
    conn.close()

# 사용자 인증 함수
def authenticate_user(email, password):
    conn = sqlite3.connect('smartinvestor.db')
    c = conn.cursor()
    c.execute("SELECT id, username, password, is_admin FROM users WHERE email = ?", (email,))
    user = c.fetchone()
    conn.close()
    
    if user and bcrypt.checkpw(password.encode('utf-8'), user[2]):
        return {"id": user[0], "username": user[1], "is_admin": user[3]}
    return None

def register_user(username, email, password):
    conn = sqlite3.connect('smartinvestor.db')
    c = conn.cursor()
    
    hashed_password = bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt())
    
    try:
        c.execute("INSERT INTO users (username, email, password) VALUES (?, ?, ?)",
                  (username, email, hashed_password))
        conn.commit()
        conn.close()
        return True
    except sqlite3.IntegrityError:
        conn.close()
        return False

# 암호화폐 온체인 데이터 가져오기
def get_crypto_onchain_data(symbol):
    """암호화폐 온체인 데이터 시뮬레이션"""
    try:
        # CoinGecko API (무료)
        crypto_map = {
            'BTC-USD': 'bitcoin',
            'ETH-USD': 'ethereum',
            'BNB-USD': 'binancecoin',
            'SOL-USD': 'solana',
            'ADA-USD': 'cardano',
            'DOGE-USD': 'dogecoin',
            'MATIC-USD': 'matic-network'
        }
        
        crypto_id = crypto_map.get(symbol, 'bitcoin')
        
        # CoinGecko API 호출
        url = f"https://api.coingecko.com/api/v3/coins/{crypto_id}"
        response = requests.get(url)
        
        if response.status_code == 200:
            data = response.json()
            
            onchain_data = {
                'market_cap': data.get('market_data', {}).get('market_cap', {}).get('usd', 0),
                'total_volume': data.get('market_data', {}).get('total_volume', {}).get('usd', 0),
                'circulating_supply': data.get('market_data', {}).get('circulating_supply', 0),
                'price_change_24h': data.get('market_data', {}).get('price_change_percentage_24h', 0),
                'ath': data.get('market_data', {}).get('ath', {}).get('usd', 0),
                'ath_change_percentage': data.get('market_data', {}).get('ath_change_percentage', {}).get('usd', 0),
                'sentiment_votes_up_percentage': data.get('sentiment_votes_up_percentage', 50),
                'developer_score': data.get('developer_score', 0),
                'community_score': data.get('community_score', 0)
            }
            
            return onchain_data
        else:
            return None
            
    except Exception as e:
        st.error(f"온체인 데이터 로딩 오류: {str(e)}")
        return None

# 번역 함수 (대체 구현)
def translate_to_korean(text):
    # 번역 기능 비활성화 (의존성 충돌로 인해)
    return text

# AI 뉴스 분석 함수
def analyze_news_with_ai(news_title, news_summary):
    if not AI_ENABLED:
        return "AI 분석 사용 불가"
    
    try:
        prompt = f"""
        다음 뉴스를 분석하고 투자자 관점에서 간단한 인사이트를 제공해주세요:
        
        제목: {news_title}
        내용: {news_summary}
        
        50자 이내로 핵심만 요약해주세요.
        """
        
        if client:  # 새로운 API 방식
            response = client.chat.completions.create(
                model="gpt-3.5-turbo",
                messages=[{"role": "user", "content": prompt}],
                max_tokens=100
            )
            return response.choices[0].message.content
        else:  # 구버전 API 방식
            response = openai.ChatCompletion.create(
                model="gpt-3.5-turbo",
                messages=[{"role": "user", "content": prompt}],
                max_tokens=100
            )
            return response.choices[0].message.content
    except:
        return "AI 분석 실패"

# 기술적 지표 계산 함수
def calculate_technical_indicators(df):
    try:
        # 데이터 복사본 생성
        df = df.copy()
        
        # RSI
        df['RSI'] = ta.momentum.RSIIndicator(df['Close'], window=14).rsi()
        
        # MACD
        macd = ta.trend.MACD(df['Close'])
        df['MACD'] = macd.macd()
        df['MACD_signal'] = macd.macd_signal()
        df['MACD_diff'] = macd.macd_diff()
        
        # Bollinger Bands
        bb = ta.volatility.BollingerBands(df['Close'], window=20)
        df['BB_upper'] = bb.bollinger_hband()
        df['BB_middle'] = bb.bollinger_mavg()
        df['BB_lower'] = bb.bollinger_lband()
        
        # Stochastic RSI
        stoch_rsi = ta.momentum.StochRSIIndicator(df['Close'])
        df['StochRSI'] = stoch_rsi.stochrsi()
        
        # CCI
        df['CCI'] = ta.trend.CCIIndicator(df['High'], df['Low'], df['Close']).cci()
        
        # MFI
        df['MFI'] = ta.volume.MFIIndicator(df['High'], df['Low'], df['Close'], df['Volume']).money_flow_index()
        
        # NaN 값 처리
        df = df.fillna(method='bfill').fillna(method='ffill')
        
        return df
    except Exception as e:
        st.error(f"기술적 지표 계산 중 오류: {str(e)}")
        return df

# 매수 신호 점수 계산
def calculate_buy_score(df):
    try:
        if len(df) < 2:
            return 0, []
            
        latest = df.iloc[-1]
        score = 0
        signals = []
        
        # RSI 과매도 (30 이하)
        if pd.notna(latest['RSI']) and latest['RSI'] < 30:
            score += 1
            signals.append("RSI 과매도 신호")
        
        # MACD 골든크로스
        if (pd.notna(latest['MACD']) and pd.notna(latest['MACD_signal']) and 
            pd.notna(df.iloc[-2]['MACD']) and pd.notna(df.iloc[-2]['MACD_signal'])):
            if latest['MACD'] > latest['MACD_signal'] and df.iloc[-2]['MACD'] <= df.iloc[-2]['MACD_signal']:
                score += 1
                signals.append("MACD 골든크로스")
        
        # 볼린저 밴드 하단 터치
        if pd.notna(latest['Close']) and pd.notna(latest['BB_lower']):
            if latest['Close'] <= latest['BB_lower']:
                score += 1
                signals.append("볼린저 밴드 하단 터치")
        
        # CCI 과매도
        if pd.notna(latest['CCI']) and latest['CCI'] < -100:
            score += 1
            signals.append("CCI 과매도 신호")
        
        # MFI 과매도
        if pd.notna(latest['MFI']) and latest['MFI'] < 20:
            score += 1
            signals.append("MFI 과매도 신호")
        
        return score, signals
    except Exception as e:
        return 0, []

# AI 분석 함수
def get_ai_analysis(symbol, technical_data, asset_type='stock', onchain_data=None):
    if not AI_ENABLED:
        return "AI 분석을 사용하려면 OpenAI API 키가 필요합니다."
    
    try:
        if asset_type == 'crypto' and onchain_data:
            prompt = f"""
            {symbol} 암호화폐의 기술적 지표와 온체인 데이터를 분석해주세요:
            
            기술적 지표:
            - 현재가: ${technical_data['Close']:.2f}
            - RSI: {technical_data['RSI']:.2f}
            - MACD: {technical_data['MACD']:.2f}
            
            온체인 데이터:
            - 시가총액: ${onchain_data['market_cap']:,.0f}
            - 24시간 거래량: ${onchain_data['total_volume']:,.0f}
            - 24시간 가격 변동: {onchain_data['price_change_24h']:.2f}%
            - ATH 대비: {onchain_data['ath_change_percentage']:.2f}%
            - 커뮤니티 점수: {onchain_data['community_score']:.1f}
            
            간단한 투자 의견을 한국어로 제공해주세요.
            """
        else:
            prompt = f"""
            {symbol} {'ETF' if asset_type == 'etf' else '주식'}의 기술적 지표를 분석해주세요:
            - 현재가: ${technical_data['Close']:.2f}
            - RSI: {technical_data['RSI']:.2f}
            - MACD: {technical_data['MACD']:.2f}
            - CCI: {technical_data['CCI']:.2f}
            - MFI: {technical_data['MFI']:.2f}
            
            간단한 투자 의견을 한국어로 제공해주세요.
            """
        
        if client:  # 새로운 API 방식
            response = client.chat.completions.create(
                model="gpt-3.5-turbo",
                messages=[
                    {"role": "system", "content": "당신은 전문 투자 분석가입니다."},
                    {"role": "user", "content": prompt}
                ],
                max_tokens=300
            )
            return response.choices[0].message.content
        else:  # 구버전 API 방식
            response = openai.ChatCompletion.create(
                model="gpt-3.5-turbo",
                messages=[
                    {"role": "system", "content": "당신은 전문 투자 분석가입니다."},
                    {"role": "user", "content": prompt}
                ],
                max_tokens=300
            )
            return response.choices[0].message.content
            
    except Exception as e:
        return f"AI 분석 중 오류: {str(e)}"

# PDF 리포트 생성 함수
def generate_pdf_report(symbol, data, score, signals, user_name, asset_type='stock'):
    pdf = FPDF()
    pdf.add_page()
    pdf.set_font("Arial", size=12)
    
    # 제목
    pdf.set_font("Arial", "B", 20)
    pdf.cell(0, 10, f"SmartInvestor Pro - {symbol} Analysis Report", ln=True, align="C")
    pdf.ln(10)
    
    # 날짜와 사용자
    pdf.set_font("Arial", size=12)
    pdf.cell(0, 10, f"Date: {datetime.now().strftime('%Y-%m-%d %H:%M')}", ln=True)
    pdf.cell(0, 10, f"Analyst: {user_name}", ln=True)
    pdf.cell(0, 10, f"Asset Type: {asset_type.upper()}", ln=True)
    pdf.ln(10)
    
    # 종목 정보
    pdf.set_font("Arial", "B", 14)
    pdf.cell(0, 10, f"{asset_type.upper()} Information", ln=True)
    pdf.set_font("Arial", size=12)
    latest = data.iloc[-1]
    pdf.cell(0, 10, f"Current Price: ${latest['Close']:.2f}", ln=True)
    pdf.cell(0, 10, f"Volume: {latest['Volume']:,}", ln=True)
    pdf.ln(5)
    
    # 기술적 지표
    pdf.set_font("Arial", "B", 14)
    pdf.cell(0, 10, "Technical Indicators", ln=True)
    pdf.set_font("Arial", size=12)
    pdf.cell(0, 10, f"RSI: {latest['RSI']:.2f}", ln=True)
    pdf.cell(0, 10, f"MACD: {latest['MACD']:.2f}", ln=True)
    pdf.cell(0, 10, f"CCI: {latest['CCI']:.2f}", ln=True)
    pdf.cell(0, 10, f"MFI: {latest['MFI']:.2f}", ln=True)
    pdf.ln(5)
    
    # 투자 추천
    pdf.set_font("Arial", "B", 14)
    pdf.cell(0, 10, "Investment Recommendation", ln=True)
    pdf.set_font("Arial", size=12)
    pdf.cell(0, 10, f"Buy Score: {score}/5", ln=True)
    
    if score >= 3:
        pdf.set_text_color(0, 128, 0)
        pdf.cell(0, 10, "Recommendation: BUY", ln=True)
    else:
        pdf.set_text_color(255, 0, 0)
        pdf.cell(0, 10, "Recommendation: HOLD/WAIT", ln=True)
    
    pdf.set_text_color(0, 0, 0)
    pdf.ln(5)
    
    # 신호 목록
    pdf.set_font("Arial", "B", 14)
    pdf.cell(0, 10, "Active Signals", ln=True)
    pdf.set_font("Arial", size=12)
    for signal in signals:
        pdf.cell(0, 10, f"- {signal}", ln=True)
    
    return pdf.output(dest='S').encode('latin-1')

# 메인 앱
def main():
    init_database()
    
    # 세션 상태 초기화
    if 'logged_in' not in st.session_state:
        st.session_state.logged_in = False
    if 'user' not in st.session_state:
        st.session_state.user = None
    
    # 로그인/회원가입 화면
    if not st.session_state.logged_in:
        st.markdown("<h1 class='main-header'>🚀 SmartInvestor Pro</h1>", unsafe_allow_html=True)
        st.markdown("<p style='text-align: center; font-size: 1.2em;'>AI 기반 스마트 투자 분석 플랫폼</p>", unsafe_allow_html=True)
        
        col1, col2, col3 = st.columns([1, 2, 1])
        
        with col2:
            tab1, tab2 = st.tabs(["로그인", "회원가입"])
            
            with tab1:
                with st.form("login_form"):
                    email = st.text_input("이메일", value="admin@smartinvestor.com")
                    password = st.text_input("비밀번호", type="password", value="admin123")
                    st.caption("데모: admin@smartinvestor.com / admin123")
                    submitted = st.form_submit_button("로그인", use_container_width=True)
                    
                    if submitted:
                        user = authenticate_user(email, password)
                        if user:
                            st.session_state.logged_in = True
                            st.session_state.user = user
                            st.success("로그인 성공!")
                            st.rerun()
                        else:
                            st.error("이메일 또는 비밀번호가 잘못되었습니다.")
            
            with tab2:
                with st.form("register_form"):
                    new_username = st.text_input("사용자명")
                    new_email = st.text_input("이메일")
                    new_password = st.text_input("비밀번호", type="password")
                    new_password_confirm = st.text_input("비밀번호 확인", type="password")
                    submitted = st.form_submit_button("회원가입", use_container_width=True)
                    
                    if submitted:
                        if new_password != new_password_confirm:
                            st.error("비밀번호가 일치하지 않습니다.")
                        elif len(new_password) < 6:
                            st.error("비밀번호는 최소 6자 이상이어야 합니다.")
                        else:
                            if register_user(new_username, new_email, new_password):
                                st.success("회원가입 성공! 로그인해주세요.")
                            else:
                                st.error("이미 존재하는 사용자명 또는 이메일입니다.")
    
    # 메인 앱 화면
    else:
        # 사이드바
        with st.sidebar:
            st.markdown(f"### 👋 환영합니다, {st.session_state.user['username']}님!")
            
            # 메뉴 옵션
            menu_options = ["홈", "실시간 분석", "포트폴리오", "뉴스", "설정"]
            menu_icons = ["house", "graph-up", "wallet2", "newspaper", "gear"]
            
            # AI 기능이 활성화된 경우 메뉴 추가
            if AI_ENABLED:
                menu_options.insert(2, "AI 분석")
                menu_icons.insert(2, "robot")
            
            selected = option_menu(
                menu_title="메뉴",
                options=menu_options,
                icons=menu_icons,
                menu_icon="cast",
                default_index=0
            )
            
            if st.button("로그아웃", use_container_width=True):
                st.session_state.logged_in = False
                st.session_state.user = None
                st.rerun()
        
        # 홈 화면
        if selected == "홈":
            st.markdown("<h1 class='main-header'>📈 SmartInvestor Pro Dashboard</h1>", unsafe_allow_html=True)
            
            # 자산 유형 선택
            asset_tabs = st.tabs(["📈 주식", "💼 ETF", "🪙 암호화폐"])
            
            with asset_tabs[0]:  # 주식
                # 주요 지표
                col1, col2, col3, col4 = st.columns(4)
                
                # 기본 주식 심볼 리스트
                DEFAULT_STOCKS = ['AAPL', 'MSFT', 'GOOGL', 'TSLA', 'AMZN']
                stock_recommendations = []
                
                with st.spinner("주식 추천 종목을 분석 중입니다..."):
                    for symbol in DEFAULT_STOCKS:
                        try:
                            stock = yf.Ticker(symbol)
                            hist = stock.history(period="1mo")
                            if not hist.empty and len(hist) >= 20:
                                hist = calculate_technical_indicators(hist)
                                score, signals = calculate_buy_score(hist)
                                if score >= 3:
                                    stock_recommendations.append({
                                        'symbol': symbol,
                                        'score': score,
                                        'price': hist.iloc[-1]['Close'],
                                        'signals': signals
                                    })
                        except Exception as e:
                            continue
                
                with col1:
                    st.metric("추천 종목 수", len(stock_recommendations), f"총 {len(DEFAULT_STOCKS)}개 분석")
                
                with col2:
                    st.metric("분석 종목 수", len(DEFAULT_STOCKS))
                
                with col3:
                    avg_score = np.mean([r['score'] for r in stock_recommendations]) if stock_recommendations else 0
                    st.metric("평균 매수 점수", f"{avg_score:.1f}/5.0")
                
                with col4:
                    st.metric("마지막 업데이트", datetime.now().strftime("%H:%M"))
                
                # 추천 종목 리스트
                st.markdown("### 🎯 오늘의 추천 주식")
                
                if stock_recommendations:
                    for rec in sorted(stock_recommendations, key=lambda x: x['score'], reverse=True):
                        with st.container():
                            col1, col2, col3 = st.columns([2, 1, 3])
                            with col1:
                                st.markdown(f"### {rec['symbol']}")
                                st.caption(f"현재가: ${rec['price']:.2f}")
                            with col2:
                                st.metric("매수 점수", f"{rec['score']}/5")
                            with col3:
                                st.info(f"신호: {', '.join(rec['signals'])}")
                else:
                    st.info("현재 추천 조건을 만족하는 종목이 없습니다.")
            
            with asset_tabs[1]:  # ETF
                # ETF 리스트
                DEFAULT_ETFS = ['SPY', 'QQQ', 'IWM', 'DIA', 'VTI', 'VOO', 'ARKK', 'XLF']
                etf_data = []
                
                st.markdown("### 📊 주요 ETF 현황")
                
                with st.spinner("ETF 데이터를 로딩 중입니다..."):
                    for symbol in DEFAULT_ETFS:
                        try:
                            etf = yf.Ticker(symbol)
                            hist = etf.history(period="5d")
                            if not hist.empty:
                                current_price = hist['Close'].iloc[-1]
                                prev_price = hist['Close'].iloc[0]
                                change = ((current_price - prev_price) / prev_price) * 100
                                
                                etf_data.append({
                                    'Symbol': symbol,
                                    'Price': f"${current_price:.2f}",
                                    'Change': f"{change:.2f}%",
                                    'Volume': f"{hist['Volume'].iloc[-1]:,.0f}"
                                })
                        except:
                            continue
                
                if etf_data:
                    df_etf = pd.DataFrame(etf_data)
                    st.dataframe(df_etf, use_container_width=True)
                else:
                    st.error("ETF 데이터를 불러올 수 없습니다.")
            
            with asset_tabs[2]:  # 암호화폐
                # 암호화폐 리스트
                DEFAULT_CRYPTO = ['BTC-USD', 'ETH-USD', 'BNB-USD', 'SOL-USD', 'ADA-USD']
                crypto_recommendations = []
                
                st.markdown("### 🪙 암호화폐 분석")
                
                with st.spinner("암호화폐 데이터를 분석 중입니다..."):
                    for symbol in DEFAULT_CRYPTO:
                        try:
                            crypto = yf.Ticker(symbol)
                            hist = crypto.history(period="1mo")
                            
                            if not hist.empty and len(hist) >= 20:
                                hist = calculate_technical_indicators(hist)
                                score, signals = calculate_buy_score(hist)
                                
                                # 온체인 데이터 가져오기
                                onchain = get_crypto_onchain_data(symbol)
                                
                                crypto_recommendations.append({
                                    'symbol': symbol.replace('-USD', ''),
                                    'score': score,
                                    'price': hist.iloc[-1]['Close'],
                                    'signals': signals,
                                    'onchain': onchain
                                })
                        except:
                            continue
                
                # 암호화폐 추천 표시
                for crypto in crypto_recommendations:
                    with st.expander(f"{crypto['symbol']} - 점수: {crypto['score']}/5"):
                        col1, col2 = st.columns(2)
                        
                        with col1:
                            st.metric("현재가", f"${crypto['price']:.2f}")
                            if crypto['onchain']:
                                st.metric("24시간 변동", f"{crypto['onchain']['price_change_24h']:.2f}%")
                                st.metric("시가총액", f"${crypto['onchain']['market_cap']:,.0f}")
                        
                        with col2:
                            st.write("**활성 신호:**")
                            for signal in crypto['signals']:
                                st.write(f"- {signal}")
                            
                            if crypto['onchain']:
                                st.write(f"**커뮤니티 점수:** {crypto['onchain']['community_score']:.1f}")
                                st.write(f"**ATH 대비:** {crypto['onchain']['ath_change_percentage']:.1f}%")
            
            # 시장 히트맵 링크
            st.markdown("### 🗺️ 시장 히트맵")
            col1, col2, col3 = st.columns(3)
            
            with col1:
                if st.button("📊 주식 히트맵", use_container_width=True):
                    st.markdown('<a href="https://finviz.com/map.ashx" target="_blank">Finviz 주식 히트맵 보기</a>', unsafe_allow_html=True)
            
            with col2:
                if st.button("🪙 암호화폐 히트맵", use_container_width=True):
                    st.markdown('<a href="https://coin360.com/" target="_blank">Coin360 암호화폐 히트맵 보기</a>', unsafe_allow_html=True)
            
            with col3:
                if st.button("🌍 글로벌 시장", use_container_width=True):
                    st.markdown('<a href="https://www.tradingview.com/markets/" target="_blank">TradingView 글로벌 시장 보기</a>', unsafe_allow_html=True)
        
        # 실시간 분석
        elif selected == "실시간 분석":
            st.markdown("<h1 class='main-header'>🔍 실시간 종목 분석</h1>", unsafe_allow_html=True)
            
            # 자산 유형 선택
            col1, col2, col3 = st.columns([2, 1, 1])
            
            with col1:
                symbol = st.text_input("종목 심볼 입력", "AAPL").upper().strip()
            
            with col2:
                asset_type = st.selectbox("자산 유형", ["주식", "ETF", "암호화폐"])
            
            with col3:
                period = st.selectbox("기간", ["1mo", "3mo", "6mo", "1y", "2y"])
            
            # 암호화폐인 경우 심볼 조정
            if asset_type == "암호화폐" and not symbol.endswith('-USD'):
                symbol = symbol + '-USD'
            
            if st.button("분석 시작", use_container_width=True, type="primary"):
                if not symbol:
                    st.error("종목 심볼을 입력해주세요.")
                else:
                    with st.spinner(f"{symbol} 데이터를 분석 중입니다..."):
                        try:
                            # 데이터 가져오기
                            ticker = yf.Ticker(symbol)
                            hist = ticker.history(period=period)
                            
                            # 데이터 유효성 검사
                            if hist.empty or len(hist) < 20:
                                st.error(f"'{symbol}'에 대한 데이터를 가져올 수 없습니다.")
                                st.info("팁: 주식/ETF는 미국 심볼, 암호화폐는 BTC, ETH 등을 사용하세요.")
                            else:
                                # 기술적 지표 계산
                                hist = calculate_technical_indicators(hist)
                                
                                # 탭 생성
                                tab1, tab2, tab3 = st.tabs(["📊 차트", "📈 기술적 지표", "📄 리포트"])
                                
                                with tab1:
                                    # 차트 표시
                                    fig = go.Figure()
                                    
                                    # 캔들스틱 차트
                                    fig.add_trace(go.Candlestick(
                                        x=hist.index,
                                        open=hist['Open'],
                                        high=hist['High'],
                                        low=hist['Low'],
                                        close=hist['Close'],
                                        name='Price'
                                    ))
                                    
                                    # 볼린저 밴드
                                    fig.add_trace(go.Scatter(
                                        x=hist.index,
                                        y=hist['BB_upper'],
                                        name='BB Upper',
                                        line=dict(color='rgba(250, 128, 114, 0.5)')
                                    ))
                                    
                                    fig.add_trace(go.Scatter(
                                        x=hist.index,
                                        y=hist['BB_lower'],
                                        name='BB Lower',
                                        line=dict(color='rgba(250, 128, 114, 0.5)'),
                                        fill='tonexty'
                                    ))
                                    
                                    fig.update_layout(
                                        title=f"{symbol} 주가 차트",
                                        xaxis_title="날짜",
                                        yaxis_title="가격 ($)",
                                        height=500,
                                        template="plotly_white"
                                    )
                                    
                                    st.plotly_chart(fig, use_container_width=True)
                                
                                with tab2:
                                    # 지표 차트
                                    col1, col2 = st.columns(2)
                                    
                                    with col1:
                                        # RSI 차트
                                        fig_rsi = go.Figure()
                                        fig_rsi.add_trace(go.Scatter(
                                            x=hist.index,
                                            y=hist['RSI'],
                                            name='RSI',
                                            line=dict(color='blue')
                                        ))
                                        fig_rsi.add_hline(y=70, line_dash="dash", line_color="red", annotation_text="과매수")
                                        fig_rsi.add_hline(y=30, line_dash="dash", line_color="green", annotation_text="과매도")
                                        fig_rsi.update_layout(title="RSI", height=300, yaxis=dict(range=[0, 100]))
                                        st.plotly_chart(fig_rsi, use_container_width=True)
                                    
                                    with col2:
                                        # MACD 차트
                                        fig_macd = go.Figure()
                                        
                                        # MACD 선
                                        fig_macd.add_trace(go.Scatter(
                                            x=hist.index,
                                            y=hist['MACD'],
                                            name='MACD',
                                            line=dict(color='blue', width=2)
                                        ))
                                        
                                        # Signal 선
                                        fig_macd.add_trace(go.Scatter(
                                            x=hist.index,
                                            y=hist['MACD_signal'],
                                            name='Signal',
                                            line=dict(color='red', width=2)
                                        ))
                                        
                                        # MACD 히스토그램
                                        colors = ['green' if val >= 0 else 'red' for val in hist['MACD_diff']]
                                        fig_macd.add_trace(go.Bar(
                                            x=hist.index,
                                            y=hist['MACD_diff'],
                                            name='MACD Diff',
                                            marker_color=colors
                                        ))
                                        
                                        fig_macd.update_layout(
                                            title="MACD",
                                            height=300,
                                            showlegend=True
                                        )
                                        st.plotly_chart(fig_macd, use_container_width=True)
                                    
                                    # 현재 지표 값
                                    st.markdown("### 현재 기술적 지표")
                                    latest = hist.iloc[-1]
                                    
                                    col1, col2, col3, col4 = st.columns(4)
                                    with col1:
                                        rsi_val = latest['RSI']
                                        if pd.notna(rsi_val):
                                            st.metric("RSI", f"{rsi_val:.2f}")
                                        else:
                                            st.metric("RSI", "N/A")
                                    
                                    with col2:
                                        cci_val = latest['CCI']
                                        if pd.notna(cci_val):
                                            st.metric("CCI", f"{cci_val:.2f}")
                                        else:
                                            st.metric("CCI", "N/A")
                                    
                                    with col3:
                                        mfi_val = latest['MFI']
                                        if pd.notna(mfi_val):
                                            st.metric("MFI", f"{mfi_val:.2f}")
                                        else:
                                            st.metric("MFI", "N/A")
                                    
                                    with col4:
                                        stoch_val = latest['StochRSI']
                                        if pd.notna(stoch_val):
                                            st.metric("StochRSI", f"{stoch_val:.2f}")
                                        else:
                                            st.metric("StochRSI", "N/A")
                                
                                with tab3:
                                    # 매수 신호 분석
                                    score, signals = calculate_buy_score(hist)
                                    
                                    st.markdown("### 📊 분석 결과")
                                    
                                    col1, col2, col3 = st.columns(3)
                                    
                                    with col1:
                                        st.metric("매수 점수", f"{score}/5")
                                    
                                    with col2:
                                        latest_price = hist.iloc[-1]['Close']
                                        st.metric("현재가", f"${latest_price:.2f}")
                                    
                                    with col3:
                                        recommendation = "매수" if score >= 3 else "관망"
                                        st.metric("투자 추천", recommendation)
                                    
                                    # 신호 상세
                                    if signals:
                                        st.markdown("#### 🚦 활성화된 매수 신호")
                                        for signal in signals:
                                            st.success(f"✅ {signal}")
                                    else:
                                        st.info("현재 활성화된 매수 신호가 없습니다.")
                                    
                                    # PDF 리포트 생성
                                    if st.button("📄 PDF 리포트 생성"):
                                        pdf_data = generate_pdf_report(
                                            symbol, 
                                            hist, 
                                            score, 
                                            signals, 
                                            st.session_state.user['username'],
                                            asset_type.lower()
                                        )
                                        st.download_button(
                                            label="📥 리포트 다운로드",
                                            data=pdf_data,
                                            file_name=f"{symbol}_analysis_{datetime.now().strftime('%Y%m%d')}.pdf",
                                            mime="application/pdf"
                                        )
                                    
                                    # AI 분석 (선택적)
                                    if AI_ENABLED and st.button("🤖 AI 분석 실행"):
                                        with st.spinner("AI가 분석 중입니다..."):
                                            onchain_data = None
                                            if asset_type == "암호화폐":
                                                onchain_data = get_crypto_onchain_data(symbol)
                                            
                                            ai_analysis = get_ai_analysis(
                                                symbol, 
                                                latest, 
                                                asset_type.lower(),
                                                onchain_data
                                            )
                                            st.markdown("### 🤖 AI 분석 결과")
                                            st.info(ai_analysis)
                                
                                # 분석 기록 저장
                                conn = sqlite3.connect('smartinvestor.db')
                                c = conn.cursor()
                                c.execute("""INSERT INTO analysis_history 
                                            (user_id, symbol, asset_type, score, recommendation) 
                                            VALUES (?, ?, ?, ?, ?)""",
                                         (st.session_state.user['id'], symbol, asset_type.lower(), score, recommendation))
                                conn.commit()
                                conn.close()
                                
                        except Exception as e:
                            st.error(f"오류가 발생했습니다: {str(e)}")
                            st.info("다시 시도하거나 다른 종목을 검색해보세요.")
        
        # AI 분석 (선택적) - 별도 페이지로 분리
        elif selected == "AI 분석" and AI_ENABLED:
            st.markdown("<h1 class='main-header'>🤖 AI 기반 심층 분석</h1>", unsafe_allow_html=True)
            
            col1, col2 = st.columns([2, 1])
            
            with col1:
                symbol = st.text_input("분석할 종목 심볼", "AAPL").upper().strip()
            
            with col2:
                asset_type = st.selectbox("자산 유형", ["주식", "ETF", "암호화폐"])
            
            # 암호화폐인 경우 심볼 조정
            if asset_type == "암호화폐" and not symbol.endswith('-USD'):
                symbol = symbol + '-USD'
            
            if st.button("AI 분석 시작", use_container_width=True, type="primary"):
                if not symbol:
                    st.error("종목 심볼을 입력해주세요.")
                else:
                    with st.spinner("AI가 종목을 분석 중입니다..."):
                        try:
                            ticker = yf.Ticker(symbol)
                            hist = ticker.history(period="3mo")
                            
                            if hist.empty:
                                st.error("데이터를 가져올 수 없습니다.")
                            else:
                                hist = calculate_technical_indicators(hist)
                                latest_data = hist.iloc[-1]
                                
                                # 온체인 데이터 (암호화폐인 경우)
                                onchain_data = None
                                if asset_type == "암호화폐":
                                    onchain_data = get_crypto_onchain_data(symbol)
                                
                                # AI 분석 실행
                                ai_analysis = get_ai_analysis(symbol, latest_data, asset_type.lower(), onchain_data)
                                
                                # 결과 표시
                                st.markdown("### 🎯 AI 분석 결과")
                                st.info(ai_analysis)
                                
                                # 주요 지표 시각화
                                st.markdown("### 📊 주요 기술적 지표")
                                
                                col1, col2, col3, col4 = st.columns(4)
                                
                                with col1:
                                    rsi_color = "🟢" if latest_data['RSI'] < 30 else "🟡" if latest_data['RSI'] < 70 else "🔴"
                                    st.metric("RSI", f"{latest_data['RSI']:.2f} {rsi_color}")
                                
                                with col2:
                                    macd_color = "🟢" if latest_data['MACD'] > latest_data['MACD_signal'] else "🔴"
                                    st.metric("MACD", f"{latest_data['MACD']:.2f} {macd_color}")
                                
                                with col3:
                                    st.metric("CCI", f"{latest_data['CCI']:.2f}")
                                
                                with col4:
                                    st.metric("MFI", f"{latest_data['MFI']:.2f}")
                                
                                # 온체인 데이터 표시 (암호화폐)
                                if asset_type == "암호화폐" and onchain_data:
                                    st.markdown("### 🔗 온체인 데이터")
                                    
                                    col1, col2, col3 = st.columns(3)
                                    
                                    with col1:
                                        st.metric("시가총액", f"${onchain_data['market_cap']:,.0f}")
                                        st.metric("24시간 거래량", f"${onchain_data['total_volume']:,.0f}")
                                    
                                    with col2:
                                        st.metric("24시간 변동", f"{onchain_data['price_change_24h']:.2f}%")
                                        st.metric("ATH 대비", f"{onchain_data['ath_change_percentage']:.2f}%")
                                    
                                    with col3:
                                        st.metric("커뮤니티 점수", f"{onchain_data['community_score']:.1f}")
                                        st.metric("개발자 점수", f"{onchain_data['developer_score']:.1f}")
                                
                        except Exception as e:
                            st.error(f"AI 분석 중 오류 발생: {str(e)}")
        
        # 포트폴리오
        elif selected == "포트폴리오":
            st.markdown("<h1 class='main-header'>💼 내 포트폴리오</h1>", unsafe_allow_html=True)
            
            # 분석 기록 조회
            conn = sqlite3.connect('smartinvestor.db')
            history_df = pd.read_sql_query("""
                SELECT symbol, asset_type, analysis_date, score, recommendation 
                FROM analysis_history 
                WHERE user_id = ? 
                ORDER BY analysis_date DESC 
                LIMIT 50
            """, conn, params=(st.session_state.user['id'],))
            conn.close()
            
            if not history_df.empty:
                # 분석 통계
                st.markdown("### 📊 분석 통계")
                col1, col2, col3, col4 = st.columns(4)
                
                with col1:
                    total_analyses = len(history_df)
                    st.metric("총 분석 횟수", total_analyses)
                
                with col2:
                    avg_score = history_df['score'].mean()
                    st.metric("평균 매수 점수", f"{avg_score:.2f}")
                
                with col3:
                    buy_recommendations = len(history_df[history_df['recommendation'] == '매수'])
                    st.metric("매수 추천", buy_recommendations)
                
                with col4:
                    hold_recommendations = len(history_df[history_df['recommendation'] == '관망'])
                    st.metric("관망 추천", hold_recommendations)
                
                # 자산 유형별 탭
                asset_tabs = st.tabs(["전체", "주식", "ETF", "암호화폐"])
                
                with asset_tabs[0]:
                    st.dataframe(history_df, use_container_width=True)
                
                with asset_tabs[1]:
                    stock_df = history_df[history_df['asset_type'] == 'stock']
                    if not stock_df.empty:
                        st.dataframe(stock_df, use_container_width=True)
                    else:
                        st.info("주식 분석 기록이 없습니다.")
                
                with asset_tabs[2]:
                    etf_df = history_df[history_df['asset_type'] == 'etf']
                    if not etf_df.empty:
                        st.dataframe(etf_df, use_container_width=True)
                    else:
                        st.info("ETF 분석 기록이 없습니다.")
                
                with asset_tabs[3]:
                    crypto_df = history_df[history_df['asset_type'] == '암호화폐']
                    if not crypto_df.empty:
                        st.dataframe(crypto_df, use_container_width=True)
                    else:
                        st.info("암호화폐 분석 기록이 없습니다.")
                
                # 포트폴리오 차트
                st.markdown("### 📊 분석 종목 분포")
                
                col1, col2 = st.columns(2)
                
                with col1:
                    # 자산 유형별 분포
                    asset_counts = history_df['asset_type'].value_counts()
                    
                    fig_asset = go.Figure(data=[go.Pie(
                        labels=asset_counts.index,
                        values=asset_counts.values,
                        hole=.3
                    )])
                    
                    fig_asset.update_layout(
                        title="자산 유형별 분포",
                        height=400
                    )
                    
                    st.plotly_chart(fig_asset, use_container_width=True)
                
                with col2:
                    # 종목별 분포
                    symbol_counts = history_df['symbol'].value_counts().head(10)
                    
                    fig_symbol = go.Figure(data=[go.Bar(
                        x=symbol_counts.index,
                        y=symbol_counts.values
                    )])
                    
                    fig_symbol.update_layout(
                        title="Top 10 분석 종목",
                        height=400
                    )
                    
                    st.plotly_chart(fig_symbol, use_container_width=True)
                
            else:
                st.info("아직 분석 기록이 없습니다. 실시간 분석을 시작해보세요!")
        
        # 뉴스
        elif selected == "뉴스":
            st.markdown("<h1 class='main-header'>📰 투자 뉴스</h1>", unsafe_allow_html=True)
            
            # 뉴스 소스 선택
            news_source = st.selectbox(
                "뉴스 소스 선택",
                ["Yahoo Finance", "Investing.com", "CNBC", "Bloomberg"]
            )
            
            feed_urls = {
                "Yahoo Finance": "https://finance.yahoo.com/news/rssindex",
                "Investing.com": "https://www.investing.com/rss/news.rss",
                "CNBC": "https://www.cnbc.com/id/100003114/device/rss/rss.html",
                "Bloomberg": "https://feeds.bloomberg.com/markets/news.rss"
            }
            
            try:
                feed = feedparser.parse(feed_urls[news_source])
                
                if feed.entries:
                    st.markdown(f"### 📰 {news_source} 최신 뉴스")
                    
                    for i, entry in enumerate(feed.entries[:10]):
                        with st.expander(f"📰 {entry.title[:80]}..."):
                            # 발행일
                            if hasattr(entry, 'published'):
                                st.caption(f"📅 {entry.published}")
                            
                            # 한국어 번역 (선택적 기능으로 변경)
                            # 현재는 비활성화됨 - 향후 다른 번역 API 사용 가능
                            
                            # 요약
                            if hasattr(entry, 'summary'):
                                summary = entry.summary[:500] + "..."
                                st.write(summary)
                                
                                # AI 분석 (있을 경우)
                                if AI_ENABLED and st.button(f"AI 분석", key=f"news_ai_{i}"):
                                    with st.spinner("AI가 뉴스를 분석 중..."):
                                        ai_insight = analyze_news_with_ai(entry.title, summary)
                                        st.info(f"**AI 인사이트:** {ai_insight}")
                            
                            # 원문 링크
                            st.markdown(f"[원문 보기]({entry.link})")
                else:
                    st.info("뉴스를 불러올 수 없습니다.")
                    
            except Exception as e:
                st.error(f"뉴스 로딩 중 오류 발생: {str(e)}")
        
        # 설정
        elif selected == "설정":
            st.markdown("<h1 class='main-header'>⚙️ 설정</h1>", unsafe_allow_html=True)
            
            # 사용자 정보
            st.markdown("### 👤 내 정보")
            col1, col2 = st.columns(2)
            
            with col1:
                st.info(f"**사용자명**: {st.session_state.user['username']}")
                st.info(f"**사용자 ID**: {st.session_state.user['id']}")
            
            with col2:
                if st.session_state.user.get('is_admin'):
                    st.success("✅ 관리자 권한 활성화")
                else:
                    st.info("일반 사용자")
            
            # 시스템 상태
            st.markdown("### 🔌 시스템 상태")
            
            col1, col2, col3, col4 = st.columns(4)
            
            with col1:
                try:
                    test_ticker = yf.Ticker("AAPL")
                    test_data = test_ticker.history(period="1d")
                    if not test_data.empty:
                        st.success("Yahoo Finance ✅")
                    else:
                        st.warning("Yahoo Finance ⚠️")
                except:
                    st.error("Yahoo Finance ❌")
            
            with col2:
                if AI_ENABLED:
                    st.success("OpenAI API ✅")
                else:
                    st.info("OpenAI API 🔧")
            
            with col3:
                st.info("번역 기능 🔧")
            
            with col4:
                st.success("Database ✅")
            
            # 사용 가이드
            st.markdown("### 📖 사용 가이드")
            
            with st.expander("🔍 실시간 분석 사용법"):
                st.markdown("""
                1. 종목 심볼을 입력합니다
                   - 주식/ETF: AAPL, MSFT, SPY, QQQ 등
                   - 암호화폐: BTC, ETH, BNB 등
                2. 자산 유형을 선택합니다
                3. 분석 기간을 선택합니다
                4. '분석 시작' 버튼을 클릭합니다
                5. 차트, 기술적 지표, 투자 신호를 확인합니다
                6. PDF 리포트를 다운로드할 수 있습니다
                """)
            
            with st.expander("📊 기술적 지표 설명"):
                st.markdown("""
                - **RSI (Relative Strength Index)**: 
                  - 30 이하: 과매도 (매수 고려)
                  - 70 이상: 과매수 (매도 고려)
                
                - **MACD**: 
                  - MACD선이 시그널선을 상향 돌파: 매수 신호
                  - MACD선이 시그널선을 하향 돌파: 매도 신호
                
                - **볼린저 밴드**: 
                  - 가격이 하단선 터치: 반등 가능성
                  - 가격이 상단선 터치: 조정 가능성
                
                - **CCI (Commodity Channel Index)**: 
                  - -100 이하: 과매도
                  - +100 이상: 과매수
                
                - **MFI (Money Flow Index)**: 
                  - 20 이하: 과매도
                  - 80 이상: 과매수
                """)
            
            with st.expander("💡 투자 점수 시스템"):
                st.markdown("""
                **매수 점수 계산 방식:**
                - RSI < 30: +1점
                - MACD 골든크로스: +1점
                - 볼린저 밴드 하단 터치: +1점
                - CCI < -100: +1점
                - MFI < 20: +1점
                
                **투자 추천:**
                - 3점 이상: 매수 추천
                - 2점 이하: 관망 추천
                
                **주의사항:**
                - 기술적 지표는 참고용입니다
                - 다양한 요인을 종합적으로 고려하세요
                - 리스크 관리를 항상 우선시하세요
                """)
            
            with st.expander("🪙 암호화폐 온체인 데이터"):
                st.markdown("""
                **온체인 데이터 설명:**
                - **시가총액**: 전체 코인의 시장 가치
                - **24시간 거래량**: 하루 거래 규모
                - **ATH 대비**: 역대 최고가 대비 현재 가격
                - **커뮤니티 점수**: 소셜 미디어 활동성
                - **개발자 점수**: 깃허브 활동성
                
                **활용 방법:**
                - 거래량 증가 + 가격 상승 = 강세 신호
                - ATH 대비 -80% 이상 = 저평가 가능성
                - 높은 개발자 점수 = 프로젝트 활성도 높음
                """)
            
            # 관리자 기능
            if st.session_state.user.get('is_admin'):
                st.markdown("### 🔐 관리자 기능")
                
                # 사용자 통계
                if st.checkbox("사용자 통계 보기"):
                    conn = sqlite3.connect('smartinvestor.db')
                    
                    # 전체 사용자 수
                    user_count = pd.read_sql_query("SELECT COUNT(*) as count FROM users", conn).iloc[0]['count']
                    st.metric("전체 사용자 수", user_count)
                    
                    # 사용자 목록
                    users_df = pd.read_sql_query(
                        "SELECT id, username, email, created_at, is_admin FROM users", 
                        conn
                    )
                    st.dataframe(users_df, use_container_width=True)
                    
                    # 분석 통계
                    analysis_stats = pd.read_sql_query("""
                        SELECT 
                            u.username,
                            COUNT(ah.id) as analysis_count,
                            AVG(ah.score) as avg_score,
                            COUNT(DISTINCT ah.symbol) as unique_symbols,
                            COUNT(DISTINCT ah.asset_type) as asset_types
                        FROM users u
                        LEFT JOIN analysis_history ah ON u.id = ah.user_id
                        GROUP BY u.username
                        ORDER BY analysis_count DESC
                    """, conn)
                    
                    st.markdown("#### 사용자별 분석 통계")
                    st.dataframe(analysis_stats, use_container_width=True)
                    
                    # 인기 종목 통계
                    popular_symbols = pd.read_sql_query("""
                        SELECT 
                            symbol,
                            asset_type,
                            COUNT(*) as analysis_count,
                            AVG(score) as avg_score,
                            SUM(CASE WHEN recommendation = '매수' THEN 1 ELSE 0 END) as buy_count,
                            SUM(CASE WHEN recommendation = '관망' THEN 1 ELSE 0 END) as hold_count
                        FROM analysis_history
                        GROUP BY symbol, asset_type
                        ORDER BY analysis_count DESC
                        LIMIT 20
                    """, conn)
                    
                    st.markdown("#### 인기 분석 종목 Top 20")
                    st.dataframe(popular_symbols, use_container_width=True)
                    
                    conn.close()

if __name__ == "__main__":
    main()