# 함수들
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
            
            # fillna method 대신 bfill() 사용
            df['MACD'] = df['MACD'].bfill()
            df['MACD_signal'] = df['MACD_signal'].bfill()
            df['MACD_diff'] = df['MACD_diff'].fillna(0)
        else:
            df['MACD'] = 0
            df['MACD_signal'] = 0
            df['MACD_diff'] = 0
        
        # 기타 지표들
        df['CCI'] = ta.trend.CCIIndicator(df['High'], df['Low'], df['Close']).cci()
        df['MFI'] = ta.volume.MFIIndicator(df['High'], df['Low'], df['Close'], df['Volume']).money_flow_index()
        
        # 볼린저 밴드
        bollinger = ta.volatility.BollingerBands(df['Close'])
        df['BB_upper'] = bollinger.bollinger_hband()
        df['BB_middle'] = bollinger.bollinger_mavg()
        df['BB_lower'] = bollinger.bollinger_lband()
        
        # 이동평균
        df['SMA_20'] = ta.trend.sma_indicator(df['Close'], window=20)
        df['SMA_50'] = ta.trend.sma_indicator(df['Close'], window=50) if len(df) >= 50 else None
        df['SMA_200'] = ta.trend.sma_indicator(df['Close'], window=200) if len(df) >= 200 else None
        
        # Stochastic
        stoch = ta.momentum.StochasticOscillator(df['High'], df['Low'], df['Close'])
        df['Stoch_K'] = stoch.stoch()
        df['Stoch_D'] = stoch.stoch_signal()
        
        # ATR
        df['ATR'] = ta.volatility.average_true_range(df['High'], df['Low'], df['Close'])
        
        return df
    except Exception as e:
        st.error(f"지표 계산 오류: {str(e)}")
        return df

def predict_price(df, days=7):
    """가격 예측 함수"""
    if df is None or df.empty or len(df) < 50:
        return None
    
    try:
        prices = df['Close'].values
        x = np.arange(len(prices))
        z = np.polyfit(x, prices, 1)
        linear_pred = np.poly1d(z)(np.arange(len(prices), len(prices) + days))
        
        # 변동성 추가
        volatility = df['Close'].pct_change().std()
        predictions = []
        for i in range(days):
            pred = linear_pred[i] * (1 + np.random.normal(0, volatility/2))
            predictions.append(max(pred, df['Close'].min() * 0.5))
        
        return np.array(predictions)
    except Exception as e:
        return None

def calculate_portfolio_value(portfolio, current_prices):
    """포트폴리오 가치 계산"""
    total_value = 0
    portfolio_details = []
    
    for symbol, data in portfolio.items():
        if symbol in current_prices:
            shares = data.get('shares', 0)
            buy_price = data.get('buy_price', current_prices[symbol])
            current_price = current_prices[symbol]
            value = shares * current_price
            cost = shares * buy_price
            profit = value - cost
            profit_pct = (profit / cost * 100) if cost > 0 else 0
            
            total_value += value
            portfolio_details.append({
                'Symbol': symbol,
                'Shares': shares,
                'Buy Price': buy_price,
                'Current Price': current_price,
                'Value': value,
                'Profit': profit,
                'Profit %': profit_pct
            })
    
    return total_value, portfolio_details

def generate_pdf_report(df, symbol, info):
    """PDF 리포트 생성"""
    buffer = BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=letter)
    story = []
    
    styles = getSampleStyleSheet()
    
    # 제목
    story.append(Paragraph(f"{symbol} 투자 분석 리포트", styles['Title']))
    story.append(Spacer(1, 12))
    
    # 생성 정보
    story.append(Paragraph(f"생성일: {datetime.now().strftime('%Y-%m-%d %H:%M')}", styles['Normal']))
    story.append(Paragraph(f"분석자: {st.session_state.get('username', 'Guest')}", styles['Normal']))
    story.append(Spacer(1, 20))
    
    # 현재 가격
    current_price = df['Close'].iloc[-1]
    prev_close = df['Close'].iloc[-2] if len(df) > 1 else current_price
    change_pct = ((current_price - prev_close) / prev_close * 100) if prev_close != 0 else 0
    
    price_data = [
        ["현재가", f"${current_price:.2f}"],
        ["전일 종가", f"${prev_close:.2f}"],
        ["변동률", f"{change_pct:+.2f}%"],
        ["거래량", f"{df['Volume'].iloc[-1]:,.0f}"]
    ]
    
    price_table = Table(price_data, colWidths=[100, 200])
    price_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, -1), colors.lightblue),
        ('GRID', (0, 0), (-1, -1), 1, colors.black)
    ]))
    story.append(price_table)
    
    doc.build(story)
    buffer.seek(0)
    return bufferimport streamlit as st
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
from reportlab.lib.units import inch
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
    page_title="AI 투자 분석 플랫폼 Pro",
    page_icon="📈",
    layout="wide",
    initial_sidebar_state="expanded"
)

# CSS 스타일
st.markdown("""
<style>
    .main > div {
        padding-top: 2rem;
    }
    .stButton > button {
        width: 100%;
        background-color: #0066cc;
        color: white;
        border-radius: 5px;
        padding: 0.5rem 1rem;
        font-weight: bold;
        border: none;
        transition: all 0.3s;
    }
    .stButton > button:hover {
        background-color: #0052a3;
        transform: translateY(-2px);
        box-shadow: 0 4px 8px rgba(0,0,0,0.2);
    }
    .metric-card {
        background-color: #f0f2f6;
        padding: 1rem;
        border-radius: 0.5rem;
        text-align: center;
        box-shadow: 0 2px 4px rgba(0,0,0,0.1);
    }
    .login-container {
        max-width: 400px;
        margin: auto;
        padding: 2rem;
        background-color: #f8f9fa;
        border-radius: 10px;
        box-shadow: 0 4px 6px rgba(0,0,0,0.1);
    }
</style>
""", unsafe_allow_html=True)

# 사용자 데이터 저장 경로
USER_DATA_FILE = "user_data.json"
ADMIN_USERNAME = "admin"

# 비밀번호 해시 함수
def hash_password(password):
    return hashlib.sha256(password.encode()).hexdigest()

# 사용자 데이터 로드
def load_user_data():
    if os.path.exists(USER_DATA_FILE):
        with open(USER_DATA_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    else:
        # 초기 관리자 계정 생성
        return {
            ADMIN_USERNAME: {
                "password": hash_password("admin123"),  # 기본 비밀번호
                "is_admin": True,
                "created_at": datetime.now().isoformat(),
                "portfolios": {
                    "stocks": ["AAPL", "GOOGL", "MSFT"],
                    "crypto": ["BTC-USD", "ETH-USD"],
                    "etf": ["SPY", "QQQ"]
                },
                "portfolio": {},
                "watchlist": [],
                "settings": {}
            }
        }

# 사용자 데이터 저장
def save_user_data(data):
    with open(USER_DATA_FILE, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

# 세션 상태 초기화
if 'authenticated' not in st.session_state:
    st.session_state.authenticated = False
if 'username' not in st.session_state:
    st.session_state.username = None
if 'is_admin' not in st.session_state:
    st.session_state.is_admin = False
if 'user_data' not in st.session_state:
    st.session_state.user_data = load_user_data()

# 로그인 함수
def login(username, password):
    user_data = st.session_state.user_data
    if username in user_data and user_data[username]["password"] == hash_password(password):
        st.session_state.authenticated = True
        st.session_state.username = username
        st.session_state.is_admin = user_data[username].get("is_admin", False)
        
        # 사용자 포트폴리오 로드
        user_portfolio = user_data[username].get("portfolios", {})
        st.session_state.stock_list = user_portfolio.get("stocks", [])
        st.session_state.crypto_list = user_portfolio.get("crypto", [])
        st.session_state.etf_list = user_portfolio.get("etf", [])
        st.session_state.portfolio = user_data[username].get("portfolio", {})
        st.session_state.watchlist = user_data[username].get("watchlist", [])
        
        return True
    return False

# 로그아웃 함수
def logout():
    save_current_user_data()
    st.session_state.authenticated = False
    st.session_state.username = None
    st.session_state.is_admin = False
    st.session_state.stock_list = []
    st.session_state.crypto_list = []
    st.session_state.etf_list = []
    st.session_state.portfolio = {}
    st.session_state.watchlist = []

# 현재 사용자 데이터 저장
def save_current_user_data():
    if st.session_state.authenticated and st.session_state.username:
        username = st.session_state.username
        st.session_state.user_data[username]["portfolios"] = {
            "stocks": st.session_state.get('stock_list', []),
            "crypto": st.session_state.get('crypto_list', []),
            "etf": st.session_state.get('etf_list', [])
        }
        st.session_state.user_data[username]["portfolio"] = st.session_state.get('portfolio', {})
        st.session_state.user_data[username]["watchlist"] = st.session_state.get('watchlist', [])
        st.session_state.user_data[username]["last_login"] = datetime.now().isoformat()
        save_user_data(st.session_state.user_data)

# Groq 클라이언트 초기화
groq_client = None
if GROQ_AVAILABLE and st.secrets.get("GROQ_API_KEY"):
    groq_client = Groq(api_key=st.secrets["GROQ_API_KEY"])

# 세션 상태 초기화
if 'stock_list' not in st.session_state:
    st.session_state.stock_list = []
if 'crypto_list' not in st.session_state:
    st.session_state.crypto_list = []
if 'etf_list' not in st.session_state:
    st.session_state.etf_list = []
if 'analysis_results' not in st.session_state:
    st.session_state.analysis_results = {}
if 'portfolio' not in st.session_state:
    st.session_state.portfolio = {}
if 'watchlist' not in st.session_state:
    st.session_state.watchlist = []

# 추천 자산
TRENDING_CRYPTOS = {
    "🔥 인기 밈코인": ["DOGE-USD", "SHIB-USD", "PEPE-USD", "FLOKI-USD", "BONK-USD"],
    "🤖 AI 관련": ["FET-USD", "AGIX-USD", "OCEAN-USD", "RNDR-USD"],
    "⚡ Layer 2": ["MATIC-USD", "ARB-USD", "OP-USD"],
    "💰 DeFi": ["UNI-USD", "AAVE-USD", "SUSHI-USD", "COMP-USD"],
    "🏆 주요 코인": ["BTC-USD", "ETH-USD", "BNB-USD", "SOL-USD", "ADA-USD"]
}

# 함수들
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
            
            df['MACD'] = df['MACD'].fillna(method='bfill')
            df['MACD_signal'] = df['MACD_signal'].fillna(method='bfill')
            df['MACD_diff'] = df['MACD_diff'].fillna(0)
        else:
            df['MACD'] = 0
            df['MACD_signal'] = 0
            df['MACD_diff'] = 0
        
        # 기타 지표들
        df['CCI'] = ta.trend.CCIIndicator(df['High'], df['Low'], df['Close']).cci()
        df['MFI'] = ta.volume.MFIIndicator(df['High'], df['Low'], df['Close'], df['Volume']).money_flow_index()
        
        # 볼린저 밴드
        bollinger = ta.volatility.BollingerBands(df['Close'])
        df['BB_upper'] = bollinger.bollinger_hband()
        df['BB_middle'] = bollinger.bollinger_mavg()
        df['BB_lower'] = bollinger.bollinger_lband()
        
        # 이동평균
        df['SMA_20'] = ta.trend.sma_indicator(df['Close'], window=20)
        df['SMA_50'] = ta.trend.sma_indicator(df['Close'], window=50) if len(df) >= 50 else None
        df['SMA_200'] = ta.trend.sma_indicator(df['Close'], window=200) if len(df) >= 200 else None
        
        # Stochastic
        stoch = ta.momentum.StochasticOscillator(df['High'], df['Low'], df['Close'])
        df['Stoch_K'] = stoch.stoch()
        df['Stoch_D'] = stoch.stoch_signal()
        
        # ATR
        df['ATR'] = ta.volatility.average_true_range(df['High'], df['Low'], df['Close'])
        
        return df
    except Exception as e:
        st.error(f"지표 계산 오류: {str(e)}")
        return df

def create_chart(df, symbol):
    fig = make_subplots(
        rows=6, cols=1,
        shared_xaxes=True,
        vertical_spacing=0.02,
        subplot_titles=('가격', '거래량', 'RSI', 'MACD', 'Stochastic', 'MFI'),
        row_heights=[0.35, 0.1, 0.15, 0.15, 0.15, 0.1]
    )
    
    # 캔들스틱
    fig.add_trace(
        go.Candlestick(
            x=df.index,
            open=df['Open'],
            high=df['High'],
            low=df['Low'],
            close=df['Close'],
            name='가격'
        ),
        row=1, col=1
    )
    
    # 이동평균
    if 'SMA_20' in df.columns:
        fig.add_trace(
            go.Scatter(x=df.index, y=df['SMA_20'], name='SMA 20', line=dict(color='orange')),
            row=1, col=1
        )
    
    # 거래량
    colors = ['red' if df['Close'].iloc[i] < df['Open'].iloc[i] else 'green' for i in range(len(df))]
    fig.add_trace(
        go.Bar(x=df.index, y=df['Volume'], name='거래량', marker_color=colors),
        row=2, col=1
    )
    
    # RSI
    if 'RSI' in df.columns:
        fig.add_trace(
            go.Scatter(x=df.index, y=df['RSI'], name='RSI', line=dict(color='purple')),
            row=3, col=1
        )
        fig.add_hline(y=70, line_dash="dash", line_color="red", row=3, col=1)
        fig.add_hline(y=30, line_dash="dash", line_color="green", row=3, col=1)
    
    # MACD
    if 'MACD' in df.columns and not df['MACD'].isna().all():
        fig.add_trace(
            go.Scatter(x=df.index, y=df['MACD'], name='MACD', line=dict(color='blue')),
            row=4, col=1
        )
        if 'MACD_signal' in df.columns:
            fig.add_trace(
                go.Scatter(x=df.index, y=df['MACD_signal'], name='Signal', line=dict(color='red')),
                row=4, col=1
            )
    
    # Stochastic
    if 'Stoch_K' in df.columns:
        fig.add_trace(
            go.Scatter(x=df.index, y=df['Stoch_K'], name='%K', line=dict(color='blue')),
            row=5, col=1
        )
        fig.add_trace(
            go.Scatter(x=df.index, y=df['Stoch_D'], name='%D', line=dict(color='red')),
            row=5, col=1
        )
    
    # MFI
    if 'MFI' in df.columns:
        fig.add_trace(
            go.Scatter(x=df.index, y=df['MFI'], name='MFI', line=dict(color='brown')),
            row=6, col=1
        )
    
    fig.update_layout(
        title=f"{symbol} 기술적 분석",
        height=1200,
        showlegend=True,
        hovermode='x unified'
    )
    
    return fig

def perform_ai_analysis(df, symbol, info, asset_type="주식"):
    if not groq_client:
        return perform_technical_analysis(df, symbol)
    
    try:
        latest = df.iloc[-1]
        news = get_stock_news(symbol)
        news_summary = ""
        if news:
            news_summary = "\n[최신 뉴스]\n"
            for i, article in enumerate(news[:3]):
                title = article.get('title', '')
                news_summary += f"{i+1}. {title}\n"
        
        volatility = df['Close'].pct_change().std() * np.sqrt(252) * 100
        
        prompt = f"""
        당신은 한국의 전문 투자 분석가입니다. {symbol} {asset_type}을 분석해주세요:
        
        [기본 정보]
        - 현재가: ${latest['Close']:.2f}
        - RSI: {latest.get('RSI', 0):.2f}
        - MACD: {latest.get('MACD', 0):.2f}
        - 변동성: {volatility:.2f}%
        {news_summary}
        
        다음을 한국어로 상세히 분석해주세요:
        1. 현재 기술적 상태
        2. 단기(1주) 및 중기(1개월) 전망
        3. 주요 매매 신호
        4. 리스크 요인
        5. 구체적인 투자 전략 (진입가, 손절가, 목표가)
        
        모든 설명은 한국어로 작성하고 구체적인 숫자를 제시해주세요.
        """
        
        completion = groq_client.chat.completions.create(
            model="llama3-8b-8192",
            messages=[
                {
                    "role": "system",
                    "content": "당신은 한국의 전문 투자 분석가입니다. 모든 답변은 한국어로 작성합니다."
                },
                {
                    "role": "user",
                    "content": prompt
                }
            ],
            temperature=0.7,
            max_tokens=2000
        )
        
        result = "## 🤖 AI 심층 분석 결과\n\n"
        if news:
            result += "### 📰 최신 뉴스\n"
            for i, article in enumerate(news[:3]):
                title = article.get('title', 'N/A')
                link = article.get('link', '')
                if link:
                    result += f"{i+1}. [{title}]({link})\n"
                else:
                    result += f"{i+1}. {title}\n"
            result += "\n---\n\n"
        
        result += completion.choices[0].message.content
        return result
        
    except Exception as e:
        return perform_technical_analysis(df, symbol)

def perform_technical_analysis(df, symbol):
    if df.empty:
        return "데이터가 부족합니다."
    
    latest = df.iloc[-1]
    
    analysis = f"""
## 📊 {symbol} 기술적 분석

### 현재 지표
- RSI: {latest.get('RSI', 0):.2f}
- MACD: {latest.get('MACD', 0):.2f}
- CCI: {latest.get('CCI', 0):.2f}
- MFI: {latest.get('MFI', 0):.2f}

### 종합 의견
"""
    
    score = 0
    if 30 < latest.get('RSI', 50) < 70: score += 1
    if latest.get('MACD', 0) > latest.get('MACD_signal', 0): score += 1
    if -100 < latest.get('CCI', 0) < 100: score += 1
    if 20 < latest.get('MFI', 50) < 80: score += 1
    
    if score >= 3:
        analysis += "**긍정적** - 매수 고려"
    elif score >= 2:
        analysis += "**중립적** - 관망"
    else:
        analysis += "**부정적** - 매도 고려"
    
    return analysis

# 로그인 페이지
if not st.session_state.authenticated:
    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        st.markdown("<div class='login-container'>", unsafe_allow_html=True)
        st.title("🔐 로그인")
        
        with st.form("login_form"):
            username = st.text_input("사용자명")
            password = st.text_input("비밀번호", type="password")
            col1, col2 = st.columns(2)
            with col1:
                login_button = st.form_submit_button("로그인", use_container_width=True)
            with col2:
                register_button = st.form_submit_button("회원가입", use_container_width=True)
            
            if login_button:
                if login(username, password):
                    st.success("로그인 성공!")
                    st.rerun()
                else:
                    st.error("사용자명 또는 비밀번호가 틀렸습니다.")
            
            if register_button:
                if username and password:
                    if username not in st.session_state.user_data:
                        st.session_state.user_data[username] = {
                            "password": hash_password(password),
                            "is_admin": False,
                            "created_at": datetime.now().isoformat(),
                            "portfolios": {"stocks": [], "crypto": [], "etf": []},
                            "portfolio": {},
                            "watchlist": [],
                            "settings": {}
                        }
                        save_user_data(st.session_state.user_data)
                        st.success("회원가입 완료! 로그인해주세요.")
                    else:
                        st.error("이미 존재하는 사용자명입니다.")
                else:
                    st.error("사용자명과 비밀번호를 입력해주세요.")
        
        st.markdown("</div>", unsafe_allow_html=True)
        
        # 기본 계정 안내
        with st.expander("📌 테스트 계정"):
            st.info("""
            **관리자 계정**
            - 사용자명: admin
            - 비밀번호: admin123
            
            **일반 사용자**
            - 회원가입 후 이용
            """)

# 메인 앱 (로그인 후)
else:
    # 상단 헤더
    col1, col2, col3 = st.columns([2, 6, 2])
    with col1:
        st.markdown(f"### 👤 {st.session_state.username}")
        if st.session_state.is_admin:
            st.caption("🔧 관리자")
    with col2:
        st.title("📈 AI 투자 분석 플랫폼 Pro")
    with col3:
        if st.button("🚪 로그아웃", use_container_width=True):
            logout()
            st.rerun()
    
    # 관리자 페이지
    if st.session_state.is_admin:
        with st.sidebar:
            if st.button("👥 사용자 관리"):
                st.session_state.show_admin = True
    
    if st.session_state.get('show_admin', False) and st.session_state.is_admin:
        st.header("👥 사용자 관리")
        
        # 사용자 목록
        user_list = []
        for username, data in st.session_state.user_data.items():
            user_list.append({
                "사용자명": username,
                "관리자": "✅" if data.get("is_admin") else "❌",
                "생성일": data.get("created_at", "N/A")[:10],
                "마지막 로그인": data.get("last_login", "N/A")[:10] if "last_login" in data else "N/A"
            })
        
        df_users = pd.DataFrame(user_list)
        st.dataframe(df_users, use_container_width=True)
        
        # 사용자 삭제
        st.subheader("사용자 삭제")
        users_to_delete = [u for u in st.session_state.user_data.keys() if u != ADMIN_USERNAME]
        if users_to_delete:
            user_to_delete = st.selectbox("삭제할 사용자", users_to_delete)
            if st.button("🗑️ 사용자 삭제"):
                del st.session_state.user_data[user_to_delete]
                save_user_data(st.session_state.user_data)
                st.success(f"{user_to_delete} 삭제됨")
                st.rerun()
        
        if st.button("돌아가기"):
            st.session_state.show_admin = False
            st.rerun()
    
    # 메인 앱
    else:
        # 사이드바
        with st.sidebar:
            st.header("📊 포트폴리오 관리")
            
            # 자동 저장 알림
            if st.button("💾 포트폴리오 저장"):
                save_current_user_data()
                st.success("저장 완료!")
            
            # 자산 추가
            asset_type = st.selectbox("자산 유형", ["주식", "암호화폐", "ETF"])
            
            with st.form(f"add_{asset_type}_form"):
                if asset_type == "주식":
                    new_asset = st.text_input("주식 심볼", placeholder="예: AAPL")
                elif asset_type == "암호화폐":
                    new_asset = st.text_input("암호화폐 심볼", placeholder="예: BTC-USD")
                else:
                    new_asset = st.text_input("ETF 심볼", placeholder="예: SPY")
                
                add_button = st.form_submit_button("➕ 추가")
                
                if add_button and new_asset:
                    symbol = new_asset.upper()
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
                            else:
                                st.error(f"❌ {symbol}를 찾을 수 없습니다.")
                        except:
                            st.error(f"❌ 유효하지 않은 심볼입니다.")
                    else:
                        st.warning("⚠️ 이미 있습니다.")
            
            # 트렌딩 암호화폐
            if asset_type == "암호화폐":
                st.markdown("---")
                st.subheader("🔥 트렌딩")
                for category, cryptos in TRENDING_CRYPTOS.items():
                    with st.expander(category):
                        for crypto in cryptos:
                            if st.button(f"+ {crypto}", key=f"add_{crypto}"):
                                if crypto not in st.session_state.crypto_list:
                                    st.session_state.crypto_list.append(crypto)
                                    save_current_user_data()
                                    st.success(f"✅ {crypto} 추가됨!")
            
            st.markdown("---")
            
            # 포트폴리오 관리
            st.subheader("💼 보유 자산")
            all_assets = st.session_state.stock_list + st.session_state.crypto_list + st.session_state.etf_list
            
            if all_assets:
                selected_asset = st.selectbox("자산 선택", all_assets)
                col1, col2 = st.columns(2)
                with col1:
                    shares = st.number_input("수량", min_value=0.0, value=0.0, step=0.01)
                with col2:
                    buy_price = st.number_input("매수가", min_value=0.0, value=0.0, step=0.01)
                
                if st.button("💾 저장"):
                    if shares > 0:
                        st.session_state.portfolio[selected_asset] = {
                            "shares": shares,
                            "buy_price": buy_price
                        }
                        save_current_user_data()
                        st.success(f"✅ {selected_asset} 저장됨!")
                    elif selected_asset in st.session_state.portfolio:
                        del st.session_state.portfolio[selected_asset]
                        save_current_user_data()
                        st.success(f"✅ {selected_asset} 제거됨!")
            
            # 자산 삭제
            st.markdown("---")
            if all_assets:
                st.subheader("🗑️ 자산 삭제")
                remove_asset = st.selectbox("삭제할 자산", all_assets)
                if st.button("삭제"):
                    if remove_asset in st.session_state.stock_list:
                        st.session_state.stock_list.remove(remove_asset)
                    elif remove_asset in st.session_state.crypto_list:
                        st.session_state.crypto_list.remove(remove_asset)
                    elif remove_asset in st.session_state.etf_list:
                        st.session_state.etf_list.remove(remove_asset)
                    
                    if remove_asset in st.session_state.portfolio:
                        del st.session_state.portfolio[remove_asset]
                    
                    save_current_user_data()
                    st.success(f"✅ {remove_asset} 삭제됨!")
                    st.rerun()
        
        # 메인 컨텐츠
        all_assets = st.session_state.stock_list + st.session_state.crypto_list + st.session_state.etf_list
        
        if all_assets:
            # 탭 생성
            tab_titles = ["📊 대시보드", "💼 포트폴리오"] + [f"📌 {asset}" for asset in all_assets]
            tabs = st.tabs(tab_titles)
            
            # 대시보드 탭
            with tabs[0]:
                st.header("📊 전체 대시보드")
                
                # 포트폴리오 요약
                if st.session_state.portfolio:
                    current_prices = {}
                    for symbol in st.session_state.portfolio.keys():
                        df, _ = get_stock_data(symbol, "1d")
                        if not df.empty:
                            current_prices[symbol] = df['Close'].iloc[-1]
                    
                    total_value, portfolio_details = calculate_portfolio_value(st.session_state.portfolio, current_prices)
                    
                    col1, col2, col3, col4 = st.columns(4)
                    with col1:
                        st.metric("총 포트폴리오", f"${total_value:,.2f}")
                    with col2:
                        total_cost = sum([d['Profit'] + d['Value'] - d['Profit'] for d in portfolio_details])
                        total_profit = sum([d['Profit'] for d in portfolio_details])
                        st.metric("총 수익", f"${total_profit:,.2f}", f"{(total_profit/total_cost*100):.2f}%")
                    with col3:
                        st.metric("보유 종목", len(st.session_state.portfolio))
                    with col4:
                        st.metric("평균 수익률", f"{np.mean([d['Profit %'] for d in portfolio_details]):.2f}%")
                
                # 자산별 현황
                st.subheader("📈 자산 현황")
                cols = st.columns(3)
                for i, symbol in enumerate(all_assets):
                    with cols[i % 3]:
                        df, info = get_stock_data(symbol, "5d")
                        if not df.empty:
                            current = df['Close'].iloc[-1]
                            prev = df['Close'].iloc[-2] if len(df) > 1 else current
                            change = ((current - prev) / prev) * 100
                            
                            # 자산 타입 아이콘
                            if symbol in st.session_state.crypto_list:
                                icon = "🪙"
                            elif symbol in st.session_state.etf_list:
                                icon = "📦"
                            else:
                                icon = "📈"
                            
                            st.metric(
                                label=f"{icon} {symbol}",
                                value=f"${current:.2f}" if current > 10 else f"${current:.6f}",
                                delta=f"{change:.2f}%"
                            )
                            
                            # 미니 차트
                            fig = go.Figure()
                            fig.add_trace(go.Scatter(
                                x=df.index[-20:],
                                y=df['Close'][-20:],
                                mode='lines',
                                line=dict(color='green' if change >= 0 else 'red', width=2),
                                showlegend=False
                            ))
                            fig.update_layout(
                                height=100,
                                margin=dict(l=0, r=0, t=0, b=0),
                                xaxis=dict(visible=False),
                                yaxis=dict(visible=False),
                                paper_bgcolor='rgba(0,0,0,0)',
                                plot_bgcolor='rgba(0,0,0,0)'
                            )
                            st.plotly_chart(fig, use_container_width=True)
            
            # 포트폴리오 탭
            with tabs[1]:
                st.header("💼 포트폴리오 상세")
                
                if st.session_state.portfolio:
                    # 포트폴리오 테이블
                    portfolio_df = pd.DataFrame(portfolio_details)
                    
                    # 스타일 적용
                    def highlight_profit(val):
                        color = 'green' if val > 0 else 'red' if val < 0 else 'black'
                        return f'color: {color}'
                    
                    styled_df = portfolio_df.style.applymap(highlight_profit, subset=['Profit', 'Profit %'])
                    st.dataframe(styled_df, use_container_width=True)
                    
                    # 포트폴리오 차트
                    col1, col2 = st.columns(2)
                    
                    with col1:
                        # 파이 차트
                        fig = go.Figure(data=[go.Pie(
                            labels=portfolio_df['Symbol'],
                            values=portfolio_df['Value'],
                            hole=.3
                        )])
                        fig.update_layout(title="포트폴리오 구성", height=400)
                        st.plotly_chart(fig, use_container_width=True)
                    
                    with col2:
                        # 수익률 바 차트
                        fig = go.Figure(data=[
                            go.Bar(
                                x=portfolio_df['Symbol'],
                                y=portfolio_df['Profit %'],
                                marker_color=['green' if x > 0 else 'red' for x in portfolio_df['Profit %']]
                            )
                        ])
                        fig.update_layout(title="종목별 수익률 (%)", height=400)
                        st.plotly_chart(fig, use_container_width=True)
                else:
                    st.info("포트폴리오에 자산을 추가하세요.")
            
            # 개별 자산 탭들
            for idx, symbol in enumerate(all_assets):
                with tabs[idx + 2]:
                    # 자산 타입 판별
                    if symbol in st.session_state.crypto_list:
                        asset_type = "암호화폐"
                        icon = "🪙"
                    elif symbol in st.session_state.etf_list:
                        asset_type = "ETF"
                        icon = "📦"
                    else:
                        asset_type = "주식"
                        icon = "📈"
                    
                    # 헤더
                    col1, col2, col3 = st.columns([3, 1, 1])
                    with col1:
                        st.header(f"{icon} {symbol} 상세 분석")
                    with col2:
                        period = st.selectbox(
                            "기간",
                            ["1d", "5d", "1mo", "3mo", "6mo", "1y"],
                            index=2,
                            key=f"period_{symbol}"
                        )
                    with col3:
                        if st.button("🔄", key=f"refresh_{symbol}"):
                            st.cache_data.clear()
                            st.rerun()
                    
                    # 데이터 로드
                    with st.spinner(f"{symbol} 로딩중..."):
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
                        
                        # 기술적 지표
                        st.subheader("📊 기술적 지표")
                        col1, col2, col3, col4, col5, col6 = st.columns(6)
                        
                        with col1:
                            rsi_val = df['RSI'].iloc[-1] if 'RSI' in df.columns else 50
                            st.metric("RSI", f"{rsi_val:.2f}", 
                                     delta="과매수" if rsi_val > 70 else "과매도" if rsi_val < 30 else "정상")
                        
                        with col2:
                            if 'MACD' in df.columns and not df['MACD'].isna().all():
                                macd_val = df['MACD'].iloc[-1]
                                macd_signal = df['MACD_signal'].iloc[-1]
                                if not pd.isna(macd_val) and not pd.isna(macd_signal):
                                    macd_status = "매수" if macd_val > macd_signal else "매도"
                                    st.metric("MACD", f"{macd_val:.2f}", delta=macd_status)
                                else:
                                    st.metric("MACD", "계산중", delta="대기")
                            else:
                                st.metric("MACD", "N/A", delta="부족")
                        
                        with col3:
                            cci_val = df['CCI'].iloc[-1] if 'CCI' in df.columns else 0
                            st.metric("CCI", f"{cci_val:.2f}",
                                     delta="과매수" if cci_val > 100 else "과매도" if cci_val < -100 else "정상")
                        
                        with col4:
                            mfi_val = df['MFI'].iloc[-1] if 'MFI' in df.columns else 50
                            st.metric("MFI", f"{mfi_val:.2f}",
                                     delta="과매수" if mfi_val > 80 else "과매도" if mfi_val < 20 else "정상")
                        
                        with col5:
                            if 'Stoch_K' in df.columns:
                                stoch_val = df['Stoch_K'].iloc[-1]
                                st.metric("Stoch %K", f"{stoch_val:.2f}",
                                         delta="과매수" if stoch_val > 80 else "과매도" if stoch_val < 20 else "정상")
                        
                        with col6:
                            if 'ATR' in df.columns:
                                atr_val = df['ATR'].iloc[-1]
                                atr_pct = (atr_val / df['Close'].iloc[-1]) * 100
                                st.metric("ATR", f"{atr_val:.2f}", delta=f"{atr_pct:.1f}% 변동성")
                        
                        # 뉴스 섹션
                        st.subheader("📰 최신 뉴스")
                        news = get_stock_news(symbol)
                        if news:
                            for article in news[:3]:
                                with st.expander(f"📄 {article.get('title', 'N/A')[:60]}..."):
                                    col1, col2 = st.columns([3, 1])
                                    with col1:
                                        st.write(article.get('title', 'N/A'))
                                        if article.get('link'):
                                            st.markdown(f"[📖 전체 기사]({article.get('link')})")
                                    with col2:
                                        if article.get('publisher'):
                                            st.caption(f"📰 {article.get('publisher')}")
                        else:
                            st.info("최신 뉴스가 없습니다.")
                        
                        # 예측 섹션
                        st.subheader("📈 가격 예측")
                        predictions = predict_price(df, days=7)
                        if predictions is not None:
                            col1, col2 = st.columns([3, 1])
                            with col1:
                                # 예측 차트
                                pred_fig = go.Figure()
                                
                                # 실제 가격
                                pred_fig.add_trace(go.Scatter(
                                    x=df.index[-30:],
                                    y=df['Close'][-30:],
                                    mode='lines',
                                    name='실제 가격',
                                    line=dict(color='blue', width=2)
                                ))
                                
                                # 예측 가격
                                future_dates = pd.date_range(start=df.index[-1] + timedelta(days=1), periods=7)
                                pred_fig.add_trace(go.Scatter(
                                    x=future_dates,
                                    y=predictions,
                                    mode='lines+markers',
                                    name='예측 가격',
                                    line=dict(color='red', width=2, dash='dash')
                                ))
                                
                                pred_fig.update_layout(
                                    title="7일 가격 예측",
                                    height=400
                                )
                                st.plotly_chart(pred_fig, use_container_width=True)
                            
                            with col2:
                                st.metric("현재가", f"${df['Close'].iloc[-1]:.2f}")
                                st.metric("7일 후 예측", f"${predictions[-1]:.2f}")
                                change_pct = ((predictions[-1] - df['Close'].iloc[-1]) / df['Close'].iloc[-1]) * 100
                                st.metric("예상 변동률", f"{change_pct:+.2f}%")
                        
                        # 분석 버튼
                        st.markdown("---")
                        col1, col2, col3, col4 = st.columns(4)
                        
                        with col1:
                            if st.button("📊 기술적 분석", key=f"tech_{symbol}"):
                                with st.spinner("분석중..."):
                                    analysis = perform_technical_analysis(df, symbol)
                                    st.session_state.analysis_results[f"{symbol}_tech"] = analysis
                        
                        with col2:
                            if st.button("🤖 AI 분석", key=f"ai_{symbol}"):
                                with st.spinner("AI 분석중..."):
                                    analysis = perform_ai_analysis(df, symbol, info, asset_type)
                                    st.session_state.analysis_results[f"{symbol}_ai"] = analysis
                        
                        with col3:
                            if st.button("📄 PDF 리포트", key=f"pdf_{symbol}"):
                                pdf_buffer = generate_pdf_report(df, symbol, info)
                                st.download_button(
                                    label="📥 다운로드",
                                    data=pdf_buffer,
                                    file_name=f"{symbol}_report_{datetime.now().strftime('%Y%m%d')}.pdf",
                                    mime="application/pdf"
                                )
                        
                        with col4:
                            if st.button("🔄 초기화", key=f"clear_{symbol}"):
                                keys = [k for k in st.session_state.analysis_results.keys() if k.startswith(symbol)]
                                for key in keys:
                                    del st.session_state.analysis_results[key]
                                st.success("초기화됨")
                        
                        # 분석 결과
                        if f"{symbol}_tech" in st.session_state.analysis_results:
                            with st.expander("📊 기술적 분석 결과", expanded=True):
                                st.markdown(st.session_state.analysis_results[f"{symbol}_tech"])
                        
                        if f"{symbol}_ai" in st.session_state.analysis_results:
                            with st.expander("🤖 AI 분석 결과", expanded=True):
                                st.markdown(st.session_state.analysis_results[f"{symbol}_ai"])
                    else:
                        st.error(f"❌ {symbol} 데이터를 불러올 수 없습니다.")
        
        else:
            # 자산이 없을 때
            st.info("👈 사이드바에서 주식, 암호화폐, ETF를 추가하세요!")
            
            with st.expander("🚀 빠른 시작"):
                st.markdown("""
                ### 📈 인기 주식
                - 미국: AAPL, GOOGL, MSFT, NVDA, TSLA
                - 한국: 005930.KS, 000660.KS
                
                ### 🪙 인기 암호화폐
                - 주요: BTC-USD, ETH-USD
                - 밈코인: DOGE-USD, SHIB-USD
                
                ### 📦 인기 ETF
                - SPY, QQQ, ARKK
                """)

# 하단 정보
st.markdown("---")
st.caption(f"AI 투자 분석 플랫폼 Pro | 마지막 업데이트: {datetime.now().strftime('%Y-%m-%d %H:%M')}")

# 보조 함수들
def calculate_portfolio_value(portfolio, current_prices):
    total_value = 0
    portfolio_details = []
    
    for symbol, data in portfolio.items():
        if symbol in current_prices:
            shares = data.get('shares', 0)
            buy_price = data.get('buy_price', current_prices[symbol])
            current_price = current_prices[symbol]
            value = shares * current_price
            cost = shares * buy_price
            profit = value - cost
            profit_pct = (profit / cost * 100) if cost > 0 else 0
            
            total_value += value
            portfolio_details.append({
                'Symbol': symbol,
                'Shares': shares,
                'Buy Price': buy_price,
                'Current Price': current_price,
                'Value': value,
                'Profit': profit,
                'Profit %': profit_pct
            })
    
    return total_value, portfolio_details

def predict_price(df, days=7):
    if len(df) < 50:
        return None
    
    try:
        prices = df['Close'].values
        x = np.arange(len(prices))
        z = np.polyfit(x, prices, 1)
        linear_pred = np.poly1d(z)(np.arange(len(prices), len(prices) + days))
        
        # 변동성 추가
        volatility = df['Close'].pct_change().std()
        predictions = []
        for i in range(days):
            pred = linear_pred[i] * (1 + np.random.normal(0, volatility/2))
            predictions.append(max(pred, df['Close'].min() * 0.5))
        
        return np.array(predictions)
    except Exception as e:
        return None

def generate_pdf_report(df, symbol, info):
    buffer = BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=letter)
    story = []
    
    styles = getSampleStyleSheet()
    
    # 제목
    story.append(Paragraph(f"{symbol} 투자 분석 리포트", styles['Title']))
    story.append(Spacer(1, 12))
    
    # 생성 정보
    story.append(Paragraph(f"생성일: {datetime.now().strftime('%Y-%m-%d %H:%M')}", styles['Normal']))
    story.append(Paragraph(f"분석자: {st.session_state.username}", styles['Normal']))
    story.append(Spacer(1, 20))
    
    # 현재 가격
    current_price = df['Close'].iloc[-1]
    prev_close = df['Close'].iloc[-2] if len(df) > 1 else current_price
    change_pct = ((current_price - prev_close) / prev_close * 100) if prev_close != 0 else 0
    
    price_data = [
        ["현재가", f"${current_price:.2f}"],
        ["전일 종가", f"${prev_close:.2f}"],
        ["변동률", f"{change_pct:+.2f}%"],
        ["거래량", f"{df['Volume'].iloc[-1]:,.0f}"]
    ]
    
    price_table = Table(price_data, colWidths=[100, 200])
    price_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, -1), colors.lightblue),
        ('GRID', (0, 0), (-1, -1), 1, colors.black)
    ]))
    story.append(price_table)
    
    doc.build(story)
    buffer.seek(0)
    return buffer
            #
