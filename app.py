import streamlit as st
import yfinance as yf
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import plotly.graph_objects as go
import ta

# 페이지 설정
st.set_page_config(
    page_title="SmartInvestor Pro",
    page_icon="📈",
    layout="wide"
)

st.title("📈 SmartInvestor Pro")

# 사이드바
with st.sidebar:
    st.header("메뉴")
    menu = st.radio("선택", ["홈", "주식 분석", "정보"])

# 홈 화면
if menu == "홈":
    st.markdown("### 🎯 실시간 주식 분석 도구")
    
    # 인기 종목 현재가
    st.markdown("### 📊 주요 종목 현재가")
    
    symbols = ['AAPL', 'MSFT', 'GOOGL', 'TSLA']
    cols = st.columns(len(symbols))
    
    for i, symbol in enumerate(symbols):
        try:
            ticker = yf.Ticker(symbol)
            info = ticker.info
            current_price = info.get('regularMarketPrice', info.get('currentPrice', 'N/A'))
            
            with cols[i]:
                if current_price != 'N/A':
                    st.metric(symbol, f"${current_price:.2f}")
                else:
                    # 대체 방법: 1일 데이터 가져오기
                    hist = ticker.history(period="1d")
                    if not hist.empty:
                        st.metric(symbol, f"${hist['Close'].iloc[-1]:.2f}")
                    else:
                        st.metric(symbol, "N/A")
        except Exception as e:
            with cols[i]:
                st.metric(symbol, "Error")
    
    st.info("Yahoo Finance API를 사용하여 실시간 데이터를 가져옵니다. (15-20분 지연)")

# 주식 분석
elif menu == "주식 분석":
    st.markdown("### 🔍 종목 분석")
    
    col1, col2 = st.columns([3, 1])
    with col1:
        symbol = st.text_input("종목 심볼 입력", "AAPL").upper()
    with col2:
        period = st.selectbox("기간", ["1mo", "3mo", "6mo", "1y"])
    
    if st.button("분석 시작", use_container_width=True):
        try:
            # Progress bar
            progress_bar = st.progress(0)
            status_text = st.empty()
            
            # 데이터 가져오기
            status_text.text("데이터 로딩 중...")
            progress_bar.progress(20)
            
            ticker = yf.Ticker(symbol)
            hist = ticker.history(period=period)
            
            if hist.empty:
                st.error(f"'{symbol}'에 대한 데이터를 찾을 수 없습니다.")
                st.info("팁: 미국 주식 심볼을 사용하세요 (예: AAPL, MSFT, GOOGL)")
            else:
                # 기술적 지표 계산
                status_text.text("기술적 지표 계산 중...")
                progress_bar.progress(40)
                
                # RSI 계산
                hist['RSI'] = ta.momentum.RSIIndicator(hist['Close'], window=14).rsi()
                
                # MACD 계산
                macd = ta.trend.MACD(hist['Close'])
                hist['MACD'] = macd.macd()
                hist['MACD_signal'] = macd.macd_signal()
                
                # 볼린저 밴드
                bb = ta.volatility.BollingerBands(hist['Close'], window=20)
                hist['BB_upper'] = bb.bollinger_hband()
                hist['BB_middle'] = bb.bollinger_mavg()
                hist['BB_lower'] = bb.bollinger_lband()
                
                progress_bar.progress(60)
                
                # 차트 생성
                status_text.text("차트 생성 중...")
                
                # 가격 차트
                fig = go.Figure()
                
                # 캔들스틱
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
                    line=dict(color='rgba(250, 128, 114, 0.5)', width=1)
                ))
                
                fig.add_trace(go.Scatter(
                    x=hist.index,
                    y=hist['BB_lower'],
                    name='BB Lower',
                    line=dict(color='rgba(250, 128, 114, 0.5)', width=1),
                    fill='tonexty',
                    fillcolor='rgba(250, 128, 114, 0.1)'
                ))
                
                fig.update_layout(
                    title=f"{symbol} 주가 차트",
                    xaxis_title="날짜",
                    yaxis_title="가격 ($)",
                    height=500,
                    template="plotly_white"
                )
                
                progress_bar.progress(80)
                
                # 차트 표시
                st.plotly_chart(fig, use_container_width=True)
                
                # 현재 지표
                st.markdown("### 📊 현재 지표")
                col1, col2, col3, col4 = st.columns(4)
                
                latest_close = hist['Close'].iloc[-1]
                latest_rsi = hist['RSI'].iloc[-1] if not pd.isna(hist['RSI'].iloc[-1]) else 50
                
                with col1:
                    st.metric("현재가", f"${latest_close:.2f}")
                
                with col2:
                    change = latest_close - hist['Close'].iloc[0]
                    change_pct = (change / hist['Close'].iloc[0]) * 100
                    st.metric("기간 수익률", f"{change_pct:.2f}%", f"${change:.2f}")
                
                with col3:
                    st.metric("RSI", f"{latest_rsi:.2f}")
                    if latest_rsi < 30:
                        st.success("과매도 구간")
                    elif latest_rsi > 70:
                        st.warning("과매수 구간")
                
                with col4:
                    volume = hist['Volume'].iloc[-1]
                    st.metric("거래량", f"{volume:,.0f}")
                
                # RSI 차트
                st.markdown("### RSI 지표")
                fig_rsi = go.Figure()
                
                fig_rsi.add_trace(go.Scatter(
                    x=hist.index,
                    y=hist['RSI'],
                    name='RSI',
                    line=dict(color='blue', width=2)
                ))
                
                # RSI 기준선
                fig_rsi.add_hline(y=70, line_dash="dash", line_color="red", annotation_text="과매수")
                fig_rsi.add_hline(y=30, line_dash="dash", line_color="green", annotation_text="과매도")
                fig_rsi.add_hline(y=50, line_dash="dot", line_color="gray")
                
                fig_rsi.update_layout(
                    title="RSI (Relative Strength Index)",
                    xaxis_title="날짜",
                    yaxis_title="RSI",
                    height=300,
                    yaxis=dict(range=[0, 100]),
                    template="plotly_white"
                )
                
                st.plotly_chart(fig_rsi, use_container_width=True)
                
                # 최근 데이터 테이블
                st.markdown("### 📋 최근 5일 데이터")
                recent_data = hist[['Open', 'High', 'Low', 'Close', 'Volume']].tail()
                recent_data = recent_data.round(2)
                st.dataframe(recent_data, use_container_width=True)
                
                progress_bar.progress(100)
                status_text.text("분석 완료!")
                
        except Exception as e:
            st.error(f"오류 발생: {str(e)}")
            st.info("다시 시도하거나 다른 종목을 검색해보세요.")

# 정보
elif menu == "정보":
    st.markdown("### ℹ️ SmartInvestor Pro 정보")
    
    st.markdown("""
    #### 사용 방법
    1. **종목 심볼 입력**: 미국 주식 심볼 사용 (예: AAPL, MSFT, GOOGL)
    2. **기간 선택**: 1개월, 3개월, 6개월, 1년
    3. **분석 시작**: 기술적 분석과 차트 확인
    
    #### 기술적 지표
    - **RSI**: 상대강도지수 (과매수/과매도 판단)
    - **볼린저 밴드**: 가격 변동성 분석
    - **MACD**: 추세 전환 신호
    
    #### 데이터 소스
    - Yahoo Finance API (실시간 데이터)
    - 15-20분 지연된 데이터
    
    #### 주의사항
    - 투자 결정은 신중하게
    - 여러 지표를 종합적으로 분석
    - 전문가 상담 권장
    """)
    
    # API 상태 체크
    st.markdown("### 🔌 시스템 상태")
    try:
        test_ticker = yf.Ticker("AAPL")
        test_data = test_ticker.history(period="1d")
        if not test_data.empty:
            st.success("✅ Yahoo Finance API: 정상 작동")
        else:
            st.warning("⚠️ Yahoo Finance API: 제한적 작동")
    except:
        st.error("❌ Yahoo Finance API: 연결 실패")
