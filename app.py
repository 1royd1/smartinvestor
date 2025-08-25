import streamlit as st
import yfinance as yf
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import ta
from datetime import datetime, timedelta
from io import BytesIO
from reportlab.lib.pagesizes import letter
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib import colors
import os
import numpy as np
import json
import hashlib

try:
    from groq import Groq
    GROQ_AVAILABLE = True
except ImportError:
    GROQ_AVAILABLE = False

# 페이지 설정
st.set_page_config(
    page_title="SmartInvestor Pro",
    page_icon="💎",
    layout="wide",
    initial_sidebar_state="expanded"
)

# 모던 UI CSS
st.markdown("""
<style>
    /* 메인 스타일 */
    .stApp {
        background: linear-gradient(135deg, #1e3c72 0%, #2a5298 100%);
    }
    
    /* 버튼 스타일 */
    .stButton > button {
        background: linear-gradient(45deg, #667eea 0%, #764ba2 100%);
        color: white;
        border: none;
        padding: 0.75rem 2rem;
        font-weight: 600;
        border-radius: 10px;
        transition: all 0.3s ease;
    }
    
    .stButton > button:hover {
        transform: translateY(-2px);
        box-shadow: 0 6px 20px rgba(102, 126, 234, 0.4);
    }
    
    /* 메트릭 카드 */
    div[data-testid="metric-container"] {
        background: rgba(255,255,255,0.1);
        border: 1px solid rgba(255,255,255,0.2);
        padding: 1rem;
        border-radius: 10px;
        backdrop-filter: blur(10px);
    }
    
    /* 탭 스타일 */
    .stTabs [data-baseweb="tab-list"] {
        background: rgba(255,255,255,0.05);
        border-radius: 10px;
        padding: 0.5rem;
    }
    
    /* 차트 배경 */
    .js-plotly-plot {
        background: rgba(255,255,255,0.02) !important;
        border-radius: 15px;
        padding: 1rem;
    }
</style>
""", unsafe_allow_html=True)

# 사용자 데이터 파일
USER_DATA_FILE = "user_data.json"
ADMIN_USERNAME = "admin"

# 비밀번호 해시
def hash_password(password):
    return hashlib.sha256(password.encode()).hexdigest()

# 사용자 데이터 로드
def load_user_data():
    if os.path.exists(USER_DATA_FILE):
        with open(USER_DATA_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    else:
        return {
            ADMIN_USERNAME: {
                "password": hash_password("admin123"),
                "is_admin": True,
                "created_at": datetime.now().isoformat(),
                "portfolios": {
                    "stocks": ["AAPL", "GOOGL", "MSFT"],
                    "crypto": ["BTC-USD", "ETH-USD"],
                    "etf": ["SPY", "QQQ"]
                },
                "portfolio": {}
            }
        }

# 사용자 데이터 저장
def save_user_data(data):
    with open(USER_DATA_FILE, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

# 세션 초기화
if 'authenticated' not in st.session_state:
    st.session_state.authenticated = False
if 'username' not in st.session_state:
    st.session_state.username = None
if 'is_admin' not in st.session_state:
    st.session_state.is_admin = False
if 'user_data' not in st.session_state:
    st.session_state.user_data = load_user_data()
if 'stock_list' not in st.session_state:
    st.session_state.stock_list = []
if 'crypto_list' not in st.session_state:
    st.session_state.crypto_list = []
if 'etf_list' not in st.session_state:
    st.session_state.etf_list = []
if 'portfolio' not in st.session_state:
    st.session_state.portfolio = {}
if 'analysis_results' not in st.session_state:
    st.session_state.analysis_results = {}

# Groq 클라이언트
groq_client = None
if GROQ_AVAILABLE and st.secrets.get("GROQ_API_KEY"):
    groq_client = Groq(api_key=st.secrets["GROQ_API_KEY"])

# 추천 목록
TRENDING_CRYPTOS = {
    "🔥 인기 밈코인": ["DOGE-USD", "SHIB-USD", "PEPE-USD"],
    "🤖 AI 토큰": ["FET-USD", "RNDR-USD"],
    "⚡ Layer 2": ["MATIC-USD", "ARB-USD", "OP-USD"],
    "💎 주요 코인": ["BTC-USD", "ETH-USD", "BNB-USD", "SOL-USD"]
}

# 로그인 함수
def login(username, password):
    user_data = st.session_state.user_data
    if username in user_data and user_data[username]["password"] == hash_password(password):
        st.session_state.authenticated = True
        st.session_state.username = username
        st.session_state.is_admin = user_data[username].get("is_admin", False)
        
        # 포트폴리오 로드
        user_portfolio = user_data[username].get("portfolios", {})
        st.session_state.stock_list = user_portfolio.get("stocks", [])
        st.session_state.crypto_list = user_portfolio.get("crypto", [])
        st.session_state.etf_list = user_portfolio.get("etf", [])
        st.session_state.portfolio = user_data[username].get("portfolio", {})
        
        return True
    return False

# 로그아웃
def logout():
    save_current_user_data()
    st.session_state.authenticated = False
    st.session_state.username = None
    st.session_state.is_admin = False
    st.session_state.stock_list = []
    st.session_state.crypto_list = []
    st.session_state.etf_list = []
    st.session_state.portfolio = {}

# 현재 사용자 데이터 저장
def save_current_user_data():
    if st.session_state.authenticated and st.session_state.username:
        username = st.session_state.username
        st.session_state.user_data[username]["portfolios"] = {
            "stocks": st.session_state.stock_list,
            "crypto": st.session_state.crypto_list,
            "etf": st.session_state.etf_list
        }
        st.session_state.user_data[username]["portfolio"] = st.session_state.portfolio
        save_user_data(st.session_state.user_data)

# 데이터 함수들
@st.cache_data(ttl=300)
def get_stock_data(symbol, period="1mo"):
    try:
        stock = yf.Ticker(symbol)
        df = stock.history(period=period)
        info = stock.info
        return df, info
    except:
        return pd.DataFrame(), {}

@st.cache_data(ttl=600)
def get_stock_news(symbol):
    try:
        ticker = yf.Ticker(symbol)
        news = ticker.news
        return news[:5] if news else []
    except:
        return []

def calculate_indicators(df):
    if df.empty or len(df) < 20:
        return df
    
    try:
        # RSI
        df['RSI'] = ta.momentum.RSIIndicator(df['Close'], window=14).rsi()
        
        # MACD
        if len(df) >= 26:
            macd_indicator = ta.trend.MACD(df['Close'], window_slow=26, window_fast=12, window_sign=9)
            df['MACD'] = macd_indicator.macd()
            df['MACD_signal'] = macd_indicator.macd_signal()
            df['MACD_diff'] = macd_indicator.macd_diff()
            
            df['MACD'] = df['MACD'].bfill()
            df['MACD_signal'] = df['MACD_signal'].bfill()
            df['MACD_diff'] = df['MACD_diff'].fillna(0)
        
        # 기타 지표
        df['CCI'] = ta.trend.CCIIndicator(df['High'], df['Low'], df['Close']).cci()
        df['MFI'] = ta.volume.MFIIndicator(df['High'], df['Low'], df['Close'], df['Volume']).money_flow_index()
        
        # Stochastic
        stoch = ta.momentum.StochasticOscillator(df['High'], df['Low'], df['Close'])
        df['Stoch_K'] = stoch.stoch()
        df['Stoch_D'] = stoch.stoch_signal()
        
        # ATR
        df['ATR'] = ta.volatility.average_true_range(df['High'], df['Low'], df['Close'])
        
        # 이동평균
        df['SMA_20'] = ta.trend.sma_indicator(df['Close'], window=20)
        if len(df) >= 50:
            df['SMA_50'] = ta.trend.sma_indicator(df['Close'], window=50)
        
        # 볼린저 밴드
        bollinger = ta.volatility.BollingerBands(df['Close'])
        df['BB_upper'] = bollinger.bollinger_hband()
        df['BB_middle'] = bollinger.bollinger_mavg()
        df['BB_lower'] = bollinger.bollinger_lband()
        
        return df
    except Exception as e:
        st.error(f"지표 계산 오류: {str(e)}")
        return df

def create_chart(df, symbol):
    """차트 생성"""
    fig = make_subplots(
        rows=5, cols=1,
        shared_xaxes=True,
        vertical_spacing=0.03,
        row_heights=[0.5, 0.15, 0.15, 0.1, 0.1],
        subplot_titles=("Price", "RSI", "MACD", "Stochastic", "MFI")
    )
    
    # 캔들스틱
    fig.add_trace(
        go.Candlestick(
            x=df.index,
            open=df['Open'],
            high=df['High'],
            low=df['Low'],
            close=df['Close'],
            name='Price'
        ),
        row=1, col=1
    )
    
    # 볼린저 밴드
    if 'BB_upper' in df.columns:
        fig.add_trace(
            go.Scatter(x=df.index, y=df['BB_upper'], name='BB Upper', 
                      line=dict(color='rgba(255,255,255,0.2)', dash='dash')),
            row=1, col=1
        )
        fig.add_trace(
            go.Scatter(x=df.index, y=df['BB_lower'], name='BB Lower',
                      line=dict(color='rgba(255,255,255,0.2)', dash='dash'),
                      fill='tonexty', fillcolor='rgba(255,255,255,0.05)'),
            row=1, col=1
        )
    
    # 이동평균
    if 'SMA_20' in df.columns:
        fig.add_trace(
            go.Scatter(x=df.index, y=df['SMA_20'], name='MA20', 
                      line=dict(color='orange', width=2)),
            row=1, col=1
        )
    
    # RSI
    if 'RSI' in df.columns:
        fig.add_trace(
            go.Scatter(x=df.index, y=df['RSI'], name='RSI', 
                      line=dict(color='purple', width=2)),
            row=2, col=1
        )
        fig.add_hline(y=70, line_dash="dash", line_color="red", row=2, col=1)
        fig.add_hline(y=30, line_dash="dash", line_color="green", row=2, col=1)
    
    # MACD
    if 'MACD' in df.columns and not df['MACD'].isna().all():
        fig.add_trace(
            go.Scatter(x=df.index, y=df['MACD'], name='MACD', 
                      line=dict(color='blue', width=2)),
            row=3, col=1
        )
        if 'MACD_signal' in df.columns:
            fig.add_trace(
                go.Scatter(x=df.index, y=df['MACD_signal'], name='Signal', 
                          line=dict(color='red', width=2)),
                row=3, col=1
            )
    
    # Stochastic
    if 'Stoch_K' in df.columns:
        fig.add_trace(
            go.Scatter(x=df.index, y=df['Stoch_K'], name='%K', 
                      line=dict(color='blue', width=2)),
            row=4, col=1
        )
        if 'Stoch_D' in df.columns:
            fig.add_trace(
                go.Scatter(x=df.index, y=df['Stoch_D'], name='%D', 
                          line=dict(color='red', width=2)),
                row=4, col=1
            )
    
    # MFI
    if 'MFI' in df.columns:
        fig.add_trace(
            go.Scatter(x=df.index, y=df['MFI'], name='MFI', 
                      line=dict(color='green', width=2)),
            row=5, col=1
        )
    
    fig.update_layout(
        title=f"{symbol} Technical Analysis",
        height=900,
        showlegend=True,
        hovermode='x unified',
        plot_bgcolor='rgba(0,0,0,0)',
        paper_bgcolor='rgba(0,0,0,0)'
    )
    
    return fig

def perform_ai_analysis(df, symbol, info, asset_type="주식"):
    """AI 분석"""
    if not groq_client:
        return perform_technical_analysis(df, symbol)
    
    try:
        latest = df.iloc[-1]
        
        prompt = f"""
        {symbol} {asset_type} 분석:
        
        현재가: ${latest['Close']:.2f}
        RSI: {latest.get('RSI', 0):.2f}
        MACD: {latest.get('MACD', 0):.2f}
        
        다음을 한국어로 분석해주세요:
        1. 현재 기술적 상태
        2. 단기 전망
        3. 투자 전략
        """
        
        completion = groq_client.chat.completions.create(
            model="llama3-8b-8192",
            messages=[
                {"role": "system", "content": "당신은 한국의 투자 전문가입니다."},
                {"role": "user", "content": prompt}
            ],
            temperature=0.7,
            max_tokens=1000
        )
        
        return completion.choices[0].message.content
        
    except:
        return perform_technical_analysis(df, symbol)

def perform_technical_analysis(df, symbol):
    """기본 기술적 분석"""
    if df.empty:
        return "데이터가 부족합니다."
    
    latest = df.iloc[-1]
    
    return f"""
## {symbol} 기술적 분석

### 현재 지표
- RSI: {latest.get('RSI', 0):.2f}
- MACD: {latest.get('MACD', 0):.2f}
- CCI: {latest.get('CCI', 0):.2f}
- MFI: {latest.get('MFI', 0):.2f}

### 종합 의견
기술적 지표를 종합한 결과, 현재 {'매수' if latest.get('RSI', 50) < 30 else '매도' if latest.get('RSI', 50) > 70 else '중립'} 신호입니다.
"""

# 로그인 페이지
if not st.session_state.authenticated:
    st.markdown("<h1 style='text-align: center; color: white;'>💎 SmartInvestor Pro</h1>", unsafe_allow_html=True)
    
    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        with st.form("login_form"):
            st.markdown("<h2 style='text-align: center; color: white;'>로그인</h2>", unsafe_allow_html=True)
            username = st.text_input("사용자명")
            password = st.text_input("비밀번호", type="password")
            
            col_a, col_b = st.columns(2)
            with col_a:
                login_button = st.form_submit_button("로그인", use_container_width=True)
            with col_b:
                register_button = st.form_submit_button("회원가입", use_container_width=True)
            
            if login_button:
                if login(username, password):
                    st.success("로그인 성공!")
                    st.rerun()
                else:
                    st.error("로그인 실패")
            
            if register_button:
                if username and password:
                    if username not in st.session_state.user_data:
                        st.session_state.user_data[username] = {
                            "password": hash_password(password),
                            "is_admin": False,
                            "created_at": datetime.now().isoformat(),
                            "portfolios": {"stocks": [], "crypto": [], "etf": []},
                            "portfolio": {}
                        }
                        save_user_data(st.session_state.user_data)
                        st.success("회원가입 완료!")
                    else:
                        st.error("이미 존재하는 사용자명")
        
        with st.expander("테스트 계정"):
            st.info("Username: admin / Password: admin123")

# 메인 앱
else:
    # 헤더
    header_col1, header_col2, header_col3 = st.columns([1, 3, 1])
    with header_col1:
        st.markdown(f"<h3 style='color: white;'>👤 {st.session_state.username}</h3>", unsafe_allow_html=True)
    with header_col2:
        st.markdown("<h1 style='text-align: center; color: white;'>💎 SmartInvestor Pro</h1>", unsafe_allow_html=True)
    with header_col3:
        if st.button("🚪 로그아웃"):
            logout()
            st.rerun()
    
    # 사이드바
    with st.sidebar:
        st.header("📊 포트폴리오 관리")
        
        # 자산 추가
        with st.expander("➕ 자산 추가", expanded=True):
            asset_type = st.selectbox("자산 유형", ["주식", "암호화폐", "ETF"])
            
            symbol_input = st.text_input("심볼", placeholder="예: AAPL")
            
            if st.button("추가", use_container_width=True):
                if symbol_input:
                    symbol = symbol_input.upper()
                    if asset_type == "암호화폐" and not symbol.endswith("-USD"):
                        symbol += "-USD"
                    
                    target_list = (st.session_state.stock_list if asset_type == "주식" 
                                  else st.session_state.crypto_list if asset_type == "암호화폐"
                                  else st.session_state.etf_list)
                    
                    if symbol not in target_list:
                        try:
                            test_df = yf.Ticker(symbol).history(period="1d")
                            if not test_df.empty:
                                target_list.append(symbol)
                                save_current_user_data()
                                st.success(f"✅ {symbol} 추가됨!")
                        except:
                            st.error("유효하지 않은 심볼")
            
            # 트렌딩 (암호화폐)
            if asset_type == "암호화폐":
                st.markdown("### 트렌딩")
                for category, cryptos in TRENDING_CRYPTOS.items():
                    st.markdown(f"**{category}**")
                    cols = st.columns(2)
                    for i, crypto in enumerate(cryptos):
                        with cols[i % 2]:
                            if st.button(crypto.split('-')[0], key=f"add_{crypto}"):
                                if crypto not in st.session_state.crypto_list:
                                    st.session_state.crypto_list.append(crypto)
                                    save_current_user_data()
                                    st.success(f"✅ {crypto}")
        
        # 포트폴리오 관리
        with st.expander("💼 포트폴리오"):
            all_assets = st.session_state.stock_list + st.session_state.crypto_list + st.session_state.etf_list
            
            if all_assets:
                selected_asset = st.selectbox("자산", all_assets)
                
                col_1, col_2 = st.columns(2)
                with col_1:
                    shares = st.number_input("수량", min_value=0.0, value=0.0, step=0.01)
                with col_2:
                    buy_price = st.number_input("매수가", min_value=0.0, value=0.0, step=0.01)
                
                if st.button("저장", use_container_width=True):
                    if shares > 0:
                        st.session_state.portfolio[selected_asset] = {
                            "shares": shares,
                            "buy_price": buy_price
                        }
                        save_current_user_data()
                        st.success("저장됨!")
    
    # 메인 컨텐츠
    all_assets = st.session_state.stock_list + st.session_state.crypto_list + st.session_state.etf_list
    
    if all_assets:
        # 탭
        tab_titles = ["📊 대시보드"] + [f"📈 {asset}" for asset in all_assets]
        tabs = st.tabs(tab_titles)
        
        # 대시보드
        with tabs[0]:
            st.header("포트폴리오 대시보드")
            
            # 자산 카드
            cols = st.columns(3)
            for i, symbol in enumerate(all_assets):
                with cols[i % 3]:
                    df, info = get_stock_data(symbol, "5d")
                    if not df.empty:
                        current = df['Close'].iloc[-1]
                        prev = df['Close'].iloc[-2] if len(df) > 1 else current
                        change = ((current - prev) / prev) * 100
                        
                        # 아이콘
                        if symbol in st.session_state.crypto_list:
                            icon = "🪙"
                        elif symbol in st.session_state.etf_list:
                            icon = "📦"
                        else:
                            icon = "📈"
                        
                        st.metric(
                            label=f"{icon} {symbol}",
                            value=f"${current:.2f}" if current > 1 else f"${current:.6f}",
                            delta=f"{change:.2f}%"
                        )
        
        # 개별 자산 탭
        for idx, symbol in enumerate(all_assets):
            with tabs[idx + 1]:
                # 헤더
                col1, col2 = st.columns([3, 1])
                with col1:
                    st.header(f"{symbol}")
                with col2:
                    period = st.selectbox(
                        "기간",
                        ["1d", "5d", "1mo", "3mo", "6mo", "1y"],
                        index=2,
                        key=f"period_{symbol}"
                    )
                
                # 데이터 로드
                df, info = get_stock_data(symbol, period)
                
                if not df.empty:
                    # 지표 계산
                    df = calculate_indicators(df)
                    
                    # 기본 정보
                    col1, col2, col3, col4 = st.columns(4)
                    with col1:
                        st.metric("현재가", f"${df['Close'].iloc[-1]:.2f}")
                    with col2:
                        change = ((df['Close'].iloc[-1] - df['Close'].iloc[-2]) / df['Close'].iloc[-2] * 100)
                        st.metric("변동률", f"{change:.2f}%")
                    with col3:
                        st.metric("거래량", f"{df['Volume'].iloc[-1]:,.0f}")
                    with col4:
                        if symbol in st.session_state.portfolio:
                            shares = st.session_state.portfolio[symbol]['shares']
                            value = shares * df['Close'].iloc[-1]
                            st.metric("보유 가치", f"${value:,.2f}")
                    
                    # 차트
                    st.plotly_chart(create_chart(df, symbol), use_container_width=True)
                    
                    # 지표
                    st.subheader("기술적 지표")
                    col1, col2, col3, col4, col5, col6 = st.columns(6)
                    
                    with col1:
                        st.metric("RSI", f"{df['RSI'].iloc[-1]:.2f}" if 'RSI' in df.columns else "N/A")
                    with col2:
                        if 'MACD' in df.columns and not df['MACD'].isna().all():
                            st.metric("MACD", f"{df['MACD'].iloc[-1]:.2f}")
                        else:
                            st.metric("MACD", "N/A")
                    with col3:
                        st.metric("CCI", f"{df['CCI'].iloc[-1]:.2f}" if 'CCI' in df.columns else "N/A")
                    with col4:
                        st.metric("MFI", f"{df['MFI'].iloc[-1]:.2f}" if 'MFI' in df.columns else "N/A")
                    with col5:
                        st.metric("Stoch %K", f"{df['Stoch_K'].iloc[-1]:.2f}" if 'Stoch_K' in df.columns else "N/A")
                    with col6:
                        st.metric("ATR", f"{df['ATR'].iloc[-1]:.2f}" if 'ATR' in df.columns else "N/A")
                    
                    # 뉴스
                    st.subheader("최신 뉴스")
                    news = get_stock_news(symbol)
                    if news:
                        for article in news[:3]:
                            with st.expander(article.get('title', 'N/A')[:80]):
                                st.write(article.get('title', 'N/A'))
                                if article.get('link'):
                                    st.markdown(f"[전체 기사]({article.get('link')})")
                    else:
                        st.info("뉴스가 없습니다.")
                    
                    # 분석 버튼
                    col1, col2 = st.columns(2)
                    with col1:
                        if st.button("📊 기술적 분석", key=f"tech_{symbol}"):
                            analysis = perform_technical_analysis(df, symbol)
                            st.markdown(analysis)
                    with col2:
                        if st.button("🤖 AI 분석", key=f"ai_{symbol}"):
                            asset_type = "암호화폐" if symbol in st.session_state.crypto_list else "ETF" if symbol in st.session_state.etf_list else "주식"
                            analysis = perform_ai_analysis(df, symbol, info, asset_type)
                            st.markdown(analysis)
                else:
                    st.error(f"{symbol} 데이터를 불러올 수 없습니다.")
    else:
        st.info("👈 사이드바에서 자산을 추가하세요!")

# 푸터
st.markdown("---")
st.markdown(f"<p style='text-align: center; color: white;'>SmartInvestor Pro | {datetime.now().strftime('%Y-%m-%d %H:%M')}</p>", unsafe_allow_html=True)
