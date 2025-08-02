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
import requests
try:
    from groq import Groq
    GROQ_AVAILABLE = True
except ImportError:
    GROQ_AVAILABLE = False

# 페이지 설정
st.set_page_config(
    page_title="AI 주식/암호화폐 분석 플랫폼",
    page_icon="📈",
    layout="wide",
    initial_sidebar_state="expanded"
)

# CSS 스타일 개선
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
    }
    .metric-card {
        background-color: #f0f2f6;
        padding: 1rem;
        border-radius: 0.5rem;
        text-align: center;
        box-shadow: 0 2px 4px rgba(0,0,0,0.1);
    }
    .success-box {
        background-color: #d4edda;
        border: 1px solid #c3e6cb;
        border-radius: 5px;
        padding: 1rem;
        margin: 1rem 0;
    }
    .error-box {
        background-color: #f8d7da;
        border: 1px solid #f5c6cb;
        border-radius: 5px;
        padding: 1rem;
        margin: 1rem 0;
    }
    .crypto-card {
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        color: white;
        padding: 1rem;
        border-radius: 10px;
        margin: 0.5rem 0;
    }
</style>
""", unsafe_allow_html=True)

# Groq 클라이언트 초기화 (새 모델 사용)
groq_client = None
if GROQ_AVAILABLE and st.secrets.get("GROQ_API_KEY"):
    groq_client = Groq(api_key=st.secrets["GROQ_API_KEY"])

# 세션 상태 초기화
if 'stock_list' not in st.session_state:
    st.session_state.stock_list = ['AAPL', 'GOOGL', 'MSFT']
if 'crypto_list' not in st.session_state:
    st.session_state.crypto_list = ['BTC-USD', 'ETH-USD']
if 'etf_list' not in st.session_state:
    st.session_state.etf_list = ['SPY', 'QQQ']
if 'analysis_results' not in st.session_state:
    st.session_state.analysis_results = {}
if 'price_predictions' not in st.session_state:
    st.session_state.price_predictions = {}
if 'portfolio' not in st.session_state:
    st.session_state.portfolio = {}

# 헤더
col1, col2, col3 = st.columns([1, 2, 1])
with col2:
    st.title("🤖 AI 기반 주식/암호화폐 분석")
    st.markdown("### 스마트한 투자 결정을 위한 종합 분석 플랫폼")

# 추천 밈코인 및 트렌딩 코인
TRENDING_CRYPTOS = {
    "인기 밈코인": ["DOGE-USD", "SHIB-USD", "PEPE-USD", "FLOKI-USD", "BONK-USD"],
    "AI 관련 코인": ["FET-USD", "AGIX-USD", "OCEAN-USD", "RNDR-USD"],
    "Layer 2": ["MATIC-USD", "ARB-USD", "OP-USD"],
    "DeFi": ["UNI-USD", "AAVE-USD", "SUSHI-USD"],
    "주요 코인": ["BTC-USD", "ETH-USD", "BNB-USD", "SOL-USD", "ADA-USD"]
}

# 사이드바
with st.sidebar:
    st.header("📊 포트폴리오 관리")
    
    # 자산 유형 선택
    asset_type = st.selectbox("자산 유형", ["주식", "암호화폐", "ETF"])
    
    # 자산 추가
    with st.form(f"add_{asset_type}_form"):
        if asset_type == "주식":
            new_asset = st.text_input("주식 심볼", placeholder="예: AAPL")
        elif asset_type == "암호화폐":
            st.caption("추천 밈코인: DOGE, SHIB, PEPE")
            new_asset = st.text_input("암호화폐 심볼", placeholder="예: BTC-USD")
        else:  # ETF
            new_asset = st.text_input("ETF 심볼", placeholder="예: SPY")
            
        add_button = st.form_submit_button("➕ 추가")
        
        if add_button and new_asset:
            symbol = new_asset.upper()
            if asset_type == "암호화폐" and not symbol.endswith("-USD"):
                symbol += "-USD"
                
            # 해당 리스트에 추가
            target_list = (st.session_state.stock_list if asset_type == "주식" 
                          else st.session_state.crypto_list if asset_type == "암호화폐"
                          else st.session_state.etf_list)
            
            if symbol not in target_list:
                try:
                    test_df = yf.Ticker(symbol).history(period="1d")
                    if not test_df.empty:
                        target_list.append(symbol)
                        st.success(f"✅ {symbol} 추가됨!")
                    else:
                        st.error(f"❌ {symbol}를 찾을 수 없습니다.")
                except:
                    st.error(f"❌ {symbol}는 유효하지 않은 심볼입니다.")
            else:
                st.warning("⚠️ 이미 목록에 있습니다.")
    
    # 트렌딩 암호화폐 추천
    if asset_type == "암호화폐":
        st.markdown("---")
        st.subheader("🔥 트렌딩 암호화폐")
        for category, cryptos in TRENDING_CRYPTOS.items():
            with st.expander(category):
                for crypto in cryptos:
                    if st.button(f"+ {crypto}", key=f"add_{crypto}"):
                        if crypto not in st.session_state.crypto_list:
                            st.session_state.crypto_list.append(crypto)
                            st.success(f"✅ {crypto} 추가됨!")
    
    st.markdown("---")
    
    # 자산 삭제
    all_assets = st.session_state.stock_list + st.session_state.crypto_list + st.session_state.etf_list
    if all_assets:
        st.subheader("자산 삭제")
        remove_asset = st.selectbox("삭제할 자산 선택", all_assets)
        if st.button("🗑️ 삭제"):
            # 해당 리스트에서 삭제
            if remove_asset in st.session_state.stock_list:
                st.session_state.stock_list.remove(remove_asset)
            elif remove_asset in st.session_state.crypto_list:
                st.session_state.crypto_list.remove(remove_asset)
            elif remove_asset in st.session_state.etf_list:
                st.session_state.etf_list.remove(remove_asset)
                
            if remove_asset in st.session_state.analysis_results:
                del st.session_state.analysis_results[remove_asset]
            st.success(f"✅ {remove_asset} 삭제됨!")
            st.rerun()
    
    st.markdown("---")
    
    # API 상태
    st.subheader("🔧 시스템 상태")
    if groq_client:
        st.success("✅ AI 분석 활성화")
    else:
        st.warning("⚠️ AI 분석 비활성화")
        st.caption("Groq API 키를 설정하면 AI 분석 기능을 사용할 수 있습니다.")

# 함수들
@st.cache_data(ttl=300)  # 5분 캐시
def get_stock_data(symbol, period="1mo"):
    """주식/암호화폐 데이터 가져오기"""
    try:
        stock = yf.Ticker(symbol)
        df = stock.history(period=period)
        info = stock.info
        return df, info
    except Exception as e:
        st.error(f"데이터 로드 실패: {str(e)}")
        return pd.DataFrame(), {}

@st.cache_data(ttl=600)
def get_crypto_metrics(symbol):
    """암호화폐 추가 지표 가져오기"""
    try:
        ticker = yf.Ticker(symbol)
        info = ticker.info
        
        metrics = {
            "market_cap": info.get('marketCap', 0),
            "volume_24h": info.get('volume24Hr', 0),
            "circulating_supply": info.get('circulatingSupply', 0),
            "total_supply": info.get('totalSupply', 0),
            "ath": info.get('fiftyTwoWeekHigh', 0),
            "atl": info.get('fiftyTwoWeekLow', 0),
        }
        return metrics
    except:
        return {}

def calculate_indicators(df):
    """기술적 지표 계산 (MACD 수정 포함)"""
    if df.empty or len(df) < 20:
        return df
    
    try:
        # RSI
        df['RSI'] = ta.momentum.RSIIndicator(df['Close'], window=14).rsi()
        
        # MACD - 수정된 버전
        if len(df) >= 26:  # MACD는 최소 26개 데이터 필요
            exp1 = df['Close'].ewm(span=12, adjust=False).mean()
            exp2 = df['Close'].ewm(span=26, adjust=False).mean()
            df['MACD'] = exp1 - exp2
            df['MACD_signal'] = df['MACD'].ewm(span=9, adjust=False).mean()
            df['MACD_diff'] = df['MACD'] - df['MACD_signal']
        else:
            df['MACD'] = np.nan
            df['MACD_signal'] = np.nan
            df['MACD_diff'] = np.nan
        
        # CCI
        df['CCI'] = ta.trend.CCIIndicator(df['High'], df['Low'], df['Close']).cci()
        
        # MFI
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
        
        # 추가 지표
        df['EMA_12'] = ta.trend.ema_indicator(df['Close'], window=12)
        df['EMA_26'] = ta.trend.ema_indicator(df['Close'], window=26)
        
        # Stochastic
        stoch = ta.momentum.StochasticOscillator(df['High'], df['Low'], df['Close'])
        df['Stoch_K'] = stoch.stoch()
        df['Stoch_D'] = stoch.stoch_signal()
        
        # ATR (Average True Range)
        df['ATR'] = ta.volatility.average_true_range(df['High'], df['Low'], df['Close'])
        
        # 암호화폐 전용 지표
        if any(crypto in df.index.name for crypto in ['BTC', 'ETH', 'DOGE', 'SHIB'] if df.index.name):
            # NVT Ratio 근사치 (Price / Volume ratio)
            df['PVR'] = df['Close'] / (df['Volume'] / 1000000)  # Volume을 백만 단위로
            
        return df
    except Exception as e:
        st.error(f"지표 계산 오류: {str(e)}")
        return df

def create_enhanced_chart(df, symbol):
    """향상된 인터랙티브 차트 생성"""
    fig = make_subplots(
        rows=6, cols=1,
        shared_xaxes=True,
        vertical_spacing=0.02,
        subplot_titles=('주가 및 이동평균', '거래량', 'RSI', 'MACD', 'Stochastic', 'MFI'),
        row_heights=[0.35, 0.1, 0.15, 0.15, 0.15, 0.1]
    )
    
    # 1. 주가 차트
    fig.add_trace(
        go.Candlestick(
            x=df.index,
            open=df['Open'],
            high=df['High'],
            low=df['Low'],
            close=df['Close'],
            name='주가',
            showlegend=False
        ),
        row=1, col=1
    )
    
    # 이동평균선
    if 'SMA_20' in df.columns:
        fig.add_trace(
            go.Scatter(x=df.index, y=df['SMA_20'], name='SMA 20', 
                      line=dict(color='orange', width=1)),
            row=1, col=1
        )
    if 'SMA_50' in df.columns and df['SMA_50'].notna().any():
        fig.add_trace(
            go.Scatter(x=df.index, y=df['SMA_50'], name='SMA 50', 
                      line=dict(color='blue', width=1)),
            row=1, col=1
        )
    
    # 볼린저 밴드
    if 'BB_upper' in df.columns:
        fig.add_trace(
            go.Scatter(x=df.index, y=df['BB_upper'], name='BB Upper', 
                      line=dict(color='rgba(250, 128, 114, 0.3)', dash='dash'),
                      showlegend=False),
            row=1, col=1
        )
        fig.add_trace(
            go.Scatter(x=df.index, y=df['BB_lower'], name='BB Lower', 
                      line=dict(color='rgba(144, 238, 144, 0.3)', dash='dash'),
                      fill='tonexty', fillcolor='rgba(200, 200, 200, 0.1)',
                      showlegend=False),
            row=1, col=1
        )
    
    # 2. 거래량
    colors = ['red' if df['Close'].iloc[i] < df['Open'].iloc[i] else 'green' 
              for i in range(len(df))]
    fig.add_trace(
        go.Bar(x=df.index, y=df['Volume'], name='거래량', 
               marker_color=colors, showlegend=False),
        row=2, col=1
    )
    
    # 3. RSI
    if 'RSI' in df.columns:
        fig.add_trace(
            go.Scatter(x=df.index, y=df['RSI'], name='RSI', 
                      line=dict(color='purple', width=2)),
            row=3, col=1
        )
        fig.add_hline(y=70, line_dash="dash", line_color="red", opacity=0.5, row=3, col=1)
        fig.add_hline(y=30, line_dash="dash", line_color="green", opacity=0.5, row=3, col=1)
        fig.add_hline(y=50, line_dash="dot", line_color="gray", opacity=0.3, row=3, col=1)
    
    # 4. MACD
    if 'MACD' in df.columns and not df['MACD'].isna().all():
        fig.add_trace(
            go.Scatter(x=df.index, y=df['MACD'], name='MACD', 
                      line=dict(color='blue', width=2)),
            row=4, col=1
        )
        if 'MACD_signal' in df.columns:
            fig.add_trace(
                go.Scatter(x=df.index, y=df['MACD_signal'], name='Signal', 
                          line=dict(color='red', width=2)),
                row=4, col=1
            )
        if 'MACD_diff' in df.columns:
            fig.add_trace(
                go.Bar(x=df.index, y=df['MACD_diff'], name='Histogram', 
                       marker_color='gray', opacity=0.3),
                row=4, col=1
            )
    
    # 5. Stochastic
    if 'Stoch_K' in df.columns:
        fig.add_trace(
            go.Scatter(x=df.index, y=df['Stoch_K'], name='%K', 
                      line=dict(color='blue', width=2)),
            row=5, col=1
        )
        if 'Stoch_D' in df.columns:
            fig.add_trace(
                go.Scatter(x=df.index, y=df['Stoch_D'], name='%D', 
                          line=dict(color='red', width=2)),
                row=5, col=1
            )
        fig.add_hline(y=80, line_dash="dash", line_color="red", opacity=0.5, row=5, col=1)
        fig.add_hline(y=20, line_dash="dash", line_color="green", opacity=0.5, row=5, col=1)
    
    # 6. MFI
    if 'MFI' in df.columns:
        fig.add_trace(
            go.Scatter(x=df.index, y=df['MFI'], name='MFI', 
                      line=dict(color='brown', width=2)),
            row=6, col=1
        )
        fig.add_hline(y=80, line_dash="dash", line_color="red", opacity=0.5, row=6, col=1)
        fig.add_hline(y=20, line_dash="dash", line_color="green", opacity=0.5, row=6, col=1)
    
    # 레이아웃 설정
    title = f"{symbol} 종합 기술적 분석 차트"
    if symbol.endswith('-USD'):
        title = f"🪙 {title}"
    
    fig.update_layout(
        title=title,
        xaxis_title="날짜",
        height=1200,
        showlegend=True,
        legend=dict(
            orientation="h",
            yanchor="bottom",
            y=1.02,
            xanchor="right",
            x=1
        ),
        hovermode='x unified'
    )
    
    fig.update_xaxes(rangeslider_visible=False)
    
    return fig

def perform_crypto_analysis(df, symbol, metrics):
    """암호화폐 전용 분석"""
    if df.empty:
        return "데이터가 부족하여 분석을 수행할 수 없습니다."
    
    latest = df.iloc[-1]
    
    # 기본 분석
    analysis = f"""
## 🪙 {symbol} 암호화폐 분석 결과

### 📊 시장 데이터
- **현재가**: ${latest['Close']:.4f}
- **24시간 거래량**: ${latest['Volume']:,.0f}
- **시가총액**: ${metrics.get('market_cap', 0):,.0f}
- **52주 최고가**: ${metrics.get('ath', 0):.4f}
- **52주 최저가**: ${metrics.get('atl', 0):.4f}
"""
    
    # 온체인 유사 지표
    if len(df) >= 7:
        week_ago = df['Close'].iloc[-8] if len(df) >= 8 else df['Close'].iloc[0]
        week_change = ((latest['Close'] - week_ago) / week_ago) * 100
        
        # 거래량 분석
        avg_volume = df['Volume'].tail(30).mean()
        volume_ratio = latest['Volume'] / avg_volume
        
        analysis += f"""
### 📈 추세 분석
- **7일 변화율**: {week_change:.2f}%
- **거래량 비율**: {volume_ratio:.2f}x (30일 평균 대비)
- **변동성**: {'높음' if df['Close'].pct_change().std() > 0.05 else '보통' if df['Close'].pct_change().std() > 0.02 else '낮음'}
"""
    
    # 밈코인 특별 분석
    if any(meme in symbol for meme in ['DOGE', 'SHIB', 'PEPE', 'FLOKI', 'BONK']):
        analysis += """
### 🚀 밈코인 특별 지표
- **커뮤니티 강도**: 소셜 미디어 활동 모니터링 필요
- **고래 움직임**: 대량 거래 주시 필요
- **리스크**: 매우 높음 - 변동성 극심
- **투자 전략**: 단기 트레이딩 또는 소액 투자 권장
"""
    
    return analysis

def perform_ai_analysis(df, symbol, info, asset_type="주식"):
    """AI 기반 심층 분석"""
    if not groq_client:
        if asset_type == "암호화폐":
            return perform_crypto_analysis(df, symbol, get_crypto_metrics(symbol))
        return perform_technical_analysis(df, symbol)
    
    try:
        latest = df.iloc[-1]
        
        # 변동성 계산
        volatility = df['Close'].pct_change().std() * np.sqrt(252) * 100  # 연간 변동성
        
        # 추가 계산
        sma_20 = df['SMA_20'].iloc[-1] if 'SMA_20' in df.columns else 0
        sma_50 = df['SMA_50'].iloc[-1] if 'SMA_50' in df.columns and not pd.isna(df['SMA_50'].iloc[-1]) else 0
        
        # 지표 값들 안전하게 가져오기
        rsi_val = f"{latest.get('RSI', 0):.2f}" if 'RSI' in latest and not pd.isna(latest.get('RSI')) else "N/A"
        macd_val = f"{latest.get('MACD', 0):.2f}" if 'MACD' in latest and not pd.isna(latest.get('MACD')) else "N/A"
        
        asset_type_kr = "암호화폐" if asset_type == "암호화폐" else "ETF" if asset_type == "ETF" else "주식"
        
        prompt = f"""
        당신은 한국의 전문 투자 분석가입니다. 다음 {asset_type_kr} 데이터를 한국어로 분석해주세요:
        
        [{symbol} 기본 정보]
        - 자산 유형: {asset_type_kr}
        - 현재가: ${latest['Close']:.2f}
        - 거래량: {latest['Volume']:,.0f}
        - 변동성: {volatility:.2f}%
        
        [기술적 지표]
        - RSI: {rsi_val}
        - MACD: {macd_val}
        - 20일 이동평균: ${sma_20:.2f}
        
        다음을 한국어로 분석해주세요:
        1. 현재 기술적 상태 평가
        2. 단기(1주) 및 중기(1개월) 전망
        3. 주요 매매 신호
        4. 리스크 요인
        5. 구체적인 투자 전략
        
        {'특히 밈코인의 경우 극심한 변동성과 리스크를 강조해주세요.' if asset_type == '암호화폐' and any(meme in symbol for meme in ['DOGE', 'SHIB', 'PEPE']) else ''}
        
        전문적이면서도 이해하기 쉽게 설명해주세요.
        """
        
        completion = groq_client.chat.completions.create(
            model="llama3-8b-8192",
            messages=[
                {
                    "role": "system",
                    "content": "당신은 한국의 20년 경력 투자 전문가입니다. 주식, 암호화폐, ETF 모든 자산에 정통하며, 기술적 분석과 리스크 관리에 전문성을 가지고 있습니다. 항상 한국어로 답변합니다."
                },
                {
                    "role": "user",
                    "content": prompt
                }
            ],
            temperature=0.7,
            max_tokens=2000
        )
        
        return f"## 🤖 AI 심층 분석 결과\n\n{completion.choices[0].message.content}"
        
    except Exception as e:
        st.error(f"AI 분석 중 오류 발생: {str(e)}")
        if asset_type == "암호화폐":
            return perform_crypto_analysis(df, symbol, get_crypto_metrics(symbol))
        return perform_technical_analysis(df, symbol)

def perform_technical_analysis(df, symbol):
    """기본 기술적 분석"""
    if df.empty or 'RSI' not in df.columns:
        return "데이터가 부족하여 분석을 수행할 수 없습니다."
    
    latest = df.iloc[-1]
    
    # 각 지표 분석
    rsi_val = latest.get('RSI', 50)
    rsi_signal = "과매수" if rsi_val > 70 else "과매도" if rsi_val < 30 else "중립"
    
    # MACD 분석 - NaN 체크 추가
    macd_val = latest.get('MACD', 0)
    macd_signal_val = latest.get('MACD_signal', 0)
    if pd.isna(macd_val) or pd.isna(macd_signal_val):
        macd_signal = "데이터 부족"
    else:
        macd_signal = "매수" if macd_val > macd_signal_val else "매도"
    
    cci_val = latest.get('CCI', 0)
    cci_signal = "과매수" if cci_val > 100 else "과매도" if cci_val < -100 else "중립"
    
    mfi_val = latest.get('MFI', 50)
    mfi_signal = "과매수" if mfi_val > 80 else "과매도" if mfi_val < 20 else "중립"
    
    analysis = f"""
## 📊 {symbol} 기술적 분석 결과

### 📈 현재 지표값
- **RSI**: {rsi_val:.2f} - {rsi_signal} 상태
- **MACD**: {macd_signal} 신호
- **CCI**: {cci_val:.2f} - {cci_signal} 상태
- **MFI**: {mfi_val:.2f} - {mfi_signal} 상태

### 💡 종합 의견
"""
    
    # 점수 계산
    score = 0
    if 30 < rsi_val < 70: score += 1
    if macd_signal == "매수": score += 1
    if -100 < cci_val < 100: score += 1
    if 20 < mfi_val < 80: score += 1
    
    if score >= 3:
        analysis += "**긍정적** 📈 - 대부분의 지표가 긍정적인 신호를 보이고 있습니다."
    elif score >= 2:
        analysis += "**중립적** ➡️ - 혼재된 신호를 보이고 있어 신중한 접근이 필요합니다."
    else:
        analysis += "**부정적** 📉 - 대부분의 지표가 부정적인 신호를 보이고 있습니다."
    
    return analysis

# 메인 화면
all_assets = st.session_state.stock_list + st.session_state.crypto_list + st.session_state.etf_list

if all_assets:
    # 탭 생성
    tab_titles = ["📊 전체 대시보드", "📈 주식", "🪙 암호화폐", "📦 ETF"] + [f"📌 {asset}" for asset in all_assets]
    tabs = st.tabs(tab_titles)
    
    # 전체 대시보드 탭
    with tabs[0]:
        st.header("📊 전체 포트폴리오 대시보드")
        
        # 자산 유형별 요약
        col1, col2, col3 = st.columns(3)
        with col1:
            st.metric("주식", len(st.session_state.stock_list), f"{len(st.session_state.stock_list)} 종목")
        with col2:
            st.metric("암호화폐", len(st.session_state.crypto_list), f"{len(st.session_state.crypto_list)} 종목")
        with col3:
            st.metric("ETF", len(st.session_state.etf_list), f"{len(st.session_state.etf_list)} 종목")
        
        # 전체 자산 미니 카드
        st.subheader("📈 전체 자산 현황")
        cols = st.columns(3)
        for i, symbol in enumerate(all_assets):
            with cols[i % 3]:
                df, info = get_stock_data(symbol, "5d")
                if not df.empty:
                    current = df['Close'].iloc[-1]
                    prev = df['Close'].iloc[-2] if len(df) > 1 else current
                    change = ((current - prev) / prev) * 100 if prev != 0 else 0
                    
                    # 자산 유형 아이콘
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
    
    # 주식 탭
    with tabs[1]:
        st.header("📈 주식 포트폴리오")
        if st.session_state.stock_list:
            for symbol in st.session_state.stock_list:
                with st.expander(f"{symbol} 요약", expanded=True):
                    df, info = get_stock_data(symbol, "1mo")
                    if not df.empty:
                        col1, col2 = st.columns([2, 1])
                        with col1:
                            st.metric("현재가", f"${df['Close'].iloc[-1]:.2f}")
                        with col2:
                            if st.button(f"상세 분석 →", key=f"goto_{symbol}"):
                                st.write(f"{symbol} 탭으로 이동하세요")
        else:
            st.info("주식을 추가하세요")
    
    # 암호화폐 탭
    with tabs[2]:
        st.header("🪙 암호화폐 포트폴리오")
        if st.session_state.crypto_list:
            # 온체인 데이터 요약
            st.subheader("🔗 온체인 데이터 기반 분석")
            for symbol in st.session_state.crypto_list:
                with st.expander(f"{symbol} 온체인 분석", expanded=True):
                    df, info = get_stock_data(symbol, "1mo")
                    if not df.empty:
                        metrics = get_crypto_metrics(symbol)
                        col1, col2, col3 = st.columns(3)
                        with col1:
                            st.metric("현재가", f"${df['Close'].iloc[-1]:.6f}")
                        with col2:
                            st.metric("24시간 거래량", f"${df['Volume'].iloc[-1]:,.0f}")
                        with col3:
                            week_change = ((df['Close'].iloc[-1] - df['Close'].iloc[-8]) / df['Close'].iloc[-8] * 100) if len(df) >= 8 else 0
                            st.metric("7일 변화율", f"{week_change:.2f}%")
                        
                        # 밈코인 특별 표시
                        if any(meme in symbol for meme in ['DOGE', 'SHIB', 'PEPE']):
                            st.warning("⚠️ 밈코인 - 높은 변동성 주의!")
        else:
            st.info("암호화폐를 추가하세요")
    
    # ETF 탭
    with tabs[3]:
        st.header("📦 ETF 포트폴리오")
        if st.session_state.etf_list:
            for symbol in st.session_state.etf_list:
                with st.expander(f"{symbol} 요약", expanded=True):
                    df, info = get_stock_data(symbol, "1mo")
                    if not df.empty:
                        col1, col2 = st.columns([2, 1])
                        with col1:
                            st.metric("현재가", f"${df['Close'].iloc[-1]:.2f}")
                        with col2:
                            if st.button(f"상세 분석 →", key=f"goto_etf_{symbol}"):
                                st.write(f"{symbol} 탭으로 이동하세요")
        else:
            st.info("ETF를 추가하세요")
    
    # 개별 자산 탭들
    for idx, symbol in enumerate(all_assets):
        with tabs[idx + 4]:
            # 자산 유형 판별
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
                if st.button("🔄 새로고침", key=f"refresh_{symbol}"):
                    st.cache_data.clear()
                    st.rerun()
            
            # 데이터 로드
            with st.spinner(f"{symbol} 데이터 로딩 중..."):
                df, info = get_stock_data(symbol, period)
            
            if not df.empty:
                # 지표 계산
                df = calculate_indicators(df)
                
                # 기본 정보
                if asset_type == "암호화폐":
                    metrics = get_crypto_metrics(symbol)
                    col1, col2, col3, col4 = st.columns(4)
                    with col1:
                        st.metric("현재가", f"${df['Close'].iloc[-1]:.6f}")
                    with col2:
                        st.metric("24시간 거래량", f"${df['Volume'].iloc[-1]:,.0f}")
                    with col3:
                        st.metric("시가총액", f"${metrics.get('market_cap', 0):,.0f}")
                    with col4:
                        st.metric("52주 최고가", f"${metrics.get('ath', 0):.6f}")
                else:
                    col1, col2, col3, col4 = st.columns(4)
                    with col1:
                        st.metric("현재가", f"${df['Close'].iloc[-1]:.2f}")
                    with col2:
                        change = ((df['Close'].iloc[-1] - df['Close'].iloc[-2]) / df['Close'].iloc[-2] * 100)
                        st.metric("변동률", f"{change:.2f}%")
                    with col3:
                        st.metric("거래량", f"{df['Volume'].iloc[-1]:,.0f}")
                    with col4:
                        if info.get('marketCap'):
                            st.metric("시가총액", f"${info.get('marketCap', 0):,.0f}")
                
                # 차트
                st.plotly_chart(create_enhanced_chart(df, symbol), use_container_width=True)
                
                # 최신 지표
                st.subheader("📊 최신 기술적 지표")
                col1, col2, col3, col4, col5, col6 = st.columns(6)
                
                with col1:
                    rsi_val = df['RSI'].iloc[-1] if 'RSI' in df.columns else 50
                    st.metric(
                        "RSI",
                        f"{rsi_val:.2f}",
                        delta="과매수" if rsi_val > 70 else "과매도" if rsi_val < 30 else "정상"
                    )
                
                with col2:
                    if 'MACD' in df.columns and not pd.isna(df['MACD'].iloc[-1]):
                        macd_val = df['MACD'].iloc[-1]
                        st.metric("MACD", f"{macd_val:.2f}", delta="신호 확인")
                    else:
                        st.metric("MACD", "N/A", delta="데이터 부족")
                
                with col3:
                    cci_val = df['CCI'].iloc[-1] if 'CCI' in df.columns else 0
                    st.metric(
                        "CCI",
                        f"{cci_val:.2f}",
                        delta="과매수" if cci_val > 100 else "과매도" if cci_val < -100 else "정상"
                    )
                
                with col4:
                    mfi_val = df['MFI'].iloc[-1] if 'MFI' in df.columns else 50
                    st.metric(
                        "MFI",
                        f"{mfi_val:.2f}",
                        delta="과매수" if mfi_val > 80 else "과매도" if mfi_val < 20 else "정상"
                    )
                
                with col5:
                    if 'Stoch_K' in df.columns:
                        stoch_val = df['Stoch_K'].iloc[-1]
                        st.metric(
                            "Stoch %K",
                            f"{stoch_val:.2f}",
                            delta="과매수" if stoch_val > 80 else "과매도" if stoch_val < 20 else "정상"
                        )
                
                with col6:
                    if 'ATR' in df.columns:
                        atr_val = df['ATR'].iloc[-1]
                        atr_pct = (atr_val / df['Close'].iloc[-1]) * 100
                        st.metric(
                            "ATR",
                            f"{atr_val:.2f}",
                            delta=f"{atr_pct:.1f}% 변동성"
                        )
                
                # 분석 버튼
                st.markdown("---")
                col1, col2, col3 = st.columns(3)
                
                with col1:
                    if st.button("📊 기술적 분석", key=f"tech_{symbol}"):
                        with st.spinner("분석 중..."):
                            if asset_type == "암호화폐":
                                analysis = perform_crypto_analysis(df, symbol, get_crypto_metrics(symbol))
                            else:
                                analysis = perform_technical_analysis(df, symbol)
                            st.session_state.analysis_results[f"{symbol}_tech"] = analysis
                
                with col2:
                    if st.button("🤖 AI 심층 분석", key=f"ai_{symbol}"):
                        with st.spinner("AI 분석 중..."):
                            analysis = perform_ai_analysis(df, symbol, info, asset_type)
                            st.session_state.analysis_results[f"{symbol}_ai"] = analysis
                
                with col3:
                    if st.button("🔄 분석 초기화", key=f"clear_{symbol}"):
                        keys_to_remove = [k for k in st.session_state.analysis_results.keys() if k.startswith(symbol)]
                        for key in keys_to_remove:
                            del st.session_state.analysis_results[key]
                        st.success("분석 결과가 초기화되었습니다.")
                
                # 분석 결과 표시
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
    st.info("👈 왼쪽 사이드바에서 주식, 암호화폐, ETF를 추가해주세요!")
    
    # 빠른 시작 가이드
    with st.expander("🚀 빠른 시작 가이드", expanded=True):
        st.markdown("""
        ### 📈 주식 추천
        - **테크 주식**: AAPL, GOOGL, MSFT, NVDA
        - **한국 주식**: 005930.KS (삼성전자), 000660.KS (SK하이닉스)
        
        ### 🪙 암호화폐 추천
        - **주요 코인**: BTC-USD, ETH-USD
        - **인기 밈코인**: DOGE-USD, SHIB-USD, PEPE-USD
        - **AI 코인**: FET-USD, RNDR-USD
        
        ### 📦 ETF 추천
        - **미국 주요**: SPY, QQQ, DIA
        - **섹터 ETF**: XLK (기술), XLF (금융)
        """)

# 푸터
st.markdown("---")
col1, col2, col3 = st.columns(3)
with col2:
    st.markdown("### 💡 AI 투자 분석 플랫폼")
    st.caption("주식, 암호화폐, ETF 종합 분석")
    st.caption(f"마지막 업데이트: {datetime.now().strftime('%Y-%m-%d %H:%M')}")
