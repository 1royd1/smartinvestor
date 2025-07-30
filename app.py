import streamlit as st
import pandas as pd
import requests
import time
from datetime import datetime

# 페이지 설정
st.set_page_config(
    page_title="SmartInvestor Pro",
    page_icon="📈",
    layout="wide"
)

# CSS 스타일
st.markdown("""
<style>
    .main-header {
        font-size: 2.5rem;
        font-weight: bold;
        text-align: center;
        color: #1f77b4;
        margin-bottom: 2rem;
    }
    .buy-signal {
        background: linear-gradient(135deg, #11998e 0%, #38ef7d 100%);
        padding: 1rem;
        border-radius: 10px;
        color: white;
        text-align: center;
        margin: 1rem 0;
    }
    .warning-signal {
        background: linear-gradient(135deg, #ff9a9e 0%, #fecfef 100%);
        padding: 1rem;
        border-radius: 10px;
        color: #333;
        text-align: center;
        margin: 1rem 0;
    }
    .neutral-signal {
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        padding: 1rem;
        border-radius: 10px;
        color: white;
        text-align: center;
        margin: 1rem 0;
    }
</style>
""", unsafe_allow_html=True)

# Alpha Vantage API 클래스
class AlphaVantageAPI:
    def __init__(self, api_key):
        self.api_key = api_key
        self.base_url = "https://www.alphavantage.co/query"
        
    def get_stock_data(self, symbol):
        """주식 데이터 가져오기"""
        try:
            params = {
                'function': 'TIME_SERIES_DAILY',
                'symbol': symbol,
                'outputsize': 'compact',
                'apikey': self.api_key
            }
            
            response = requests.get(self.base_url, params=params, timeout=15)
            data = response.json()
            
            if 'Error Message' in data:
                st.error(f"❌ 잘못된 심볼: {symbol}")
                return None
                
            if 'Note' in data:
                st.warning("⚠️ API 호출 제한에 도달했습니다. 잠시 후 다시 시도해주세요.")
                return None
                
            time_series = data.get('Time Series (Daily)', {})
            if not time_series:
                st.error(f"❌ {symbol} 데이터를 찾을 수 없습니다.")
                return None
                
            # DataFrame 변환
            df_data = []
            for date_str, values in time_series.items():
                try:
                    df_data.append({
                        'Date': pd.to_datetime(date_str),
                        'Open': float(values['1. open']),
                        'High': float(values['2. high']),
                        'Low': float(values['3. low']),
                        'Close': float(values['4. close']),
                        'Volume': int(values['5. volume'])
                    })
                except (ValueError, KeyError):
                    continue
            
            if not df_data:
                return None
                
            df = pd.DataFrame(df_data)
            df.set_index('Date', inplace=True)
            df.sort_index(inplace=True)
            
            return df
            
        except requests.exceptions.RequestException:
            st.error(f"🌐 네트워크 오류: {symbol} 데이터를 가져올 수 없습니다.")
            return None
        except Exception as e:
            st.error(f"❌ 오류 발생: {str(e)}")
            return None
    
    def get_real_time_quote(self, symbol):
        """실시간 시세"""
        try:
            params = {
                'function': 'GLOBAL_QUOTE',
                'symbol': symbol,
                'apikey': self.api_key
            }
            
            response = requests.get(self.base_url, params=params, timeout=15)
            data = response.json()
            
            quote = data.get('Global Quote', {})
            if not quote:
                return None
                
            return {
                'symbol': quote.get('01. symbol', symbol),
                'price': float(quote.get('05. price', 0)),
                'change': float(quote.get('09. change', 0)),
                'change_percent': quote.get('10. change percent', '0%').replace('%', ''),
                'volume': int(quote.get('06. volume', 0))
            }
            
        except Exception:
            return None

# 기술적 지표 계산
def calculate_rsi(data, period=14):
    """RSI 계산"""
    if len(data) < period + 1:
        return 50
    
    try:
        delta = data['Close'].diff()
        gain = delta.where(delta > 0, 0)
        loss = -delta.where(delta < 0, 0)
        
        avg_gain = gain.rolling(window=period).mean()
        avg_loss = loss.rolling(window=period).mean()
        
        rs = avg_gain / avg_loss
        rsi = 100 - (100 / (1 + rs))
        
        return rsi.iloc[-1] if not pd.isna(rsi.iloc[-1]) else 50
    except:
        return 50

def calculate_simple_macd(data):
    """간단한 MACD 계산"""
    if len(data) < 26:
        return False
    
    try:
        exp12 = data['Close'].ewm(span=12).mean()
        exp26 = data['Close'].ewm(span=26).mean()
        macd = exp12 - exp26
        signal = macd.ewm(span=9).mean()
        
        return macd.iloc[-1] > signal.iloc[-1]
    except:
        return False

def calculate_price_trend(data, period=5):
    """가격 추세 계산"""
    if len(data) < period:
        return "Unknown"
    
    try:
        recent_avg = data['Close'].tail(period).mean()
        previous_avg = data['Close'].tail(period * 2).head(period).mean()
        
        if recent_avg > previous_avg * 1.02:
            return "강한 상승"
        elif recent_avg > previous_avg:
            return "상승"
        elif recent_avg < previous_avg * 0.98:
            return "강한 하락"
        else:
            return "하락"
    except:
        return "Unknown"

# 종합 분석
def analyze_stock(data, quote=None):
    """종합 주식 분석"""
    if data is None or len(data) < 20:
        return {
            'score': 0,
            'rsi': 50,
            'trend': 'Unknown',
            'macd_signal': False,
            'volume_trend': 'Normal',
            'recommendation': 'Insufficient Data'
        }
    
    try:
        # RSI 계산
        rsi = calculate_rsi(data)
        
        # MACD 신호
        macd_bullish = calculate_simple_macd(data)
        
        # 가격 추세
        price_trend = calculate_price_trend(data)
        
        # 거래량 분석
        recent_volume = data['Volume'].tail(5).mean()
        avg_volume = data['Volume'].mean()
        volume_trend = "High" if recent_volume > avg_volume * 1.5 else "Normal"
        
        # 점수 계산 (5점 만점)
        score = 0
        
        # RSI 점수
        if rsi < 30:  # 과매도
            score += 2
        elif rsi < 50:
            score += 1
        
        # MACD 점수
        if macd_bullish:
            score += 1
        
        # 추세 점수
        if "상승" in price_trend:
            score += 1
            if "강한" in price_trend:
                score += 1
        
        # 거래량 점수
        if volume_trend == "High" and score > 0:
            score += 1
        
        # 추천 결정
        if score >= 4:
            recommendation = "Strong Buy"
        elif score >= 3:
            recommendation = "Buy"
        elif score >= 2:
            recommendation = "Hold"
        else:
            recommendation = "Wait"
        
        return {
            'score': min(score, 5),
            'rsi': round(rsi, 2),
            'trend': price_trend,
            'macd_signal': macd_bullish,
            'volume_trend': volume_trend,
            'recommendation': recommendation
        }
        
    except Exception as e:
        return {
            'score': 0,
            'rsi': 50,
            'trend': 'Error',
            'macd_signal': False,
            'volume_trend': 'Error',
            'recommendation': 'Error in Analysis'
        }

# 메인 애플리케이션
def main():
    # 헤더
    st.markdown('<div class="main-header">🚀 SmartInvestor Pro</div>', unsafe_allow_html=True)
    st.markdown("### AI 기반 스마트 투자 분석 도구")
    
    # 사이드바
    st.sidebar.title("📊 설정")
    
    # API 키 확인
    api_key = st.secrets.get("ALPHA_VANTAGE_API_KEY", "")
    
    if not api_key:
        st.sidebar.error("⚠️ API 키가 설정되지 않았습니다.")
        
        # 직접 입력 옵션
        with st.sidebar.expander("🔑 API 키 입력"):
            test_key = st.text_input(
                "Alpha Vantage API 키:",
                type="password",
                help="https://www.alphavantage.co/support/#api-key"
            )
            if test_key:
                api_key = test_key
                st.success("✅ API 키가 설정되었습니다!")
    else:
        st.sidebar.success("✅ API 키가 설정되어 있습니다.")
    
    # 탭 생성
    tab1, tab2, tab3 = st.tabs(["📈 다중 종목 분석", "🎯 개별 종목 분석", "ℹ️ 사용법"])
    
    with tab1:
        st.subheader("📈 다중 종목 분석")
        
        # 인기 종목 리스트
        popular_stocks = {
            "🍎 Apple": "AAPL",
            "🖥️ Microsoft": "MSFT", 
            "🔍 Google": "GOOGL",
            "🚗 Tesla": "TSLA",
            "📦 Amazon": "AMZN",
            "💡 NVIDIA": "NVDA",
            "📘 Meta": "META",
            "🎬 Netflix": "NFLX",
            "☕ Starbucks": "SBUX",
            "✈️ Boeing": "BA"
        }
        
        selected_names = st.multiselect(
            "분석할 종목을 선택하세요:",
            list(popular_stocks.keys()),
            default=["🍎 Apple", "🖥️ Microsoft", "🔍 Google"]
        )
        
        selected_symbols = [popular_stocks[name] for name in selected_names]
        
        col1, col2 = st.columns([1, 3])
        
        with col1:
            analyze_button = st.button("🔍 분석 시작", type="primary", use_container_width=True)
        
        with col2:
            if len(selected_symbols) > 0:
                st.info(f"선택된 종목: {len(selected_symbols)}개 | 예상 소요시간: {len(selected_symbols) * 12}초")
        
        if analyze_button and api_key:
            if selected_symbols:
                av_api = AlphaVantageAPI(api_key)
                results = []
                
                # 진행률 표시
                progress_bar = st.progress(0)
                status_placeholder = st.empty()
                
                for i, symbol in enumerate(selected_symbols):
                    status_placeholder.info(f"📊 분석 중: {symbol} ({i+1}/{len(selected_symbols)})")
                    
                    # 데이터 가져오기
                    data = av_api.get_stock_data(symbol)
                    quote = av_api.get_real_time_quote(symbol)
                    
                    if data is not None:
                        analysis = analyze_stock(data, quote)
                        current_price = quote['price'] if quote else data['Close'].iloc[-1]
                        change_percent = quote['change_percent'] if quote else '0'
                        
                        results.append({
                            'symbol': symbol,
                            'name': [k for k, v in popular_stocks.items() if v == symbol][0],
                            'price': current_price,
                            'change_percent': change_percent,
                            'score': analysis['score'],
                            'rsi': analysis['rsi'],
                            'trend': analysis['trend'],
                            'macd_signal': analysis['macd_signal'],
                            'volume_trend': analysis['volume_trend'],
                            'recommendation': analysis['recommendation']
                        })
                    
                    # API 제한 대응 (분당 5회)
                    if i < len(selected_symbols) - 1:
                        time.sleep(12)
                    
                    progress_bar.progress((i + 1) / len(selected_symbols))
                
                progress_bar.empty()
                status_placeholder.empty()
                
                # 결과 표시
                if results:
                    st.success(f"✅ {len(results)}개 종목 분석 완료!")
                    
                    # 점수순 정렬
                    results.sort(key=lambda x: x['score'], reverse=True)
                    
                    for result in results:
                        with st.expander(f"{result['name']} ({result['symbol']}) - 점수: {result['score']}/5 ⭐"):
                            col1, col2, col3, col4 = st.columns(4)
                            
                            with col1:
                                price_color = "normal"
                                if result['change_percent'] != '0':
                                    try:
                                        change_val = float(result['change_percent'])
                                        price_color = "normal" if change_val == 0 else "inverse" if change_val < 0 else "normal"
                                    except:
                                        pass
                                
                                st.metric(
                                    "현재가", 
                                    f"${result['price']:.2f}",
                                    f"{result['change_percent']}%"
                                )
                            
                            with col2:
                                rsi_color = "normal"
                                if result['rsi'] < 30:
                                    rsi_color = "inverse"
                                elif result['rsi'] > 70:
                                    rsi_color = "normal"
                                
                                st.metric("RSI", f"{result['rsi']}")
                            
                            with col3:
                                st.metric("추세", result['trend'])
                            
                            with col4:
                                macd_text = "골든크로스" if result['macd_signal'] else "데드크로스"
                                st.metric("MACD", macd_text)
                            
                            # 추천 정보
                            rec = result['recommendation']
                            if rec == "Strong Buy":
                                st.markdown('<div class="buy-signal">🚀 강력 매수 추천!</div>', unsafe_allow_html=True)
                            elif rec == "Buy":
                                st.markdown('<div class="buy-signal">📈 매수 추천</div>', unsafe_allow_html=True)
                            elif rec == "Hold":
                                st.markdown('<div class="neutral-signal">📊 보유 권장</div>', unsafe_allow_html=True)
                            else:
                                st.markdown('<div class="warning-signal">⏳ 관망 권장</div>', unsafe_allow_html=True)
                            
                            # 상세 정보
                            st.markdown("**📋 상세 분석:**")
                            col_a, col_b = st.columns(2)
                            with col_a:
                                st.write(f"• RSI: {result['rsi']} ({'과매도' if result['rsi'] < 30 else '과매수' if result['rsi'] > 70 else '정상'})")
                                st.write(f"• 추세: {result['trend']}")
                            with col_b:
                                st.write(f"• MACD: {'상승신호' if result['macd_signal'] else '하락신호'}")
                                st.write(f"• 거래량: {result['volume_trend']}")
                
                else:
                    st.error("❌ 분석 결과를 가져올 수 없습니다. API 키를 확인해주세요.")
            else:
                st.warning("⚠️ 분석할 종목을 선택해주세요.")
    
    with tab2:
        st.subheader("🎯 개별 종목 심층 분석")
        
        # 종목 입력
        col1, col2 = st.columns([2, 1])
        
        with col1:
            custom_symbol = st.text_input(
                "종목 심볼을 입력하세요:",
                value="AAPL",
                help="예: AAPL, MSFT, GOOGL, TSLA 등"
            ).upper()
        
        with col2:
            single_analyze = st.button("🔍 분석하기", type="primary", use_container_width=True)
        
        if single_analyze and api_key and custom_symbol:
            av_api = AlphaVantageAPI(api_key)
            
            with st.spinner(f"📊 {custom_symbol} 분석 중..."):
                data = av_api.get_stock_data(custom_symbol)
                quote = av_api.get_real_time_quote(custom_symbol)
            
            if data is not None:
                analysis = analyze_stock(data, quote)
                
                # 기본 정보 표시
                st.success(f"✅ {custom_symbol} 분석 완료!")
                
                col1, col2, col3, col4 = st.columns(4)
                
                current_price = quote['price'] if quote else data['Close'].iloc[-1]
                change_percent = quote['change_percent'] if quote else '0'
                
                with col1:
                    st.metric("현재가", f"${current_price:.2f}", f"{change_percent}%")
                
                with col2:
                    st.metric("분석 점수", f"{analysis['score']}/5")
                
                with col3:
                    st.metric("RSI", f"{analysis['rsi']}")
                
                with col4:
                    st.metric("거래량", analysis['volume_trend'])
                
                # 상세 분석
                st.markdown("---")
                st.subheader("📊 상세 분석")
                
                col_left, col_right = st.columns(2)
                
                with col_left:
                    st.markdown("**🔍 기술적 지표:**")
                    st.write(f"• **RSI**: {analysis['rsi']} ({'과매도' if analysis['rsi'] < 30 else '과매수' if analysis['rsi'] > 70 else '정상 범위'})")
                    st.write(f"• **MACD**: {'상승 신호' if analysis['macd_signal'] else '하락 신호'}")
                    st.write(f"• **가격 추세**: {analysis['trend']}")
                    st.write(f"• **거래량**: {analysis['volume_trend']}")
                
                with col_right:
                    st.markdown("**💡 투자 의견:**")
                    
                    rec = analysis['recommendation']
                    if rec == "Strong Buy":
                        st.success("🚀 **강력 매수 추천**")
                        st.write("여러 기술적 지표가 긍정적입니다.")
                    elif rec == "Buy":
                        st.success("📈 **매수 추천**")
                        st.write("기술적 지표가 상승을 시사합니다.")
                    elif rec == "Hold":
                        st.info("📊 **보유 권장**")
                        st.write("현재 포지션 유지를 권장합니다.")
                    else:
                        st.warning("⏳ **관망 권장**")
                        st.write("더 나은 진입 시점을 기다려보세요.")
                
                # 최근 가격 차트 (간단한 라인 차트)
                st.markdown("---")
                st.subheader("📈 최근 30일 가격 추이")
                
                recent_data = data.tail(30)
                st.line_chart(recent_data['Close'])
                
            else:
                st.error(f"❌ {custom_symbol} 데이터를 가져올 수 없습니다. 심볼을 확인해주세요.")
    
    with tab3:
        st.subheader("ℹ️ SmartInvestor Pro 사용법")
        
        st.markdown("""
        ### 🎯 주요 기능
        
        **1. 다중 종목 분석**
        - 인기 종목들을 한 번에 분석
        - 5점 만점 점수 시스템
        - RSI, MACD, 가격 추세 종합 분석
        
        **2. 개별 종목 분석**
        - 원하는 종목의 심층 분석
        - 상세한 기술적 지표 제공
        - 30일 가격 차트 표시
        
        ### 📊 분석 지표 설명
        
        **RSI (Relative Strength Index)**
        - 30 이하: 과매도 (매수 고려)
        - 70 이상: 과매수 (매도 고려)
        - 30-70: 정상 범위
        
        **MACD (Moving Average Convergence Divergence)**
        - 골든크로스: 상승 신호
        - 데드크로스: 하락 신호
        
        **점수 시스템**
        - 5점: 강력 매수
        - 3-4점: 매수 고려
        - 1-2점: 보유/관망
        - 0점: 주의 필요
        
        ### ⚠️ 중요 안내사항
        
        - 이 도구는 **투자 참고용**입니다
        - 실제 투자 결정은 **본인 책임**하에 신중히 하세요
        - **분산 투자**와 **리스크 관리**를 권장합니다
        - 과거 데이터 기반 분석이므로 **미래 수익을 보장하지 않습니다**
        
        ### 🔑 API Key 발급 방법
        
        1. https://www.alphavantage.co/support/#api-key 방문
        2. 이메일 주소 입력
        3. "GET FREE API KEY" 클릭
        4. 발급받은 키를 Streamlit Secrets에 추가
        """)
        
        # 현재 시간 표시
        st.markdown("---")
        st.info(f"🕒 현재 시간: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

if __name__ == "__main__":
    main()