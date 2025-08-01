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
try:
    from groq import Groq
    GROQ_AVAILABLE = True
except ImportError:
    GROQ_AVAILABLE = False

# 페이지 설정
st.set_page_config(
    page_title="AI 주식 분석 플랫폼",
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
</style>
""", unsafe_allow_html=True)

# Groq 클라이언트 초기화 (새 모델 사용)
groq_client = None
if GROQ_AVAILABLE and st.secrets.get("GROQ_API_KEY"):
    groq_client = Groq(api_key=st.secrets["GROQ_API_KEY"])

# 세션 상태 초기화
if 'stock_list' not in st.session_state:
    st.session_state.stock_list = ['AAPL', 'GOOGL', 'MSFT', 'AMZN', 'TSLA']
if 'analysis_results' not in st.session_state:
    st.session_state.analysis_results = {}
if 'price_predictions' not in st.session_state:
    st.session_state.price_predictions = {}
if 'portfolio' not in st.session_state:
    st.session_state.portfolio = {}

# 헤더
col1, col2, col3 = st.columns([1, 2, 1])
with col2:
    st.title("🤖 AI 기반 실시간 주식 분석")
    st.markdown("### 스마트한 투자 결정을 위한 종합 분석 플랫폼")

# 사이드바
with st.sidebar:
    st.header("📊 주식 관리")
    
    # 주식 추가
    with st.form("add_stock_form"):
        new_stock = st.text_input("주식 심볼 추가", placeholder="예: NVDA")
        add_button = st.form_submit_button("➕ 추가")
        
        if add_button and new_stock:
            symbol = new_stock.upper()
            if symbol not in st.session_state.stock_list:
                # 유효성 검사
                try:
                    test_df = yf.Ticker(symbol).history(period="1d")
                    if not test_df.empty:
                        st.session_state.stock_list.append(symbol)
                        st.success(f"✅ {symbol} 추가됨!")
                    else:
                        st.error(f"❌ {symbol}를 찾을 수 없습니다.")
                except:
                    st.error(f"❌ {symbol}는 유효하지 않은 심볼입니다.")
            else:
                st.warning("⚠️ 이미 목록에 있습니다.")
    
    st.markdown("---")
    
    # 주식 삭제
    if st.session_state.stock_list:
        st.subheader("주식 삭제")
        remove_stock = st.selectbox("삭제할 주식 선택", st.session_state.stock_list)
        if st.button("🗑️ 삭제"):
            st.session_state.stock_list.remove(remove_stock)
            if remove_stock in st.session_state.analysis_results:
                del st.session_state.analysis_results[remove_stock]
            if remove_stock in st.session_state.price_predictions:
                del st.session_state.price_predictions[remove_stock]
            st.success(f"✅ {remove_stock} 삭제됨!")
            st.rerun()
    
    st.markdown("---")
    
    # 포트폴리오 관리
    st.subheader("💼 포트폴리오 관리")
    if st.session_state.stock_list:
        selected_stock = st.selectbox("주식 선택", st.session_state.stock_list)
        shares = st.number_input("보유 주식 수", min_value=0, value=0)
        if st.button("💾 포트폴리오 업데이트"):
            if shares > 0:
                st.session_state.portfolio[selected_stock] = shares
                st.success(f"✅ {selected_stock}: {shares}주 저장됨!")
            elif selected_stock in st.session_state.portfolio:
                del st.session_state.portfolio[selected_stock]
                st.success(f"✅ {selected_stock} 포트폴리오에서 제거됨!")
    
    # 포트폴리오 현황
    if st.session_state.portfolio:
        st.markdown("### 📊 포트폴리오 현황")
        for stock, shares in st.session_state.portfolio.items():
            st.caption(f"{stock}: {shares}주")
    
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
    """주식 데이터 가져오기"""
    try:
        stock = yf.Ticker(symbol)
        df = stock.history(period=period)
        info = stock.info
        return df, info
    except Exception as e:
        st.error(f"데이터 로드 실패: {str(e)}")
        return pd.DataFrame(), {}

@st.cache_data(ttl=600)  # 10분 캐시
def get_stock_news(symbol):
    """주식 관련 뉴스 가져오기"""
    try:
        stock = yf.Ticker(symbol)
        news = stock.news
        return news[:5] if news else []  # 최신 5개 뉴스만
    except:
        return []

def calculate_indicators(df):
    """기술적 지표 계산"""
    if df.empty or len(df) < 20:
        return df
    
    try:
        # RSI
        df['RSI'] = ta.momentum.RSIIndicator(df['Close'], window=14).rsi()
        
        # MACD
        macd = ta.trend.MACD(df['Close'])
        df['MACD'] = macd.macd()
        df['MACD_signal'] = macd.macd_signal()
        df['MACD_diff'] = macd.macd_diff()
        
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
        
        return df
    except Exception as e:
        st.error(f"지표 계산 오류: {str(e)}")
        return df

def predict_price(df, days=7):
    """간단한 가격 예측 (이동평균 기반)"""
    if len(df) < 50:
        return None
    
    try:
        # 최근 추세 계산
        recent_prices = df['Close'].tail(20).values
        x = np.arange(len(recent_prices))
        z = np.polyfit(x, recent_prices, 1)
        p = np.poly1d(z)
        
        # 예측
        future_x = np.arange(len(recent_prices), len(recent_prices) + days)
        predictions = p(future_x)
        
        # 예측값이 음수가 되지 않도록 보정
        predictions = np.maximum(predictions, df['Close'].min() * 0.5)
        
        return predictions
    except:
        return None

def calculate_portfolio_value(portfolio, current_prices):
    """포트폴리오 가치 계산"""
    total_value = 0
    portfolio_details = []
    
    for symbol, shares in portfolio.items():
        if symbol in current_prices:
            value = shares * current_prices[symbol]
            total_value += value
            portfolio_details.append({
                'Symbol': symbol,
                'Shares': shares,
                'Price': current_prices[symbol],
                'Value': value
            })
    
    return total_value, portfolio_details

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
    if 'SMA_200' in df.columns and df['SMA_200'].notna().any():
        fig.add_trace(
            go.Scatter(x=df.index, y=df['SMA_200'], name='SMA 200', 
                      line=dict(color='red', width=1)),
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
    if 'MACD' in df.columns:
        fig.add_trace(
            go.Scatter(x=df.index, y=df['MACD'], name='MACD', 
                      line=dict(color='blue', width=2)),
            row=4, col=1
        )
        fig.add_trace(
            go.Scatter(x=df.index, y=df['MACD_signal'], name='Signal', 
                      line=dict(color='red', width=2)),
            row=4, col=1
        )
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
    fig.update_layout(
        title=f"{symbol} 종합 기술적 분석 차트",
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

def generate_pdf_report(df, symbol, info):
    """PDF 리포트 생성"""
    buffer = BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=letter)
    story = []
    
    styles = getSampleStyleSheet()
    title_style = styles['Title']
    heading_style = styles['Heading2']
    normal_style = styles['Normal']
    
    # 제목
    story.append(Paragraph(f"{symbol} 주식 종합 분석 리포트", title_style))
    story.append(Spacer(1, 12))
    
    # 생성 날짜
    story.append(Paragraph(f"생성일: {datetime.now().strftime('%Y-%m-%d %H:%M')}", normal_style))
    story.append(Spacer(1, 20))
    
    # 기본 정보
    story.append(Paragraph("📊 기본 정보", heading_style))
    if info:
        basic_info = [
            ["회사명", info.get('longName', 'N/A')],
            ["섹터", info.get('sector', 'N/A')],
            ["산업", info.get('industry', 'N/A')],
            ["시가총액", f"${info.get('marketCap', 0):,.0f}" if info.get('marketCap') else 'N/A'],
            ["52주 최고가", f"${info.get('fiftyTwoWeekHigh', 0):.2f}" if info.get('fiftyTwoWeekHigh') else 'N/A'],
            ["52주 최저가", f"${info.get('fiftyTwoWeekLow', 0):.2f}" if info.get('fiftyTwoWeekLow') else 'N/A']
        ]
        basic_table = Table(basic_info, colWidths=[100, 300])
        basic_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, -1), colors.beige),
            ('TEXTCOLOR', (0, 0), (-1, -1), colors.black),
            ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
            ('FONTNAME', (0, 0), (-1, -1), 'Helvetica'),
            ('FONTSIZE', (0, 0), (-1, -1), 10),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 12),
            ('GRID', (0, 0), (-1, -1), 1, colors.black)
        ]))
        story.append(basic_table)
    story.append(Spacer(1, 20))
    
    # 가격 정보
    story.append(Paragraph("💰 가격 정보", heading_style))
    current_price = df['Close'].iloc[-1]
    prev_close = df['Close'].iloc[-2] if len(df) > 1 else current_price
    change = current_price - prev_close
    change_pct = (change / prev_close) * 100 if prev_close != 0 else 0
    
    # 52주 고저
    high_52w = df['High'].tail(252).max() if len(df) >= 252 else df['High'].max()
    low_52w = df['Low'].tail(252).min() if len(df) >= 252 else df['Low'].min()
    
    price_info = [
        ["현재가", f"${current_price:.2f}"],
        ["전일 종가", f"${prev_close:.2f}"],
        ["변동", f"${change:.2f} ({change_pct:+.2f}%)"],
        ["거래량", f"{df['Volume'].iloc[-1]:,.0f}"],
        ["일일 범위", f"${df['Low'].iloc[-1]:.2f} - ${df['High'].iloc[-1]:.2f}"],
        ["52주 범위", f"${low_52w:.2f} - ${high_52w:.2f}"]
    ]
    price_table = Table(price_info, colWidths=[100, 300])
    price_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, -1), colors.lightblue),
        ('TEXTCOLOR', (0, 0), (-1, -1), colors.black),
        ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
        ('FONTNAME', (0, 0), (-1, -1), 'Helvetica'),
        ('FONTSIZE', (0, 0), (-1, -1), 10),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 12),
        ('GRID', (0, 0), (-1, -1), 1, colors.black)
    ]))
    story.append(price_table)
    story.append(Spacer(1, 20))
    
    # 기술적 지표
    story.append(Paragraph("📈 기술적 지표 (최신값)", heading_style))
    indicators = []
    if 'RSI' in df.columns and not pd.isna(df['RSI'].iloc[-1]):
        indicators.append(["RSI (14)", f"{df['RSI'].iloc[-1]:.2f}"])
    if 'MACD' in df.columns and not pd.isna(df['MACD'].iloc[-1]):
        indicators.append(["MACD", f"{df['MACD'].iloc[-1]:.2f}"])
        indicators.append(["MACD Signal", f"{df['MACD_signal'].iloc[-1]:.2f}"])
    if 'CCI' in df.columns and not pd.isna(df['CCI'].iloc[-1]):
        indicators.append(["CCI", f"{df['CCI'].iloc[-1]:.2f}"])
    if 'MFI' in df.columns and not pd.isna(df['MFI'].iloc[-1]):
        indicators.append(["MFI", f"{df['MFI'].iloc[-1]:.2f}"])
    if 'ATR' in df.columns and not pd.isna(df['ATR'].iloc[-1]):
        indicators.append(["ATR", f"{df['ATR'].iloc[-1]:.2f}"])
    
    if indicators:
        indicators_table = Table(indicators, colWidths=[100, 300])
        indicators_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, -1), colors.lightyellow),
            ('TEXTCOLOR', (0, 0), (-1, -1), colors.black),
            ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
            ('FONTNAME', (0, 0), (-1, -1), 'Helvetica'),
            ('FONTSIZE', (0, 0), (-1, -1), 10),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 12),
            ('GRID', (0, 0), (-1, -1), 1, colors.black)
        ]))
        story.append(indicators_table)
    
    doc.build(story)
    buffer.seek(0)
    
    return buffer

def perform_technical_analysis(df, symbol):
    """기본 기술적 분석"""
    if df.empty or 'RSI' not in df.columns:
        return "데이터가 부족하여 분석을 수행할 수 없습니다."
    
    latest = df.iloc[-1]
    
    # 각 지표 분석
    rsi_val = latest.get('RSI', 50)
    rsi_signal = "과매수" if rsi_val > 70 else "과매도" if rsi_val < 30 else "중립"
    
    macd_val = latest.get('MACD', 0)
    macd_signal_val = latest.get('MACD_signal', 0)
    macd_signal = "매수" if macd_val > macd_signal_val else "매도"
    
    cci_val = latest.get('CCI', 0)
    cci_signal = "과매수" if cci_val > 100 else "과매도" if cci_val < -100 else "중립"
    
    mfi_val = latest.get('MFI', 50)
    mfi_signal = "과매수" if mfi_val > 80 else "과매도" if mfi_val < 20 else "중립"
    
    # Stochastic 분석
    stoch_k = latest.get('Stoch_K', 50)
    stoch_d = latest.get('Stoch_D', 50)
    stoch_signal = "과매수" if stoch_k > 80 else "과매도" if stoch_k < 20 else "중립"
    
    # 추세 분석
    sma_20 = df['SMA_20'].iloc[-1] if 'SMA_20' in df.columns else latest['Close']
    sma_50 = df['SMA_50'].iloc[-1] if 'SMA_50' in df.columns and not pd.isna(df['SMA_50'].iloc[-1]) else sma_20
    
    if latest['Close'] > sma_20 > sma_50:
        trend = "강한 상승"
    elif latest['Close'] > sma_20:
        trend = "상승"
    elif latest['Close'] < sma_20 < sma_50:
        trend = "강한 하락"
    else:
        trend = "하락"
    
    # 볼린저 밴드 분석
    bb_position = ""
    if 'BB_upper' in df.columns and 'BB_lower' in df.columns:
        if latest['Close'] > latest['BB_upper']:
            bb_position = "상단 돌파 (과매수 신호)"
        elif latest['Close'] < latest['BB_lower']:
            bb_position = "하단 돌파 (과매도 신호)"
        else:
            bb_width = latest['BB_upper'] - latest['BB_lower']
            bb_position = f"밴드 내부 (변동성: {'높음' if bb_width > df['Close'].mean() * 0.1 else '낮음'})"
    
    analysis = f"""
## 📊 {symbol} 기술적 분석 결과

### 📈 현재 지표값
- **RSI (14)**: {rsi_val:.2f} - {rsi_signal} 상태
- **MACD**: {macd_signal} 신호 (MACD: {macd_val:.2f}, Signal: {macd_signal_val:.2f})
- **CCI**: {cci_val:.2f} - {cci_signal} 상태
- **MFI**: {mfi_val:.2f} - {mfi_signal} 상태
- **Stochastic**: %K: {stoch_k:.2f}, %D: {stoch_d:.2f} - {stoch_signal} 상태

### 📉 추세 및 이동평균
- **현재 추세**: {trend}
- **현재가**: ${latest['Close']:.2f}
- **20일 이동평균**: ${sma_20:.2f}
- **50일 이동평균**: ${sma_50:.2f}
- **볼린저 밴드**: {bb_position}

### 💡 종합 의견
"""
    
    # 점수 계산
    score = 0
    signals = []
    
    if 30 < rsi_val < 70: 
        score += 1
        signals.append("RSI 정상")
    elif rsi_val <= 30:
        signals.append("RSI 과매도 (반등 가능)")
    else:
        signals.append("RSI 과매수 (조정 가능)")
    
    if macd_signal == "매수": 
        score += 1
        signals.append("MACD 매수 신호")
    else:
        signals.append("MACD 매도 신호")
    
    if -100 < cci_val < 100: 
        score += 1
        signals.append("CCI 정상")
    
    if 20 < mfi_val < 80: 
        score += 1
        signals.append("MFI 정상")
    
    if trend in ["상승", "강한 상승"]: 
        score += 1
        signals.append(f"추세 {trend}")
    
    if 20 < stoch_k < 80:
        score += 1
        signals.append("Stochastic 정상")
    
    # 종합 평가
    if score >= 5:
        analysis += "**매우 긍정적** 📈 - 대부분의 지표가 긍정적인 신호를 보이고 있습니다.\n"
        analysis += "- 매수 타이밍으로 적합할 수 있습니다.\n"
    elif score >= 3:
        analysis += "**중립적** ➡️ - 혼재된 신호를 보이고 있어 신중한 접근이 필요합니다.\n"
        analysis += "- 추가적인 확인 신호를 기다리는 것이 좋습니다.\n"
    else:
        analysis += "**부정적** 📉 - 대부분의 지표가 부정적인 신호를 보이고 있습니다.\n"
        analysis += "- 매수를 보류하거나 리스크 관리가 필요합니다.\n"
    
    # 주요 신호
    analysis += f"\n### 🔍 주요 신호\n"
    for signal in signals:
        analysis += f"- {signal}\n"
    
    # 리스크 요인
    risks = []
    if rsi_val > 70:
        risks.append("RSI 과매수 구간 - 단기 조정 가능성")
    elif rsi_val < 30:
        risks.append("RSI 과매도 구간 - 추가 하락 가능성")
    if mfi_val > 80:
        risks.append("MFI 과매수 구간 - 매도 압력 증가")
    elif mfi_val < 20:
        risks.append("MFI 과매도 구간 - 극단적 매도 상태")
    if stoch_k > 80:
        risks.append("Stochastic 과매수 - 단기 조정 가능")
    
    if risks:
        analysis += f"\n### ⚠️ 리스크 요인\n"
        for risk in risks:
            analysis += f"- {risk}\n"
    
    # 투자 제안
    analysis += f"\n### 💰 투자 제안\n"
    if score >= 5:
        analysis += "- 분할 매수 전략을 고려해보세요.\n"
        analysis += "- 목표가와 손절가를 명확히 설정하세요.\n"
    elif score >= 3:
        analysis += "- 관망하며 추가 신호를 기다리세요.\n"
        analysis += "- 소량 매수 후 추이를 지켜보는 것도 가능합니다.\n"
    else:
        analysis += "- 현재는 매수를 보류하는 것이 좋습니다.\n"
        analysis += "- 기술적 지표가 개선될 때까지 기다리세요.\n"
    
    analysis += "\n\n*※ 이 분석은 기술적 지표만을 기반으로 하며, 투자 결정 시 펀더멘털 분석과 시장 상황도 함께 고려하시기 바랍니다.*"
    
    return analysis

def perform_ai_analysis(df, symbol, info):
    """AI 기반 심층 분석"""
    if not groq_client:
        return perform_technical_analysis(df, symbol)
    
    try:
        latest = df.iloc[-1]
        
        # 변동성 계산
        volatility = df['Close'].pct_change().std() * np.sqrt(252) * 100  # 연간 변동성
        
        prompt = f"""
        다음은 {symbol} ({info.get('longName', symbol)}) 주식의 종합 분석 데이터입니다:
        
        [기본 정보]
        - 섹터: {info.get('sector', 'N/A')}
        - 산업: {info.get('industry', 'N/A')}
        - 시가총액: ${info.get('marketCap', 0):,.0f}
        - 52주 최고가: ${info.get('fiftyTwoWeekHigh', 'N/A')}
        - 52주 최저가: ${info.get('fiftyTwoWeekLow', 'N/A')}
        
        [최신 가격 데이터]
        - 현재가: ${latest['Close']:.2f}
        - 전일 대비: {((latest['Close'] - df['Close'].iloc[-2]) / df['Close'].iloc[-2] * 100):.2f}%
        - 거래량: {latest['Volume']:,.0f}
        - 연간 변동성: {volatility:.2f}%
        
        [기술적 지표]
        - RSI: {latest.get('RSI', 'N/A'):.2f}
        - MACD: {latest.get('MACD', 'N/A'):.2f}
        - MACD Signal: {latest.get('MACD_signal', 'N/A'):.2f}
        - CCI: {latest.get('CCI', 'N/A'):.2f}
        - MFI: {latest.get('MFI', 'N/A'):.2f}
        - Stochastic %K: {latest.get('Stoch_K', 'N/A'):.2f}
        - ATR: {latest.get('ATR', 'N/A'):.2f}
        
        [이동평균]
        - 20일: ${df['SMA_20'].iloc[-1]:.2f} if 'SMA_20' in df.columns else 'N/A'}
        - 50일: ${df['SMA_50'].iloc[-1]:.2f} if 'SMA_50' in df.columns and not pd.isna(df['SMA_50'].iloc[-1]) else 'N/A'}
        
        [최근 성과]
        - 5일 수익률: {((latest['Close'] - df['Close'].iloc[-6]) / df['Close'].iloc[-6] * 100):.2f}%
        - 20일 수익률: {((latest['Close'] - df['Close'].iloc[-21]) / df['Close'].iloc[-21] * 100):.2f}%
        
        위 데이터를 바탕으로 다음을 분석해주세요:
        
        1. 현재 주식의 기술적 상태와 투자 매력도
        2. 단기(1-2주) 및 중기(1-3개월) 가격 전망
        3. 주요 지지선과 저항선 레벨
        4. 현재 시장에서의 리스크 요인
        5. 구체적인 매매 전략과 포지션 관리 방안
        6. 이 주식의 강점과 약점
        
        전문적이면서도 이해하기 쉽게 한국어로 설명해주세요.
        """
        
        completion = groq_client.chat.completions.create(
            model="llama3-8b-8192",  # 새로운 모델
            messages=[
                {
                    "role": "system",
                    "content": "당신은 20년 경력의 전문 주식 분석가이자 포트폴리오 매니저입니다. 기술적 분석, 시장 심리, 리스크 관리에 정통하며, 실용적이고 구체적인 투자 조언을 제공합니다."
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
        return perform_technical_analysis(df, symbol)

# 메인 화면
if st.session_state.stock_list:
    # 탭 생성
    tab_titles = ["📊 포트폴리오 대시보드"] + [f"📈 {stock}" for stock in st.session_state.stock_list]
    tabs = st.tabs(tab_titles)
    
    # 포트폴리오 대시보드 탭
    with tabs[0]:
        st.header("📊 포트폴리오 대시보드")
        
        # 포트폴리오 가치 계산
        if st.session_state.portfolio:
            current_prices = {}
            for symbol in st.session_state.portfolio.keys():
                df, _ = get_stock_data(symbol, "1d")
                if not df.empty:
                    current_prices[symbol] = df['Close'].iloc[-1]
            
            total_value, portfolio_details = calculate_portfolio_value(st.session_state.portfolio, current_prices)
            
            # 포트폴리오 요약
            col1, col2, col3 = st.columns(3)
            with col1:
                st.metric("총 포트폴리오 가치", f"${total_value:,.2f}")
            with col2:
                st.metric("보유 종목 수", len(st.session_state.portfolio))
            with col3:
                st.metric("평균 종목당 가치", f"${total_value/len(st.session_state.portfolio):,.2f}")
            
            # 포트폴리오 상세
            st.subheader("보유 종목 상세")
            portfolio_df = pd.DataFrame(portfolio_details)
            if not portfolio_df.empty:
                portfolio_df['비중(%)'] = (portfolio_df['Value'] / total_value * 100).round(2)
                st.dataframe(portfolio_df, use_container_width=True)
                
                # 파이 차트
                fig = go.Figure(data=[go.Pie(
                    labels=portfolio_df['Symbol'],
                    values=portfolio_df['Value'],
                    hole=.3
                )])
                fig.update_layout(title="포트폴리오 구성", height=400)
                st.plotly_chart(fig, use_container_width=True)
        
        # 전체 주식 개요
        st.subheader("📈 관심 종목 현황")
        
        # 주식 카드 레이아웃
        cols = st.columns(3)
        for i, symbol in enumerate(st.session_state.stock_list):
            with cols[i % 3]:
                with st.container():
                    df, info = get_stock_data(symbol, "5d")
                    if not df.empty:
                        current = df['Close'].iloc[-1]
                        prev = df['Close'].iloc[-2] if len(df) > 1 else current
                        change = ((current - prev) / prev) * 100 if prev != 0 else 0
                        
                        # 카드 스타일
                        color = "🟢" if change >= 0 else "🔴"
                        
                        st.metric(
                            label=f"{color} {symbol}",
                            value=f"${current:.2f}",
                            delta=f"{change:.2f}%",
                            delta_color="normal"
                        )
                        
                        # 미니 정보
                        col1, col2 = st.columns(2)
                        with col1:
                            st.caption(f"거래량: {df['Volume'].iloc[-1]:,.0f}")
                        with col2:
                            st.caption(f"섹터: {info.get('sector', 'N/A')[:15]}")
                        
                        # 미니 차트 (스파크라인)
                        mini_fig = go.Figure()
                        mini_fig.add_trace(go.Scatter(
                            x=df.index[-20:],
                            y=df['Close'][-20:],
                            mode='lines',
                            line=dict(color='green' if change >= 0 else 'red', width=2),
                            showlegend=False
                        ))
                        mini_fig.update_layout(
                            height=100,
                            margin=dict(l=0, r=0, t=0, b=0),
                            xaxis=dict(visible=False),
                            yaxis=dict(visible=False),
                            paper_bgcolor='rgba(0,0,0,0)',
                            plot_bgcolor='rgba(0,0,0,0)'
                        )
                        st.plotly_chart(mini_fig, use_container_width=True)
                    else:
                        st.error(f"{symbol} 데이터 없음")
                    
                    st.markdown("---")
    
    # 개별 주식 탭
    for idx, symbol in enumerate(st.session_state.stock_list):
        with tabs[idx + 1]:
            # 헤더 행
            col1, col2, col3, col4 = st.columns([3, 1, 1, 1])
            
            with col1:
                st.header(f"{symbol} 상세 분석")
            
            with col2:
                period = st.selectbox(
                    "기간",
                    ["1d", "5d", "1mo", "3mo", "6mo", "1y", "2y", "5y", "max"],
                    index=2,
                    key=f"period_{symbol}"
                )
            
            with col3:
                chart_type = st.selectbox(
                    "차트",
                    ["캔들", "라인"],
                    key=f"chart_type_{symbol}"
                )
            
            with col4:
                if st.button("🔄 새로고침", key=f"refresh_{symbol}"):
                    st.cache_data.clear()
                    st.rerun()
            
            # 데이터 로드
            with st.spinner(f"{symbol} 데이터 로딩 중..."):
                df, info = get_stock_data(symbol, period)
            
            if not df.empty:
                # 지표 계산
                df = calculate_indicators(df)
                
                # 회사 정보 및 실시간 데이터
                if info:
                    with st.expander("🏢 회사 정보 및 실시간 데이터", expanded=True):
                        col1, col2, col3, col4 = st.columns(4)
                        with col1:
                            st.metric("회사명", info.get('longName', 'N/A'))
                            st.metric("섹터", info.get('sector', 'N/A'))
                        with col2:
                            st.metric("산업", info.get('industry', 'N/A'))
                            market_cap = info.get('marketCap', 0)
                            if market_cap > 1e12:
                                cap_str = f"${market_cap/1e12:.1f}T"
                            elif market_cap > 1e9:
                                cap_str = f"${market_cap/1e9:.1f}B"
                            else:
                                cap_str = f"${market_cap/1e6:.1f}M"
                            st.metric("시가총액", cap_str)
                        with col3:
                            st.metric("52주 최고", f"${info.get('fiftyTwoWeekHigh', 0):.2f}")
                            st.metric("52주 최저", f"${info.get('fiftyTwoWeekLow', 0):.2f}")
                        with col4:
                            if info.get('dividendYield'):
                                st.metric("배당수익률", f"{info.get('dividendYield', 0)*100:.2f}%")
                            else:
                                st.metric("배당수익률", "N/A")
                            st.metric("PER", f"{info.get('forwardPE', info.get('trailingPE', 0)):.2f}")
                
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
                    if 'MACD' in df.columns and 'MACD_signal' in df.columns:
                        macd_diff = df['MACD'].iloc[-1] - df['MACD_signal'].iloc[-1]
                        st.metric(
                            "MACD",
                            f"{df['MACD'].iloc[-1]:.2f}",
                            delta="매수" if macd_diff > 0 else "매도"
                        )
                    else:
                        st.metric("MACD", "N/A")
                
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
                    else:
                        st.metric("Stoch", "N/A")
                
                with col6:
                    if 'ATR' in df.columns:
                        atr_val = df['ATR'].iloc[-1]
                        atr_pct = (atr_val / df['Close'].iloc[-1]) * 100
                        st.metric(
                            "ATR",
                            f"{atr_val:.2f}",
                            delta=f"{atr_pct:.1f}% 변동성"
                        )
                    else:
                        st.metric("ATR", "N/A")
                
                # 뉴스 섹션
                st.subheader("📰 최신 뉴스")
                news = get_stock_news(symbol)
                if news:
                    for article in news[:3]:
                        with st.expander(f"📄 {article.get('title', 'N/A')[:80]}..."):
                            col1, col2 = st.columns([3, 1])
                            with col1:
                                st.write(article.get('title', 'N/A'))
                                if article.get('link'):
                                    st.markdown(f"[전체 기사 읽기]({article.get('link')})")
                            with col2:
                                if article.get('publisher'):
                                    st.caption(f"출처: {article.get('publisher')}")
                                if article.get('providerPublishTime'):
                                    pub_time = datetime.fromtimestamp(article.get('providerPublishTime'))
                                    st.caption(f"시간: {pub_time.strftime('%Y-%m-%d %H:%M')}")
                else:
                    st.info("최신 뉴스가 없습니다.")
                
                # 가격 예측
                st.subheader("📈 가격 예측 (7일)")
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
                            line=dict(color='red', width=2, dash='dash'),
                            marker=dict(size=8)
                        ))
                        
                        pred_fig.update_layout(
                            title="가격 예측 (선형 회귀 기반)",
                            xaxis_title="날짜",
                            yaxis_title="가격 ($)",
                            height=400
                        )
                        st.plotly_chart(pred_fig, use_container_width=True)
                    
                    with col2:
                        st.metric("현재가", f"${df['Close'].iloc[-1]:.2f}")
                        st.metric("7일 후 예측가", f"${predictions[-1]:.2f}")
                        change_pct = ((predictions[-1] - df['Close'].iloc[-1]) / df['Close'].iloc[-1]) * 100
                        st.metric("예상 변동률", f"{change_pct:+.2f}%")
                        st.caption("⚠️ 예측은 참고용입니다")
                
                # 분석 버튼
                st.markdown("---")
                col1, col2, col3, col4 = st.columns(4)
                
                with col1:
                    if st.button("📄 PDF 리포트", key=f"pdf_{symbol}"):
                        with st.spinner("PDF 생성 중..."):
                            pdf_buffer = generate_pdf_report(df, symbol, info)
                            st.download_button(
                                label="📥 PDF 다운로드",
                                data=pdf_buffer,
                                file_name=f"{symbol}_report_{datetime.now().strftime('%Y%m%d_%H%M')}.pdf",
                                mime="application/pdf",
                                key=f"download_pdf_{symbol}"
                            )
                
                with col2:
                    if st.button("📊 기술적 분석", key=f"tech_{symbol}"):
                        with st.spinner("분석 중..."):
                            analysis = perform_technical_analysis(df, symbol)
                            st.session_state.analysis_results[f"{symbol}_tech"] = analysis
                
                with col3:
                    if st.button("🤖 AI 심층 분석", key=f"ai_{symbol}"):
                        with st.spinner("AI 분석 중... (최대 30초 소요)"):
                            analysis = perform_ai_analysis(df, symbol, info)
                            st.session_state.analysis_results[f"{symbol}_ai"] = analysis
                
                with col4:
                    if st.button("🔄 분석 초기화", key=f"clear_{symbol}"):
                        if f"{symbol}_tech" in st.session_state.analysis_results:
                            del st.session_state.analysis_results[f"{symbol}_tech"]
                        if f"{symbol}_ai" in st.session_state.analysis_results:
                            del st.session_state.analysis_results[f"{symbol}_ai"]
                        st.success("분석 결과가 초기화되었습니다.")
                
                # 분석 결과 표시
                if f"{symbol}_tech" in st.session_state.analysis_results:
                    with st.expander("📊 기술적 분석 결과", expanded=True):
                        st.markdown(st.session_state.analysis_results[f"{symbol}_tech"])
                
                if f"{symbol}_ai" in st.session_state.analysis_results:
                    with st.expander("🤖 AI 분석 결과", expanded=True):
                        st.markdown(st.session_state.analysis_results[f"{symbol}_ai"])
                
            else:
                st.error(f"❌ {symbol} 데이터를 불러올 수 없습니다. 심볼을 확인해주세요.")
else:
    # 주식이 없을 때
    st.info("👈 왼쪽 사이드바에서 분석할 주식을 추가해주세요!")
    
    # 사용 가이드
    with st.expander("📖 사용 가이드", expanded=True):
        st.markdown("""
        ### 🚀 시작하기
        1. **주식 추가**: 왼쪽 사이드바에서 주식 심볼(예: AAPL, GOOGL)을 입력하고 추가
        2. **포트폴리오 관리**: 보유 주식 수를 입력하여 포트폴리오 추적
        3. **차트 확인**: 각 주식 탭에서 종합 기술적 지표와 차트 확인
        4. **뉴스 확인**: 최신 뉴스로 시장 동향 파악
        5. **분석 실행**: 기술적 분석 또는 AI 분석 버튼 클릭
        6. **예측 확인**: 7일 가격 예측으로 단기 전망 확인
        7. **리포트 생성**: PDF 리포트로 분석 결과 저장
        
        ### 📊 기술적 지표 설명
        - **RSI**: 14일 상대강도지수 (70 이상 과매수, 30 이하 과매도)
        - **MACD**: 이동평균수렴확산 (Signal선 교차 시 매매 신호)
        - **CCI**: 상품채널지수 (±100 초과 시 과매수/과매도)
        - **MFI**: 자금흐름지수 (80 이상 과매수, 20 이하 과매도)
        - **Stochastic**: 스토캐스틱 (80 이상 과매수, 20 이하 과매도)
        - **ATR**: 평균진폭범위 (변동성 지표)
        
        ### 💡 투자 팁
        - 여러 지표를 종합적으로 판단하세요
        - 뉴스와 함께 기술적 분석을 참고하세요
        - AI 분석으로 더 깊은 인사이트를 얻으세요
        - 포트폴리오를 분산하여 리스크를 관리하세요
        """)
    
    # 샘플 주식 추천
    st.subheader("🎯 인기 주식 심볼")
    popular_stocks = {
        "미국 테크": ["AAPL", "GOOGL", "MSFT", "AMZN", "META", "NVDA", "TSLA"],
        "한국 주식": ["005930.KS", "000660.KS", "035720.KS", "005490.KS", "051910.KS"],
        "ETF": ["SPY", "QQQ", "DIA", "IWM", "VTI"]
    }
    
    for category, stocks in popular_stocks.items():
        st.write(f"**{category}**: {', '.join(stocks)}")

# 푸터
st.markdown("---")
col1, col2, col3 = st.columns(3)
with col2:
    st.markdown("### 💡 Smart Investor")
    st.caption("AI 기반 실시간 주식 분석 플랫폼")
    st.caption(f"마지막 업데이트: {datetime.now().strftime('%Y-%m-%d %H:%M')}")