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

# CSS 스타일
st.markdown("""
<style>
    .main > div {
        padding-top: 2rem;
    }
    .stButton > button {
        width: 100%;
    }
    .metric-card {
        background-color: #f0f2f6;
        padding: 1rem;
        border-radius: 0.5rem;
        text-align: center;
    }
</style>
""", unsafe_allow_html=True)

# Groq 클라이언트 초기화
groq_client = None
if GROQ_AVAILABLE and st.secrets.get("GROQ_API_KEY"):
    groq_client = Groq(api_key=st.secrets["GROQ_API_KEY"])

# 세션 상태 초기화
if 'stock_list' not in st.session_state:
    st.session_state.stock_list = ['AAPL', 'GOOGL', 'MSFT', 'AMZN', 'TSLA']
if 'analysis_results' not in st.session_state:
    st.session_state.analysis_results = {}

# 헤더
col1, col2, col3 = st.columns([1, 2, 1])
with col2:
    st.title("🤖 AI 기반 실시간 주식 분석")
    st.markdown("### 스마트한 투자 결정을 위한 기술적 분석 플랫폼")

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
            st.success(f"✅ {remove_stock} 삭제됨!")
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
    """주식 데이터 가져오기"""
    try:
        stock = yf.Ticker(symbol)
        df = stock.history(period=period)
        info = stock.info
        return df, info
    except Exception as e:
        st.error(f"데이터 로드 실패: {str(e)}")
        return pd.DataFrame(), {}

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
        
        return df
    except Exception as e:
        st.error(f"지표 계산 오류: {str(e)}")
        return df

def create_chart(df, symbol):
    """인터랙티브 차트 생성"""
    fig = make_subplots(
        rows=5, cols=1,
        shared_xaxes=True,
        vertical_spacing=0.03,
        subplot_titles=('주가 및 볼린저 밴드', 'RSI', 'MACD', 'CCI', 'MFI'),
        row_heights=[0.4, 0.15, 0.15, 0.15, 0.15]
    )
    
    # 주가 차트
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
    
    # 볼린저 밴드
    if 'BB_upper' in df.columns:
        fig.add_trace(
            go.Scatter(x=df.index, y=df['BB_upper'], name='BB Upper', 
                      line=dict(color='rgba(250, 128, 114, 0.5)')),
            row=1, col=1
        )
        fig.add_trace(
            go.Scatter(x=df.index, y=df['BB_middle'], name='BB Middle', 
                      line=dict(color='rgba(100, 149, 237, 0.5)')),
            row=1, col=1
        )
        fig.add_trace(
            go.Scatter(x=df.index, y=df['BB_lower'], name='BB Lower', 
                      line=dict(color='rgba(144, 238, 144, 0.5)')),
            row=1, col=1
        )
    
    # RSI
    if 'RSI' in df.columns:
        fig.add_trace(
            go.Scatter(x=df.index, y=df['RSI'], name='RSI', 
                      line=dict(color='orange', width=2)),
            row=2, col=1
        )
        fig.add_hline(y=70, line_dash="dash", line_color="red", opacity=0.5, row=2, col=1)
        fig.add_hline(y=30, line_dash="dash", line_color="green", opacity=0.5, row=2, col=1)
    
    # MACD
    if 'MACD' in df.columns:
        fig.add_trace(
            go.Scatter(x=df.index, y=df['MACD'], name='MACD', 
                      line=dict(color='blue', width=2)),
            row=3, col=1
        )
        fig.add_trace(
            go.Scatter(x=df.index, y=df['MACD_signal'], name='Signal', 
                      line=dict(color='red', width=2)),
            row=3, col=1
        )
        fig.add_trace(
            go.Bar(x=df.index, y=df['MACD_diff'], name='Histogram', 
                   marker_color='gray', opacity=0.3),
            row=3, col=1
        )
    
    # CCI
    if 'CCI' in df.columns:
        fig.add_trace(
            go.Scatter(x=df.index, y=df['CCI'], name='CCI', 
                      line=dict(color='purple', width=2)),
            row=4, col=1
        )
        fig.add_hline(y=100, line_dash="dash", line_color="red", opacity=0.5, row=4, col=1)
        fig.add_hline(y=-100, line_dash="dash", line_color="green", opacity=0.5, row=4, col=1)
    
    # MFI
    if 'MFI' in df.columns:
        fig.add_trace(
            go.Scatter(x=df.index, y=df['MFI'], name='MFI', 
                      line=dict(color='brown', width=2)),
            row=5, col=1
        )
        fig.add_hline(y=80, line_dash="dash", line_color="red", opacity=0.5, row=5, col=1)
        fig.add_hline(y=20, line_dash="dash", line_color="green", opacity=0.5, row=5, col=1)
    
    # 레이아웃 설정
    fig.update_layout(
        title=f"{symbol} 기술적 분석 차트",
        xaxis_title="날짜",
        height=1000,
        showlegend=True,
        legend=dict(
            orientation="h",
            yanchor="bottom",
            y=1.02,
            xanchor="right",
            x=1
        )
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
    story.append(Paragraph(f"{symbol} Stock Analysis Report", title_style))
    story.append(Spacer(1, 12))
    
    # 생성 날짜
    story.append(Paragraph(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M')}", normal_style))
    story.append(Spacer(1, 20))
    
    # 기본 정보
    story.append(Paragraph("Company Information", heading_style))
    if info:
        basic_info = [
            ["Company", info.get('longName', 'N/A')],
            ["Sector", info.get('sector', 'N/A')],
            ["Industry", info.get('industry', 'N/A')],
            ["Market Cap", f"${info.get('marketCap', 0):,.0f}" if info.get('marketCap') else 'N/A']
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
    story.append(Paragraph("Price Information", heading_style))
    current_price = df['Close'].iloc[-1]
    prev_close = df['Close'].iloc[-2] if len(df) > 1 else current_price
    change = current_price - prev_close
    change_pct = (change / prev_close) * 100 if prev_close != 0 else 0
    
    price_info = [
        ["Current Price", f"${current_price:.2f}"],
        ["Previous Close", f"${prev_close:.2f}"],
        ["Change", f"${change:.2f} ({change_pct:+.2f}%)"],
        ["Volume", f"{df['Volume'].iloc[-1]:,.0f}"]
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
    story.append(Paragraph("Technical Indicators", heading_style))
    indicators = []
    if 'RSI' in df.columns and not pd.isna(df['RSI'].iloc[-1]):
        indicators.append(["RSI", f"{df['RSI'].iloc[-1]:.2f}"])
    if 'MACD' in df.columns and not pd.isna(df['MACD'].iloc[-1]):
        indicators.append(["MACD", f"{df['MACD'].iloc[-1]:.2f}"])
    if 'CCI' in df.columns and not pd.isna(df['CCI'].iloc[-1]):
        indicators.append(["CCI", f"{df['CCI'].iloc[-1]:.2f}"])
    if 'MFI' in df.columns and not pd.isna(df['MFI'].iloc[-1]):
        indicators.append(["MFI", f"{df['MFI'].iloc[-1]:.2f}"])
    
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
    
    # 추세 분석
    sma_20 = df['SMA_20'].iloc[-1] if 'SMA_20' in df.columns else latest['Close']
    trend = "상승" if latest['Close'] > sma_20 else "하락"
    
    analysis = f"""
## 📊 {symbol} 기술적 분석 결과

### 📈 현재 지표값
- **RSI**: {rsi_val:.2f} - {rsi_signal} 상태
- **MACD**: {macd_signal} 신호
- **CCI**: {cci_val:.2f} - {cci_signal} 상태
- **MFI**: {mfi_val:.2f} - {mfi_signal} 상태

### 📉 추세 분석
- **현재 추세**: {trend} (20일 이동평균 기준)
- **현재가**: ${latest['Close']:.2f}
- **20일 이동평균**: ${sma_20:.2f}

### 💡 종합 의견
"""
    
    # 점수 계산
    score = 0
    if 30 < rsi_val < 70: score += 1
    if macd_signal == "매수": score += 1
    if -100 < cci_val < 100: score += 1
    if 20 < mfi_val < 80: score += 1
    if trend == "상승": score += 1
    
    if score >= 4:
        analysis += "**긍정적** - 대부분의 지표가 긍정적인 신호를 보이고 있습니다."
    elif score >= 2:
        analysis += "**중립적** - 혼재된 신호를 보이고 있어 신중한 접근이 필요합니다."
    else:
        analysis += "**부정적** - 대부분의 지표가 부정적인 신호를 보이고 있습니다."
    
    # 리스크 요인
    risks = []
    if rsi_val > 70:
        risks.append("RSI 과매수 구간")
    elif rsi_val < 30:
        risks.append("RSI 과매도 구간")
    if mfi_val > 80:
        risks.append("MFI 과매수 구간")
    elif mfi_val < 20:
        risks.append("MFI 과매도 구간")
    
    if risks:
        analysis += f"\n\n### ⚠️ 주의사항\n"
        for risk in risks:
            analysis += f"- {risk}\n"
    
    analysis += "\n\n*※ 이 분석은 기술적 지표만을 기반으로 하며, 투자 결정 시 다른 요인들도 함께 고려하시기 바랍니다.*"
    
    return analysis

def perform_ai_analysis(df, symbol, info):
    """AI 기반 심층 분석"""
    if not groq_client:
        return perform_technical_analysis(df, symbol)
    
    try:
        latest = df.iloc[-1]
        
        prompt = f"""
        다음은 {symbol} ({info.get('longName', symbol)}) 주식의 기술적 분석 데이터입니다:
        
        기본 정보:
        - 섹터: {info.get('sector', 'N/A')}
        - 산업: {info.get('industry', 'N/A')}
        - 시가총액: ${info.get('marketCap', 0):,.0f}
        
        최신 가격 데이터:
        - 현재가: ${latest['Close']:.2f}
        - 거래량: {latest['Volume']:,.0f}
        
        기술적 지표:
        - RSI: {latest.get('RSI', 'N/A'):.2f}
        - MACD: {latest.get('MACD', 'N/A'):.2f}
        - CCI: {latest.get('CCI', 'N/A'):.2f}
        - MFI: {latest.get('MFI', 'N/A'):.2f}
        
        5일 이동평균:
        - 종가: ${df['Close'].tail(5).mean():.2f}
        - RSI: {df['RSI'].tail(5).mean():.2f}
        
        이 데이터를 바탕으로:
        1. 현재 주식의 기술적 상태를 평가해주세요
        2. 단기(1주일) 및 중기(1개월) 전망을 제시해주세요
        3. 주요 리스크 요인을 분석해주세요
        4. 투자자를 위한 구체적인 제안을 해주세요
        
        한국어로 전문적이면서도 이해하기 쉽게 설명해주세요.
        """
        
        completion = groq_client.chat.completions.create(
            model="mixtral-8x7b-32768",
            messages=[
                {
                    "role": "system",
                    "content": "당신은 20년 경력의 전문 주식 분석가입니다. 기술적 분석과 시장 동향을 바탕으로 객관적이고 실용적인 투자 조언을 제공합니다."
                },
                {
                    "role": "user",
                    "content": prompt
                }
            ],
            temperature=0.7,
            max_tokens=1500
        )
        
        return f"## 🤖 AI 심층 분석 결과\n\n{completion.choices[0].message.content}"
        
    except Exception as e:
        st.error(f"AI 분석 중 오류 발생: {str(e)}")
        return perform_technical_analysis(df, symbol)

# 메인 화면
if st.session_state.stock_list:
    # 탭 생성
    tab_titles = ["📊 전체 개요"] + [f"📈 {stock}" for stock in st.session_state.stock_list]
    tabs = st.tabs(tab_titles)
    
    # 전체 개요 탭
    with tabs[0]:
        st.header("📊 포트폴리오 개요")
        
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
                            st.caption(f"섹터: {info.get('sector', 'N/A')[:10]}")
                    else:
                        st.error(f"{symbol} 데이터 없음")
                    
                    st.markdown("---")
    
    # 개별 주식 탭
    for idx, symbol in enumerate(st.session_state.stock_list):
        with tabs[idx + 1]:
            # 헤더 행
            col1, col2, col3 = st.columns([3, 1, 1])
            
            with col1:
                st.header(f"{symbol} 상세 분석")
            
            with col2:
                period = st.selectbox(
                    "기간",
                    ["1d", "5d", "1mo", "3mo", "6mo", "1y", "2y", "5y"],
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
                
                # 회사 정보
                if info:
                    with st.expander("🏢 회사 정보", expanded=False):
                        col1, col2, col3, col4 = st.columns(4)
                        with col1:
                            st.metric("회사명", info.get('longName', 'N/A'))
                        with col2:
                            st.metric("섹터", info.get('sector', 'N/A'))
                        with col3:
                            st.metric("산업", info.get('industry', 'N/A'))
                        with col4:
                            market_cap = info.get('marketCap', 0)
                            if market_cap > 1e12:
                                cap_str = f"${market_cap/1e12:.1f}T"
                            elif market_cap > 1e9:
                                cap_str = f"${market_cap/1e9:.1f}B"
                            else:
                                cap_str = f"${market_cap/1e6:.1f}M"
                            st.metric("시가총액", cap_str)
                
                # 차트
                st.plotly_chart(create_chart(df, symbol), use_container_width=True)
                
                # 최신 지표
                st.subheader("📊 최신 기술적 지표")
                col1, col2, col3, col4 = st.columns(4)
                
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
                
                # 분석 버튼
                st.markdown("---")
                col1, col2, col3 = st.columns(3)
                
                with col1:
                    if st.button("📄 PDF 리포트 생성", key=f"pdf_{symbol}"):
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
    with st.expander("📖 사용 가이드"):
        st.markdown("""
        ### 🚀 시작하기
        1. **주식 추가**: 왼쪽 사이드바에서 주식 심볼(예: AAPL, GOOGL)을 입력하고 추가
        2. **차트 확인**: 각 주식 탭에서 기술적 지표와 차트 확인
        3. **분석 실행**: 기술적 분석 또는 AI 분석 버튼 클릭
        4. **리포트 생성**: PDF 리포트로 분석 결과 저장
        
        ### 📊 기술적 지표 설명
        - **RSI**: 14일 상대강도지수 (70 이상 과매수, 30 이하 과매도)
        - **MACD**: 이동평균수렴확산 (Signal선 교차 시 매매 신호)
        - **CCI**: 상품채널지수 (±100 초과 시 과매수/과매도)
        - **MFI**: 자금흐름지수 (80 이상 과매수, 20 이하 과매도)
        """)

# 푸터
st.markdown("---")
col1, col2, col3 = st.columns(3)
with col2:
    st.markdown("### 💡 Smart Investor")
    st.caption("AI 기반 실시간 주식 분석 플랫폼")
    st.caption(f"마지막 업데이트: {datetime.now().strftime('%Y-%m-%d %H:%M')}")