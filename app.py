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
from streamlit_option_menu import option_menu

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
        text-align: center;
        color: #1E88E5;
        margin-bottom: 30px;
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
    # RSI
    df['RSI'] = ta.momentum.RSIIndicator(df['Close']).rsi()
    
    # MACD
    macd = ta.trend.MACD(df['Close'])
    df['MACD'] = macd.macd()
    df['MACD_signal'] = macd.macd_signal()
    df['MACD_diff'] = macd.macd_diff()
    
    # Bollinger Bands
    bb = ta.volatility.BollingerBands(df['Close'])
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
    
    return df

# 매수 신호 점수 계산
def calculate_buy_score(df):
    latest = df.iloc[-1]
    score = 0
    signals = []
    
    # RSI 과매도 (30 이하)
    if latest['RSI'] < 30:
        score += 1
        signals.append("RSI 과매도 신호")
    
    # MACD 골든크로스
    if latest['MACD'] > latest['MACD_signal'] and df.iloc[-2]['MACD'] <= df.iloc[-2]['MACD_signal']:
        score += 1
        signals.append("MACD 골든크로스")
    
    # 볼린저 밴드 하단 터치
    if latest['Close'] <= latest['BB_lower']:
        score += 1
        signals.append("볼린저 밴드 하단 터치")
    
    # CCI 과매도
    if latest['CCI'] < -100:
        score += 1
        signals.append("CCI 과매도 신호")
    
    # MFI 과매도
    if latest['MFI'] < 20:
        score += 1
        signals.append("MFI 과매도 신호")
    
    return score, signals

# AI 뉴스 요약 함수
def summarize_news_with_ai(news_items):
    if 'OPENAI_API_KEY' in st.secrets:
        openai.api_key = st.secrets['OPENAI_API_KEY']
        
        try:
            news_text = "\n".join([f"- {item['title']}" for item in news_items[:5]])
            
            response = openai.ChatCompletion.create(
                model="gpt-3.5-turbo",
                messages=[
                    {"role": "system", "content": "You are a financial news analyst. Summarize the key points in Korean."},
                    {"role": "user", "content": f"다음 뉴스들을 요약해주세요:\n{news_text}"}
                ],
                max_tokens=200
            )
            
            return response.choices[0].message.content
        except Exception as e:
            return "AI 요약을 사용할 수 없습니다."
    else:
        return "OpenAI API 키가 설정되지 않았습니다."

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
        st.markdown("<p style='text-align: center;'>AI 기반 스마트 투자 분석 플랫폼</p>", unsafe_allow_html=True)
        
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
            
            selected = option_menu(
                menu_title="메뉴",
                options=["홈", "실시간 분석", "포트폴리오", "뉴스", "설정"],
                icons=["house", "graph-up", "wallet2", "newspaper", "gear"],
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
            
            for symbol in DEFAULT_SYMBOLS:
                try:
                    stock = yf.Ticker(symbol)
                    hist = stock.history(period="1mo")
                    if not hist.empty:
                        hist = calculate_technical_indicators(hist)
                        score, signals = calculate_buy_score(hist)
                        if score >= 3:
                            recommendations.append({
                                'symbol': symbol,
                                'score': score,
                                'price': hist.iloc[-1]['Close'],
                                'signals': signals
                            })
                except:
                    pass
            
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
                symbol = st.text_input("종목 심볼 입력 (예: AAPL, MSFT, TSLA)", "AAPL")
            
            with col2:
                period = st.selectbox("기간", ["1mo", "3mo", "6mo", "1y", "2y"])
            
            if st.button("분석 시작", use_container_width=True):
                with st.spinner("데이터 분석 중..."):
                    try:
                        # 주식 데이터 가져오기
                        stock = yf.Ticker(symbol)
                        hist = stock.history(period=period)
                        
                        if hist.empty:
                            st.error("데이터를 가져올 수 없습니다. 심볼을 확인해주세요.")
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
                st.dataframe(history_df, use_container_width=True)
                
                # 분석 통계
                st.markdown("### 📊 분석 통계")
                col1, col2, col3 = st.columns(3)
                
                with col1:
                    total_analyses = len(history_df)
                    st.metric("총 분석 횟수", total_analyses)
                
                with col2:
                    avg_score = history_df['score'].mean()
                    st.metric("평균 매수 점수", f"{avg_score:.2f}")
                
                with col3:
                    buy_recommendations = len(history_df[history_df['recommendation'] == '매수'])
                    st.metric("매수 추천 횟수", buy_recommendations)
            else:
                st.info("아직 분석 기록이 없습니다. 실시간 분석을 시작해보세요!")
        
        # 뉴스
        elif selected == "뉴스":
            st.markdown("<h1 class='main-header'>📰 투자 뉴스</h1>", unsafe_allow_html=True)
            
            # RSS 피드에서 뉴스 가져오기
            feed_url = "https://www.investing.com/rss/news.rss"
            
            try:
                feed = feedparser.parse(feed_url)
                news_items = []
                
                for entry in feed.entries[:10]:
                    news_items.append({
                        'title': entry.title,
                        'link': entry.link,
                        'published': entry.published,
                        'summary': entry.get('summary', '')
                    })
                
                # AI 요약
                if st.button("🤖 AI 뉴스 요약"):
                    with st.spinner("AI가 뉴스를 분석 중입니다..."):
                        summary = summarize_news_with_ai(news_items)
                        st.markdown("### 📋 AI 뉴스 요약")
                        st.info(summary)
                
                # 뉴스 목록
                st.markdown("### 📰 최신 뉴스")
                for item in news_items:
                    st.markdown(f"""
                    <div style='padding: 10px; border-bottom: 1px solid #ddd;'>
                        <h4><a href='{item['link']}' target='_blank'>{item['title']}</a></h4>
                        <p style='color: #666;'>{item['published']}</p>
                        <p>{item['summary'][:200]}...</p>
                    </div>
                    """, unsafe_allow_html=True)
                    
            except Exception as e:
                st.error(f"뉴스를 불러오는 중 오류가 발생했습니다: {str(e)}")
        
        # 설정
        elif selected == "설정":
            st.markdown("<h1 class='main-header'>⚙️ 설정</h1>", unsafe_allow_html=True)
            
            # 사용자 정보
            st.markdown("### 👤 내 정보")
            st.info(f"사용자명: {st.session_state.user['username']}")
            
            # 관리자 기능
            if st.session_state.user.get('is_admin'):
                st.markdown("### 🔐 관리자 기능")
                
                conn = sqlite3.connect('smartinvestor.db')
                users_df = pd.read_sql_query("SELECT id, username, email, created_at FROM users", conn)
                conn.close()
                
                st.markdown("#### 사용자 목록")
                st.dataframe(users_df, use_container_width=True)
                
                st.markdown("#### 전체 분석 통계")
                conn = sqlite3.connect('smartinvestor.db')
                stats_df = pd.read_sql_query("""
                    SELECT u.username, COUNT(ah.id) as analysis_count, AVG(ah.score) as avg_score
                    FROM users u
                    LEFT JOIN analysis_history ah ON u.id = ah.user_id
                    GROUP BY u.username
                """, conn)
                conn.close()
                
                st.dataframe(stats_df, use_container_width=True)

if __name__ == "__main__":
    main()
