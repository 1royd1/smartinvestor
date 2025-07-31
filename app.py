import streamlit as st
import yfinance as yf
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import plotly.graph_objects as go
import ta
import sqlite3
import hashlib
import bcrypt
from fpdf import FPDF
import feedparser
import openai
import os
import requests
import json
from streamlit_option_menu import option_menu

# Alpha Vantage와 NewsAPI는 나중에 필요할 때만 import
try:
    from alpha_vantage.timeseries import TimeSeries
    from alpha_vantage.techindicators import TechIndicators
    ALPHA_VANTAGE_AVAILABLE = True
except ImportError:
    ALPHA_VANTAGE_AVAILABLE = False

try:
    from newsapi import NewsApiClient
    NEWSAPI_AVAILABLE = True
except ImportError:
    NEWSAPI_AVAILABLE = False

# 페이지 설정
st.set_page_config(
    page_title="SmartInvestor Pro",
    page_icon="📈",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Streamlit Secrets에서 API 키 가져오기
# API 키가 없어도 기본 기능은 작동하도록 처리
try:
    ALPHA_VANTAGE_API_KEY = st.secrets.get("ALPHA_VANTAGE_API_KEY", None)
    ALPHA_VANTAGE_BACKUP_KEY = st.secrets.get("ALPHA_VANTAGE_BACKUP_1", None)
    OPENAI_API_KEY = st.secrets.get("OPENAI_API_KEY", None)
    NEWSAPI_KEY = st.secrets.get("NEWSAPI_KEY", None)
    
    # OpenAI API 설정
    if OPENAI_API_KEY:
        openai.api_key = OPENAI_API_KEY
except Exception as e:
    st.warning("API 키를 Secrets에서 불러올 수 없습니다. 일부 기능이 제한될 수 있습니다.")
    ALPHA_VANTAGE_API_KEY = None
    ALPHA_VANTAGE_BACKUP_KEY = None
    OPENAI_API_KEY = None
    NEWSAPI_KEY = None

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
    
    # 분석 기록 테이블
    c.execute('''CREATE TABLE IF NOT EXISTS analysis_history
                 (id INTEGER PRIMARY KEY AUTOINCREMENT,
                  user_id INTEGER,
                  symbol TEXT,
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

# Alpha Vantage 데이터 가져오기 (API 키가 있을 때만)
def get_alpha_vantage_data(symbol, function='TIME_SERIES_DAILY'):
    if not ALPHA_VANTAGE_AVAILABLE or not ALPHA_VANTAGE_API_KEY:
        return None
        
    try:
        ts = TimeSeries(key=ALPHA_VANTAGE_API_KEY, output_format='pandas')
        if function == 'TIME_SERIES_DAILY':
            data, meta_data = ts.get_daily(symbol=symbol, outputsize='full')
            return data
        elif function == 'TIME_SERIES_INTRADAY':
            data, meta_data = ts.get_intraday(symbol=symbol, interval='5min', outputsize='full')
            return data
    except Exception as e:
        # 백업 키 사용
        if ALPHA_VANTAGE_BACKUP_KEY:
            try:
                ts = TimeSeries(key=ALPHA_VANTAGE_BACKUP_KEY, output_format='pandas')
                if function == 'TIME_SERIES_DAILY':
                    data, meta_data = ts.get_daily(symbol=symbol, outputsize='full')
                    return data
            except:
                pass
    return None

# NewsAPI를 사용한 뉴스 가져오기 (API 키가 있을 때만)
def get_stock_news(symbol):
    if not NEWSAPI_AVAILABLE or not NEWSAPI_KEY:
        return []
        
    try:
        newsapi = NewsApiClient(api_key=NEWSAPI_KEY)
        
        # 종목 관련 뉴스 검색
        all_articles = newsapi.get_everything(
            q=symbol,
            language='en',
            sort_by='relevancy',
            page_size=10,
            from_param=(datetime.now() - timedelta(days=7)).strftime('%Y-%m-%d')
        )
        
        return all_articles['articles']
    except Exception as e:
        return []

# AI 분석 함수 (OpenAI API 키가 있을 때만)
def get_ai_analysis(symbol, technical_data, news_data):
    if not OPENAI_API_KEY:
        return "AI 분석을 사용하려면 OpenAI API 키가 필요합니다."
        
    try:
        # 기술적 데이터 요약
        tech_summary = f"""
        Symbol: {symbol}
        Current Price: ${technical_data['Close']:.2f}
        RSI: {technical_data['RSI']:.2f}
        MACD: {technical_data['MACD']:.2f}
        Volume: {technical_data['Volume']:,}
        """
        
        # 뉴스 요약
        news_summary = "\n".join([f"- {article['title']}" for article in news_data[:5]])
        
        prompt = f"""
        As a professional financial analyst, analyze the following stock:
        
        Technical Analysis:
        {tech_summary}
        
        Recent News:
        {news_summary}
        
        Please provide:
        1. Overall investment recommendation (Buy/Hold/Sell)
        2. Key strengths and risks
        3. Price target for next 3 months
        4. Confidence level (1-10)
        
        Answer in Korean.
        """
        
        response = openai.ChatCompletion.create(
            model="gpt-3.5-turbo",
            messages=[
                {"role": "system", "content": "You are a professional stock analyst providing investment advice."},
                {"role": "user", "content": prompt}
            ],
            max_tokens=500,
            temperature=0.7
        )
        
        return response.choices[0].message.content
    except Exception as e:
        return f"AI 분석을 수행할 수 없습니다: {str(e)}"

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

# 기술적 지표 계산 함수
def calculate_technical_indicators(df):
    try:
        # 데이터 복사본 생성
        df = df.copy()
        
        # 컬럼명 표준화 (Alpha Vantage 데이터인 경우)
        if '1. open' in df.columns:
            df.rename(columns={
                '1. open': 'Open',
                '2. high': 'High',
                '3. low': 'Low',
                '4. close': 'Close',
                '5. volume': 'Volume'
            }, inplace=True)
        
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

# PDF 리포트 생성 함수
def generate_pdf_report(symbol, data, score, signals, user_name):
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
    pdf.ln(10)
    
    # 종목 정보
    pdf.set_font("Arial", "B", 14)
    pdf.cell(0, 10, "Stock Information", ln=True)
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
        st.markdown("<p style='text-align: center; font-size: 1.2em;'>AI & 실시간 데이터 기반 투자 분석 플랫폼</p>", unsafe_allow_html=True)
        
        col1, col2, col3 = st.columns([1, 2, 1])
        
        with col2:
            tab1, tab2 = st.tabs(["로그인", "회원가입"])
            
            with tab1:
                with st.form("login_form"):
                    email = st.text_input("이메일")
                    password = st.text_input("비밀번호", type="password")
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
            
            # AI 메뉴는 OpenAI API 키가 있을 때만 표시
            menu_options = ["홈", "실시간 분석", "포트폴리오", "뉴스", "설정"]
            menu_icons = ["house", "graph-up", "wallet2", "newspaper", "gear"]
            
            if OPENAI_API_KEY:
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
            
            # 주요 지표
            col1, col2, col3, col4 = st.columns(4)
            
            # 기본 심볼 리스트
            DEFAULT_SYMBOLS = ['AAPL', 'MSFT', 'GOOGL', 'TSLA', 'AMZN']
            recommendations = []
            
            with st.spinner("추천 종목을 분석 중입니다..."):
                for symbol in DEFAULT_SYMBOLS:
                    try:
                        # Yahoo Finance 데이터 사용 (항상 사용 가능)
                        stock = yf.Ticker(symbol)
                        hist = stock.history(period="1mo")
                        if not hist.empty and len(hist) >= 20:
                            hist = calculate_technical_indicators(hist)
                            score, signals = calculate_buy_score(hist)
                            if score >= 3:
                                recommendations.append({
                                    'symbol': symbol,
                                    'score': score,
                                    'price': hist.iloc[-1]['Close'],
                                    'signals': signals
                                })
                    except Exception as e:
                        continue
            
            with col1:
                st.markdown("<div class='metric-card'>", unsafe_allow_html=True)
                st.metric("추천 종목 수", len(recommendations))
                st.markdown("</div>", unsafe_allow_html=True)
            
            with col2:
                st.markdown("<div class='metric-card'>", unsafe_allow_html=True)
                st.metric("분석 종목 수", len(DEFAULT_SYMBOLS))
                st.markdown("</div>", unsafe_allow_html=True)
            
            with col3:
                st.markdown("<div class='metric-card'>", unsafe_allow_html=True)
                avg_score = np.mean([r['score'] for r in recommendations]) if recommendations else 0
                st.metric("평균 매수 점수", f"{avg_score:.1f}/5.0")
                st.markdown("</div>", unsafe_allow_html=True)
            
            with col4:
                st.markdown("<div class='metric-card'>", unsafe_allow_html=True)
                st.metric("마지막 업데이트", datetime.now().strftime("%H:%M"))
                st.markdown("</div>", unsafe_allow_html=True)
            
            # 추천 종목 리스트
            st.markdown("### 🎯 오늘의 추천 종목")
            
            if recommendations:
                for rec in sorted(recommendations, key=lambda x: x['score'], reverse=True):
                    st.markdown(f"""
                    <div class='recommendation-card'>
                        <h4>{rec['symbol']} - 매수 점수: {rec['score']}/5</h4>
                        <p>현재가: ${rec['price']:.2f}</p>
                        <p>신호: {', '.join(rec['signals'])}</p>
                    </div>
                    """, unsafe_allow_html=True)
            else:
                st.info("현재 추천 조건을 만족하는 종목이 없습니다.")
            
            # 시장 히트맵
            st.markdown("### 🗺️ 시장 히트맵")
            st.components.v1.iframe("https://finviz.com/map.ashx", height=600)
        
        # 실시간 분석
        elif selected == "실시간 분석":
            st.markdown("<h1 class='main-header'>🔍 실시간 종목 분석</h1>", unsafe_allow_html=True)
            
            col1, col2 = st.columns([3, 1])
            
            with col1:
                symbol = st.text_input("종목 심볼 입력 (예: AAPL, MSFT, TSLA)", "AAPL").upper().strip()
            
            with col2:
                period = st.selectbox("기간", ["1mo", "3mo", "6mo", "1y", "2y"])
            
            # Alpha Vantage 사용 옵션 (API 키가 있을 때만)
            use_alpha_vantage = False
            if ALPHA_VANTAGE_API_KEY and ALPHA_VANTAGE_AVAILABLE:
                use_alpha_vantage = st.checkbox("Alpha Vantage 데이터 사용", value=False)
            
            if st.button("분석 시작", use_container_width=True):
                if not symbol:
                    st.error("종목 심볼을 입력해주세요.")
                else:
                    with st.spinner("데이터 분석 중..."):
                        try:
                            # 데이터 가져오기
                            hist = None
                            
                            if use_alpha_vantage:
                                hist = get_alpha_vantage_data(symbol)
                                if hist is not None:
                                    st.info("Alpha Vantage 데이터를 사용합니다.")
                                else:
                                    st.warning("Alpha Vantage 데이터를 가져올 수 없어 Yahoo Finance를 사용합니다.")
                            
                            if hist is None:
                                stock = yf.Ticker(symbol)
                                hist = stock.history(period=period)
                            
                            # 데이터 유효성 검사
                            if hist is None or hist.empty or len(hist) < 20:
                                st.error(f"'{symbol}'에 대한 데이터를 가져올 수 없습니다.")
                                st.info("올바른 심볼인지 확인해주세요.")
                            else:
                                # 기술적 지표 계산
                                hist = calculate_technical_indicators(hist)
                                
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
                                    height=500
                                )
                                
                                st.plotly_chart(fig, use_container_width=True)
                                
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
                                    fig_rsi.add_hline(y=70, line_dash="dash", line_color="red")
                                    fig_rsi.add_hline(y=30, line_dash="dash", line_color="green")
                                    fig_rsi.update_layout(title="RSI", height=300)
                                    st.plotly_chart(fig_rsi, use_container_width=True)
                                
                                with col2:
                                    # MACD 차트
                                    fig_macd = go.Figure()
                                    fig_macd.add_trace(go.Scatter(
                                        x=hist.index,
                                        y=hist['MACD'],
                                        name='MACD',
                                        line=dict(color='blue')
                                    ))
                                    fig_macd.add_trace(go.Scatter(
                                        x=hist.index,
                                        y=hist['MACD_signal'],
                                        name='Signal',
                                        line=dict(color='red')
                                    ))
                                    fig_macd.update_layout(title="MACD", height=300)
                                    st.plotly_chart(fig_macd, use_container_width=True)
                                
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
                                
                                # 뉴스 가져오기 (NewsAPI 키가 있을 때만)
                                if NEWSAPI_KEY and NEWSAPI_AVAILABLE:
                                    st.markdown("### 📰 관련 뉴스")
                                    news_articles = get_stock_news(symbol)
                                    if news_articles:
                                        for article in news_articles[:3]:
                                            st.markdown(f"""
                                            <div class='news-card'>
                                                <h5>{article['title']}</h5>
                                                <p>{article['description'][:200] if article['description'] else ''}...</p>
                                                <a href='{article['url']}' target='_blank'>자세히 보기</a>
                                            </div>
                                            """, unsafe_allow_html=True)
                                
                                # PDF 리포트 생성
                                if st.button("📄 PDF 리포트 생성"):
                                    pdf_data = generate_pdf_report(
                                        symbol, 
                                        hist, 
                                        score, 
                                        signals, 
                                        st.session_state.user['username']
                                    )
                                    st.download_button(
                                        label="📥 리포트 다운로드",
                                        data=pdf_data,
                                        file_name=f"{symbol}_analysis_{datetime.now().strftime('%Y%m%d')}.pdf",
                                        mime="application/pdf"
                                    )
                                
                                # 분석 기록 저장
                                conn = sqlite3.connect('smartinvestor.db')
                                c = conn.cursor()
                                c.execute("""INSERT INTO analysis_history 
                                            (user_id, symbol, score, recommendation) 
                                            VALUES (?, ?, ?, ?)""",
                                         (st.session_state.user['id'], symbol, score, recommendation))
                                conn.commit()
                                conn.close()
                                
                        except Exception as e:
                            st.error(f"오류가 발생했습니다: {str(e)}")
        
        # AI 분석 (OpenAI API 키가 있을 때만)
        elif selected == "AI 분석" and OPENAI_API_KEY:
            st.markdown("<h1 class='main-header'>🤖 AI 기반 심층 분석</h1>", unsafe_allow_html=True)
            
            col1, col2 = st.columns([3, 1])
            
            with col1:
                symbol = st.text_input("분석할 종목 심볼", "AAPL").upper().strip()
            
            with col2:
                analysis_type = st.selectbox("분석 유형", ["종합 분석", "기술적 분석", "시장 센티먼트"])
            
            if st.button("AI 분석 시작", use_container_width=True):
                if not symbol:
                    st.error("종목 심볼을 입력해주세요.")
                else:
                    with st.spinner("AI가 종목을 분석 중입니다..."):
                        try:
                            # 기술적 데이터 가져오기
                            stock = yf.Ticker(symbol)
                            hist = stock.history(period="3mo")
                            
                            if hist.empty:
                                st.error("데이터를 가져올 수 없습니다.")
                            else:
                                hist = calculate_technical_indicators(hist)
                                latest_data = hist.iloc[-1]
                                
                                # 뉴스 데이터 가져오기
                                news_articles = get_stock_news(symbol) if NEWSAPI_KEY else []
                                
                                # AI 분석 실행
                                ai_analysis = get_ai_analysis(symbol, latest_data, news_articles)
                                
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
                                
                                # 가격 추세 차트
                                st.markdown("### 📈 가격 추세 분석")
                                
                                fig_trend = go.Figure()
                                fig_trend.add_trace(go.Scatter(
                                    x=hist.index,
                                    y=hist['Close'],
                                    mode='lines',
                                    name='종가',
                                    line=dict(color='blue', width=2)
                                ))
                                
                                # 이동평균선 추가
                                hist['MA20'] = hist['Close'].rolling(window=20).mean()
                                hist['MA50'] = hist['Close'].rolling(window=50).mean()
                                
                                fig_trend.add_trace(go.Scatter(
                                    x=hist.index,
                                    y=hist['MA20'],
                                    mode='lines',
                                    name='MA20',
                                    line=dict(color='orange', width=1)
                                ))
                                
                                fig_trend.add_trace(go.Scatter(
                                    x=hist.index,
                                    y=hist['MA50'],
                                    mode='lines',
                                    name='MA50',
                                    line=dict(color='red', width=1)
                                ))
                                
                                fig_trend.update_layout(
                                    title=f"{symbol} 가격 추세",
                                    xaxis_title="날짜",
                                    yaxis_title="가격 ($)",
                                    height=400
                                )
                                
                                st.plotly_chart(fig_trend, use_container_width=True)
                                
                        except Exception as e:
                            st.error(f"AI 분석 중 오류 발생: {str(e)}")
        
        # 포트폴리오
        elif selected == "포트폴리오":
            st.markdown("<h1 class='main-header'>💼 내 포트폴리오</h1>", unsafe_allow_html=True)
            
            # 분석 기록 조회
            conn = sqlite3.connect('smartinvestor.db')
            history_df = pd.read_sql_query("""
                SELECT symbol, analysis_date, score, recommendation 
                FROM analysis_history 
                WHERE user_id = ? 
                ORDER BY analysis_date DESC 
                LIMIT 20
            """, conn, params=(st.session_state.user['id'],))
            conn.close()
            
            if not history_df.empty:
                st.markdown("### 📈 최근 분석 기록")
                
                # 분석 기록을 보기 좋게 표시
                for _, row in history_df.iterrows():
                    rec_color = "recommendation-card" if row['recommendation'] == '매수' else "warning-card"
                    st.markdown(f"""
                    <div class='{rec_color}'>
                        <h5>{row['symbol']} - {row['recommendation']}</h5>
                        <p>분석일: {row['analysis_date']}</p>
                        <p>매수 점수: {row['score']}/5</p>
                    </div>
                    """, unsafe_allow_html=True)
                
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
                
                # 포트폴리오 성과 차트
                st.markdown("### 📊 분석 종목 분포")
                
                symbol_counts = history_df['symbol'].value_counts()
                
                fig_pie = go.Figure(data=[go.Pie(
                    labels=symbol_counts.index,
                    values=symbol_counts.values,
                    hole=.3
                )])
                
                fig_pie.update_layout(
                    title="분석 종목 비중",
                    height=400
                )
                
                st.plotly_chart(fig_pie, use_container_width=True)
                
            else:
                st.info("아직 분석 기록이 없습니다. 실시간 분석을 시작해보세요!")
        
        # 뉴스
        elif selected == "뉴스":
            st.markdown("<h1 class='main-header'>📰 투자 뉴스</h1>", unsafe_allow_html=True)
            
            # NewsAPI가 있으면 사용, 없으면 RSS 피드 사용
            if NEWSAPI_KEY and NEWSAPI_AVAILABLE:
                # 뉴스 카테고리 선택
                news_category = st.selectbox(
                    "뉴스 카테고리",
                    ["전체", "기술주", "금융", "에너지", "헬스케어"]
                )
                
                category_queries = {
                    "전체": "stock market",
                    "기술주": "tech stocks NASDAQ",
                    "금융": "banking financial stocks",
                    "에너지": "oil energy stocks",
                    "헬스케어": "healthcare pharma stocks"
                }
                
                try:
                    newsapi = NewsApiClient(api_key=NEWSAPI_KEY)
                    
                    all_articles = newsapi.get_everything(
                        q=category_queries[news_category],
                        language='en',
                        sort_by='publishedAt',
                        page_size=10,
                        from_param=(datetime.now() - timedelta(days=7)).strftime('%Y-%m-%d')
                    )
                    
                    articles = all_articles['articles']
                    
                    if articles:
                        st.markdown(f"### 📰 {news_category} 최신 뉴스")
                        
                        for article in articles:
                            if article['title'] and article['url']:
                                st.markdown(f"""
                                <div class='news-card'>
                                    <h4><a href='{article['url']}' target='_blank'>{article['title']}</a></h4>
                                    <p style='color: #666;'>{article['publishedAt'][:10]} | {article['source']['name']}</p>
                                    <p>{article['description'][:200] if article['description'] else ''}...</p>
                                </div>
                                """, unsafe_allow_html=True)
                except:
                    st.info("NewsAPI를 사용할 수 없어 RSS 피드를 사용합니다.")
            
            # RSS 피드 (백업 또는 기본)
            if not NEWSAPI_KEY or not NEWSAPI_AVAILABLE:
                st.markdown("### 📰 최신 투자 뉴스 (Investing.com)")
                feed_url = "https://www.investing.com/rss/news.rss"
                
                try:
                    feed = feedparser.parse(feed_url)
                    for entry in feed.entries[:10]:
                        st.markdown(f"""
                        <div class='news-card'>
                            <h4><a href='{entry.link}' target='_blank'>{entry.title}</a></h4>
                            <p style='color: #666;'>{entry.published}</p>
                            <p>{entry.get('summary', '')[:200]}...</p>
                        </div>
                        """, unsafe_allow_html=True)
                except Exception as e:
                    st.error(f"뉴스를 불러올 수 없습니다: {str(e)}")
        
        # 설정
        elif selected == "설정":
            st.markdown("<h1 class='main-header'>⚙️ 설정</h1>", unsafe_allow_html=True)
            
            # 사용자 정보
            st.markdown("### 👤 내 정보")
            col1, col2 = st.columns(2)
            
            with col1:
                st.info(f"사용자명: {st.session_state.user['username']}")
            
            with col2:
                if st.session_state.user.get('is_admin'):
                    st.success("관리자 권한 활성화")
            
            # API 상태
            st.markdown("### 🔌 API 연결 상태")
            
            col1, col2, col3, col4 = st.columns(4)
            
            with col1:
                if ALPHA_VANTAGE_API_KEY and ALPHA_VANTAGE_AVAILABLE:
                    st.success("Alpha Vantage ✅")
                else:
                    st.error("Alpha Vantage ❌")
            
            with col2:
                if OPENAI_API_KEY:
                    st.success("OpenAI ✅")
                else:
                    st.warning("OpenAI 🔧")
            
            with col3:
                if NEWSAPI_KEY and NEWSAPI_AVAILABLE:
                    st.success("NewsAPI ✅")
                else:
                    st.warning("NewsAPI 🔧")
            
            with col4:
                st.success("Yahoo Finance ✅")
            
            # API 키 설정 안내
            st.markdown("### 🔑 API 키 설정")
            st.info("""
            API 키는 Streamlit Cloud의 Settings > Secrets에서 관리됩니다.
            
            필요한 API 키:
            - **ALPHA_VANTAGE_API_KEY**: 실시간 주가 데이터
            - **OPENAI_API_KEY**: AI 분석 기능
            - **NEWSAPI_KEY**: 실시간 뉴스
            
            모든 API 키가 없어도 기본 기능은 사용 가능합니다.
            """)
            
            # 관리자 기능
            if st.session_state.user.get('is_admin'):
                st.markdown("### 🔐 관리자 기능")
                
                # 사용자 관리
                if st.checkbox("사용자 목록 보기"):
                    conn = sqlite3.connect('smartinvestor.db')
                    users_df = pd.read_sql_query(
                        "SELECT id, username, email, created_at, is_admin FROM users", 
                        conn
                    )
                    conn.close()
                    
                    st.dataframe(users_df, use_container_width=True)
                
                # 전체 분석 통계
                if st.checkbox("전체 분석 통계 보기"):
                    conn = sqlite3.connect('smartinvestor.db')
                    stats_df = pd.read_sql_query("""
                        SELECT 
                            u.username, 
                            COUNT(ah.id) as analysis_count, 
                            AVG(ah.score) as avg_score,
                            MAX(ah.analysis_date) as last_analysis
                        FROM users u
                        LEFT JOIN analysis_history ah ON u.id = ah.user_id
                        GROUP BY u.username
                        ORDER BY analysis_count DESC
                    """, conn)
                    conn.close()
                    
                    st.dataframe(stats_df, use_container_width=True)

if __name__ == "__main__":
    main()