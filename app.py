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
    page_title="AI 투자 분석 플랫폼",
    page_icon="📈",
    layout="wide",
    initial_sidebar_state="expanded"
)

# CSS 스타일
st.markdown("""
<style>
    .stButton > button {
        width: 100%;
        background-color: #0066cc;
        color: white;
        border-radius: 5px;
        padding: 0.5rem 1rem;
        font-weight: bold;
        transition: all 0.3s;
    }
    .stButton > button:hover {
        background-color: #0052a3;
        transform: translateY(-2px);
    }
    .metric-card {
        background-color: #f0f2f6;
        padding: 1rem;
        border-radius: 0.5rem;
        text-align: center;
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
                "portfolio": {},
                "watchlist": []
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
    "🤖 AI 관련": ["FET-USD", "RNDR-USD"],
    "⚡ Layer 2": ["MATIC-USD", "ARB-USD", "OP-USD"],
    "🏆 주요 코인": ["BTC-USD", "ETH-USD", "BNB-USD", "SOL-USD"]
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
    
    # 캔들차트
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
        if 'Stoch_D' in df.columns:
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
        showlegend=True
    )
    
    return fig

def predict_price(df, days=7):
    if df is None or df.empty or len(df) < 50:
        return None
    
    try:
        prices = df['Close'].values
        x = np.arange(len(prices))
        z = np.polyfit(x, prices, 1)
        linear_pred = np.poly1d(z)(np.arange(len(prices), len(prices) + days))
        
        volatility = df['Close'].pct_change().std()
        predictions = []
        for i in range(days):
            pred = linear_pred[i] * (1 + np.random.normal(0, volatility/2))
            predictions.append(max(pred, df['Close'].min() * 0.5))
        
        return np.array(predictions)
    except:
        return None

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
        
        prompt = f"""
        당신은 한국의 전문 투자 분석가입니다. {symbol} {asset_type}을 분석해주세요:
        
        [기본 정보]
        - 현재가: ${latest['Close']:.2f}
        - RSI: {latest.get('RSI', 0):.2f}
        - MACD: {latest.get('MACD', 0):.2f}
        {news_summary}
        
        다음을 한국어로 상세히 분석해주세요:
        1. 현재 기술적 상태
        2. 단기(1주) 및 중기(1개월) 전망
        3. 주요 매매 신호
        4. 리스크 요인
        5. 구체적인 투자 전략
        
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

def generate_pdf_report(df, symbol, info):
    try:
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
        return buffer
    except Exception as e:
        st.error(f"PDF 생성 오류: {str(e)}")
        return None

# 로그인 페이지
if not st.session_state.authenticated:
    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
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
                            "portfolio": {}
                        }
                        save_user_data(st.session_state.user_data)
                        st.success("회원가입 완료! 로그인해주세요.")
                    else:
                        st.error("이미 존재하는 사용자명입니다.")
        
        with st.expander("📌 테스트 계정"):
            st.info("""
            **관리자 계정**
            - ID: admin
            - PW: admin123
            """)

# 메인 앱
else:
    # 헤더
    col1, col2, col3 = st.columns([2, 6, 2])
    with col1:
        st.markdown(f"### 👤 {st.session_state.username}")
    with col2:
        st.title("📈 AI 투자 분석 플랫폼")
    with col3:
        if st.button("🚪 로그아웃"):
            logout()
            st.rerun()
    
    # 사이드바
    with st.sidebar:
        st.header("📊 포트폴리오 관리")
        
        if st.button("💾 저장"):
            save_current_user_data()
            st.success("저장 완료!")
        
        # 자산 추가
        asset_type = st.selectbox("자산 유형", ["주식", "암호화폐", "ETF"])
        
        with st.form("add_asset_form"):
            if asset_type == "암호화폐":
                new_asset = st.text_input("심볼", placeholder="예: BTC-USD")
            else:
                new_asset = st.text_input("심볼", placeholder="예: AAPL")
            
            if st.form_submit_button("➕ 추가"):
                if new_asset:
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
                        except:
                            st.error("유효하지 않은 심볼입니다.")
        
        # 트렌딩 암호화폐
        if asset_type == "암호화폐":
            st.subheader("🔥 트렌딩")
            for category, cryptos in TRENDING_CRYPTOS.items():
                with st.expander(category):
                    for crypto in cryptos:
                        if st.button(f"+ {crypto}", key=f"add_{crypto}"):
                            if crypto not in st.session_state.crypto_list:
                                st.session_state.crypto_list.append(crypto)
                                save_current_user_data()
                                st.success(f"✅ {crypto} 추가됨!")
        
        # 포트폴리오 관리
        st.markdown("---")
        st.subheader("💼 보유 자산")
        all_assets = st.session_state.stock_list + st.session_state.crypto_list + st.session_state.etf_list
        
        if all_assets:
            selected_asset = st.selectbox("자산 선택", all_assets)
            col1, col2 = st.columns(2)
            with col1:
                shares = st.number_input("수량", min_value=0.0, value=0.0, step=0.01)
            with col2:
                buy_price = st.number_input("매수가", min_value=0.0, value=0.0, step=0.01)
            
            if st.button("💾 저장", key="save_portfolio"):
                if shares > 0:
                    st.session_state.portfolio[selected_asset] = {
                        "shares": shares,
                        "buy_price": buy_price
                    }
                    save_current_user_data()
                    st.success(f"✅ {selected_asset} 저장됨!")
    
    # 메인 컨텐츠
    all_assets = st.session_state.stock_list + st.session_state.crypto_list + st.session_state.etf_list
    
    if all_assets:
        # 탭 생성
        tab_titles = ["📊 대시보드"] + [f"📌 {asset}" for asset in all_assets]
        tabs = st.tabs(tab_titles)
        
        # 대시보드
        with tabs[0]:
            st.header("📊 전체 대시보드")
            
            # 포트폴리오 요약
            if st.session_state.portfolio:
                current_prices = {}
                for symbol in st.session_state.portfolio.keys():
                    df, _ = get_stock_data(symbol, "1d")
                    if not df.empty:
                        current_prices[symbol] = df['Close'].iloc[-1]
                
                if current_prices:
                    total_value, portfolio_details = calculate_portfolio_value(st.session_state.portfolio, current_prices)
                    
                    col1, col2, col3 = st.columns(3)
                    with col1:
                        st.metric("총 포트폴리오", f"${total_value:,.2f}")
                    with col2:
                        total_profit = sum([d['Profit'] for d in portfolio_details])
                        st.metric("총 수익", f"${total_profit:,.2f}")
                    with col3:
                        st.metric("보유 종목", len(st.session_state.portfolio))
            
            # 자산 현황
            st.subheader("📈 자산 현황")
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
                            value=f"${current:.2f}" if current > 10 else f"${current:.6f}",
                            delta=f"{change:.2f}%"
                        )
        
        # 개별 자산 탭
        for idx, symbol in enumerate(all_assets):
            with tabs[idx + 1]:
                # 자산 타입
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
                        st.metric("RSI", f"{rsi_val:.2f}")
                    
                    with col2:
                        if 'MACD' in df.columns and not df['MACD'].isna().all():
                            macd_val = df['MACD'].iloc[-1]
                            st.metric("MACD", f"{macd_val:.2f}")
                        else:
                            st.metric("MACD", "N/A")
                    
                    with col3:
                        cci_val = df['CCI'].iloc[-1] if 'CCI' in df.columns else 0
                        st.metric("CCI", f"{cci_val:.2f}")
                    
                    with col4:
                        mfi_val = df['MFI'].iloc[-1] if 'MFI' in df.columns else 50
                        st.metric("MFI", f"{mfi_val:.2f}")
                    
                    with col5:
                        if 'Stoch_K' in df.columns:
                            stoch_val = df['Stoch_K'].iloc[-1]
                            st.metric("Stoch %K", f"{stoch_val:.2f}")
                    
                    with col6:
                        if 'ATR' in df.columns:
                            atr_val = df['ATR'].iloc[-1]
                            st.metric("ATR", f"{atr_val:.2f}")
                    
                    # 뉴스
                    st.subheader("📰 최신 뉴스")
                    news = get_stock_news(symbol)
                    if news:
                        for article in news[:3]:
                            with st.expander(f"📄 {article.get('title', 'N/A')[:60]}..."):
                                st.write(article.get('title', 'N/A'))
                                if article.get('link'):
                                    st.markdown(f"[전체 기사]({article.get('link')})")
                    else:
                        st.info("최신 뉴스가 없습니다.")
                    
                    # 예측
                    st.subheader("📈 가격 예측")
                    predictions = predict_price(df, days=7)
                    if predictions is not None:
                        col1, col2 = st.columns([3, 1])
                        with col1:
                            pred_fig = go.Figure()
                            
                            # 실제 가격
                            pred_fig.add_trace(go.Scatter(
                                x=df.index[-30:],
                                y=df['Close'][-30:],
                                mode='lines',
                                name='실제 가격',
                                line=dict(color='blue', width=2)
                            ))
                            
                            # 예측
                            future_dates = pd.date_range(start=df.index[-1] + timedelta(days=1), periods=7)
                            pred_fig.add_trace(go.Scatter(
                                x=future_dates,
                                y=predictions,
                                mode='lines+markers',
                                name='예측 가격',
                                line=dict(color='red', width=2, dash='dash')
                            ))
                            
                            pred_fig.update_layout(title="7일 가격 예측", height=400)
                            st.plotly_chart(pred_fig, use_container_width=True)
                        
                        with col2:
                            st.metric("현재가", f"${df['Close'].iloc[-1]:.2f}")
                            st.metric("7일 후 예측", f"${predictions[-1]:.2f}")
                            change_pct = ((predictions[-1] - df['Close'].iloc[-1]) / df['Close'].iloc[-1]) * 100
                            st.metric("예상 변동률", f"{change_pct:+.2f}%")
                    
                    # 분석 버튼
                    st.markdown("---")
                    col1, col2, col3 = st.columns(3)
                    
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
                            if pdf_buffer:
                                st.download_button(
                                    label="📥 다운로드",
                                    data=pdf_buffer,
                                    file_name=f"{symbol}_report_{datetime.now().strftime('%Y%m%d')}.pdf",
                                    mime="application/pdf"
                                )
                    
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
            - 미국: AAPL, GOOGL, MSFT, NVDA
            - 한국: 005930.KS, 000660.KS
            
            ### 🪙 인기 암호화폐
            - 주요: BTC-USD, ETH-USD
            - 밈코인: DOGE-USD, SHIB-USD
            
            ### 📦 인기 ETF
            - SPY, QQQ, ARKK
            """)

# 푸터
st.markdown("---")
st.caption(f"AI 투자 분석 플랫폼 | {datetime.now().strftime('%Y-%m-%d %H:%M')}")
