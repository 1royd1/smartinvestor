from flask import Flask, render_template, request, redirect, url_for, flash, send_file, session
import yfinance as yf
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import ta
from datetime import datetime, timedelta
from reportlab.lib.pagesizes import letter
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer
from reportlab.lib.styles import getSampleStyleSheet
import io
import os
from dotenv import load_dotenv
from groq import Groq

# 환경 변수 로드
load_dotenv()

app = Flask(__name__)
app.secret_key = 'your-secret-key-here'  # 실제 운영 시 변경 필요

# Groq 클라이언트 초기화
groq_client = None
if os.getenv('GROQ_API_KEY'):
    groq_client = Groq(api_key=os.getenv('GROQ_API_KEY'))

def get_stock_data(symbol, period='1y'):
    """주식 데이터 가져오기"""
    try:
        stock = yf.Ticker(symbol)
        df = stock.history(period=period)
        return df
    except Exception as e:
        app.logger.error(f"주식 데이터 가져오기 오류: {str(e)}")
        return pd.DataFrame()

def calculate_indicators(df):
    """기술적 지표 계산"""
    # RSI
    df['RSI'] = ta.momentum.RSIIndicator(df['Close']).rsi()
    
    # MACD
    macd = ta.trend.MACD(df['Close'])
    df['MACD'] = macd.macd()
    df['MACD_signal'] = macd.macd_signal()
    df['MACD_diff'] = macd.macd_diff()
    
    # CCI
    df['CCI'] = ta.trend.CCIIndicator(df['High'], df['Low'], df['Close']).cci()
    
    # MFI
    df['MFI'] = ta.volume.MFIIndicator(df['High'], df['Low'], df['Close'], df['Volume']).money_flow_index()
    
    return df

def create_chart(df, symbol):
    """인터랙티브 차트 생성"""
    fig = make_subplots(
        rows=5, cols=1,
        shared_xaxes=True,
        vertical_spacing=0.05,
        subplot_titles=('주가', 'RSI', 'MACD', 'CCI', 'MFI'),
        row_heights=[0.4, 0.15, 0.15, 0.15, 0.15]
    )
    
    # 캔들스틱 차트
    fig.add_trace(
        go.Candlestick(
            x=df.index,
            open=df['Open'],
            high=df['High'],
            low=df['Low'],
            close=df['Close'],
            name='주가'
        ),
        row=1, col=1
    )
    
    # RSI
    fig.add_trace(
        go.Scatter(x=df.index, y=df['RSI'], name='RSI', line=dict(color='purple')),
        row=2, col=1
    )
    fig.add_hline(y=70, line_dash="dash", line_color="red", row=2, col=1)
    fig.add_hline(y=30, line_dash="dash", line_color="green", row=2, col=1)
    
    # MACD
    fig.add_trace(
        go.Scatter(x=df.index, y=df['MACD'], name='MACD', line=dict(color='blue')),
        row=3, col=1
    )
    fig.add_trace(
        go.Scatter(x=df.index, y=df['MACD_signal'], name='Signal', line=dict(color='red')),
        row=3, col=1
    )
    fig.add_trace(
        go.Bar(x=df.index, y=df['MACD_diff'], name='Histogram', marker_color='gray'),
        row=3, col=1
    )
    
    # CCI
    fig.add_trace(
        go.Scatter(x=df.index, y=df['CCI'], name='CCI', line=dict(color='orange')),
        row=4, col=1
    )
    fig.add_hline(y=100, line_dash="dash", line_color="red", row=4, col=1)
    fig.add_hline(y=-100, line_dash="dash", line_color="green", row=4, col=1)
    
    # MFI
    fig.add_trace(
        go.Scatter(x=df.index, y=df['MFI'], name='MFI', line=dict(color='green')),
        row=5, col=1
    )
    fig.add_hline(y=80, line_dash="dash", line_color="red", row=5, col=1)
    fig.add_hline(y=20, line_dash="dash", line_color="green", row=5, col=1)
    
    # 레이아웃 설정
    fig.update_layout(
        title=f'{symbol} 주식 분석',
        xaxis_title='날짜',
        height=1000,
        showlegend=True,
        template='plotly_white'
    )
    
    fig.update_xaxes(rangeslider_visible=False)
    
    return fig.to_html(full_html=False, include_plotlyjs='cdn')

def perform_technical_analysis(df, symbol):
    """기본 기술적 분석"""
    latest = df.iloc[-1]
    
    # RSI 분석
    rsi_signal = "과매수" if latest['RSI'] > 70 else "과매도" if latest['RSI'] < 30 else "중립"
    
    # MACD 분석
    macd_signal = "매수" if latest['MACD'] > latest['MACD_signal'] else "매도"
    
    # CCI 분석
    cci_signal = "과매수" if latest['CCI'] > 100 else "과매도" if latest['CCI'] < -100 else "중립"
    
    # MFI 분석
    mfi_signal = "과매수" if latest['MFI'] > 80 else "과매도" if latest['MFI'] < 20 else "중립"
    
    analysis = f"""
{symbol} 기술적 분석 결과:

1. RSI ({latest['RSI']:.2f}): {rsi_signal} 상태
2. MACD: {macd_signal} 신호
3. CCI ({latest['CCI']:.2f}): {cci_signal} 상태
4. MFI ({latest['MFI']:.2f}): {mfi_signal} 상태

종합 의견: 
- RSI와 MFI를 기준으로 {"과열" if rsi_signal == "과매수" or mfi_signal == "과매수" else "침체" if rsi_signal == "과매도" or mfi_signal == "과매도" else "안정적인"} 상태입니다.
- MACD는 {macd_signal} 신호를 보이고 있습니다.
- 투자 결정 시 다른 요인들도 함께 고려하시기 바랍니다.
"""
    
    return analysis

def perform_ai_deep_analysis(df, symbol):
    """Groq AI를 사용한 심층 분석"""
    try:
        # 최근 데이터 준비
        latest = df.iloc[-1]
        
        # 프롬프트 생성
        prompt = f"""
다음은 {symbol} 주식의 최근 기술적 지표입니다:

최신 데이터:
- 종가: ${latest['Close']:.2f}
- RSI: {latest['RSI']:.2f}
- MACD: {latest['MACD']:.2f}
- CCI: {latest['CCI']:.2f}
- MFI: {latest['MFI']:.2f}

5일 평균:
- RSI: {df['RSI'].tail(5).mean():.2f}
- MACD: {df['MACD'].tail(5).mean():.2f}

이 데이터를 바탕으로 투자 전망과 리스크를 분석해주세요.
"""
        
        # Groq API 호출
        completion = groq_client.chat.completions.create(
            model="mixtral-8x7b-32768",
            messages=[
                {
                    "role": "system",
                    "content": "당신은 전문 주식 분석가입니다. 기술적 지표를 바탕으로 객관적이고 전문적인 분석을 제공합니다."
                },
                {
                    "role": "user",
                    "content": prompt
                }
            ],
            temperature=0.7,
            max_tokens=1000
        )
        
        return completion.choices[0].message.content
        
    except Exception as e:
        app.logger.error(f"Groq AI 분석 중 오류: {str(e)}")
        return perform_enhanced_technical_analysis(df, symbol)

def perform_enhanced_technical_analysis(df, symbol):
    """향상된 기술적 분석"""
    latest = df.iloc[-1]
    prev = df.iloc[-2]
    
    # 가격 변동 분석
    price_change = ((latest['Close'] - prev['Close']) / prev['Close']) * 100
    
    # 추세 분석
    sma_20 = df['Close'].tail(20).mean()
    sma_50 = df['Close'].tail(50).mean() if len(df) >= 50 else sma_20
    
    trend = "상승" if latest['Close'] > sma_20 > sma_50 else "하락" if latest['Close'] < sma_20 < sma_50 else "횡보"
    
    # 볼린저 밴드 계산
    std_20 = df['Close'].tail(20).std()
    upper_band = sma_20 + (2 * std_20)
    lower_band = sma_20 - (2 * std_20)
    
    bb_position = "상단" if latest['Close'] > upper_band else "하단" if latest['Close'] < lower_band else "중간"
    
    analysis = f"""
📊 {symbol} 심층 기술적 분석

📈 가격 분석:
- 현재가: ${latest['Close']:.2f} ({price_change:+.2f}%)
- 20일 이동평균: ${sma_20:.2f}
- 추세: {trend}
- 볼린저 밴드 위치: {bb_position}

🔍 기술적 지표:
- RSI ({latest['RSI']:.2f}): {"과매수 구간 - 조정 가능성" if latest['RSI'] > 70 else "과매도 구간 - 반등 가능성" if latest['RSI'] < 30 else "중립 구간"}
- MACD: {"상승 모멘텀" if latest['MACD'] > latest['MACD_signal'] else "하락 모멘텀"}
- CCI ({latest['CCI']:.2f}): {"강한 상승 추세" if latest['CCI'] > 100 else "강한 하락 추세" if latest['CCI'] < -100 else "정상 범위"}
- MFI ({latest['MFI']:.2f}): {"매수 압력 우세" if latest['MFI'] > 50 else "매도 압력 우세"}

💡 종합 의견:
"""
    
    # 종합 점수 계산
    score = 0
    if latest['RSI'] < 70 and latest['RSI'] > 30: score += 1
    if latest['MACD'] > latest['MACD_signal']: score += 1
    if latest['CCI'] > 0: score += 1
    if latest['MFI'] > 50: score += 1
    if trend == "상승": score += 1
    
    if score >= 4:
        analysis += "긍정적인 신호가 우세합니다. 단기적으로 상승 가능성이 높습니다."
    elif score >= 2:
        analysis += "중립적인 상태입니다. 추가적인 모멘텀을 기다려보는 것이 좋습니다."
    else:
        analysis += "부정적인 신호가 많습니다. 신중한 접근이 필요합니다."
    
    analysis += f"\n\n⚠️ 리스크 요인:\n"
    if latest['RSI'] > 70:
        analysis += "- RSI 과매수 구간으로 단기 조정 가능성\n"
    if latest['RSI'] < 30:
        analysis += "- RSI 과매도 구간으로 추가 하락 가능성\n"
    if bb_position == "상단":
        analysis += "- 볼린저 밴드 상단 돌파로 과열 상태\n"
    if latest['MFI'] > 80:
        analysis += "- MFI 과매수 구간으로 매도 압력 증가 가능\n"
    
    return analysis

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/search', methods=['POST'])
def search():
    symbol = request.form.get('symbol', '').upper()
    if not symbol:
        flash('종목 코드를 입력해주세요.')
        return redirect(url_for('index'))
    
    return redirect(url_for('stock_detail', symbol=symbol))

@app.route('/stock/<symbol>')
def stock_detail(symbol):
    df = get_stock_data(symbol)
    if df.empty:
        flash(f'{symbol} 주식 데이터를 찾을 수 없습니다.')
        return redirect(url_for('index'))
    
    df = calculate_indicators(df)
    chart_html = create_chart(df, symbol)
    
    # 현재 가격 정보
    current_price = df['Close'].iloc[-1]
    prev_close = df['Close'].iloc[-2]
    change = current_price - prev_close
    change_pct = (change / prev_close) * 100
    
    # 최신 지표 값
    latest_indicators = {
        'RSI': df['RSI'].iloc[-1],
        'MACD': df['MACD'].iloc[-1],
        'CCI': df['CCI'].iloc[-1],
        'MFI': df['MFI'].iloc[-1]
    }
    
    return render_template('stock_detail.html',
                         symbol=symbol,
                         chart_html=chart_html,
                         current_price=current_price,
                         change=change,
                         change_pct=change_pct,
                         indicators=latest_indicators)

@app.route('/generate_pdf/<symbol>')
def generate_pdf(symbol):
    try:
        df = get_stock_data(symbol)
        if df.empty:
            flash(f'{symbol} 주식 데이터를 찾을 수 없습니다.')
            return redirect(url_for('index'))
            
        df = calculate_indicators(df)
        
        # PDF 생성
        buffer = io.BytesIO()
        doc = SimpleDocTemplate(buffer, pagesize=letter)
        story = []
        
        styles = getSampleStyleSheet()
        title_style = styles['Title']
        normal_style = styles['Normal']
        
        # 제목
        story.append(Paragraph(f"{symbol} 주식 분석 리포트", title_style))
        story.append(Spacer(1, 12))
        
        # 생성 날짜
        story.append(Paragraph(f"생성일: {datetime.now().strftime('%Y-%m-%d %H:%M')}", normal_style))
        story.append(Spacer(1, 12))
        
        # 현재 가격 정보
        current_price = df['Close'].iloc[-1]
        prev_close = df['Close'].iloc[-2]
        change = current_price - prev_close
        change_pct = (change / prev_close) * 100
        
        story.append(Paragraph(f"<b>현재 가격:</b> ${current_price:.2f}", normal_style))
        story.append(Paragraph(f"<b>변동:</b> ${change:.2f} ({change_pct:+.2f}%)", normal_style))
        story.append(Spacer(1, 12))
        
        # 기술적 지표
        story.append(Paragraph("<b>기술적 지표 (최신값)</b>", normal_style))
        story.append(Paragraph(f"RSI: {df['RSI'].iloc[-1]:.2f}", normal_style))
        story.append(Paragraph(f"MACD: {df['MACD'].iloc[-1]:.2f}", normal_style))
        story.append(Paragraph(f"CCI: {df['CCI'].iloc[-1]:.2f}", normal_style))
        story.append(Paragraph(f"MFI: {df['MFI'].iloc[-1]:.2f}", normal_style))
        
        doc.build(story)
        buffer.seek(0)
        
        return send_file(
            buffer,
            as_attachment=True,
            download_name=f'{symbol}_analysis_{datetime.now().strftime("%Y%m%d")}.pdf',
            mimetype='application/pdf'
        )
        
    except Exception as e:
        app.logger.error(f"PDF 생성 중 오류 발생: {str(e)}")
        flash('PDF 생성 중 오류가 발생했습니다.')
        return redirect(url_for('stock_detail', symbol=symbol))

@app.route('/ai_analysis/<symbol>')
def ai_analysis(symbol):
    try:
        df = get_stock_data(symbol)
        if df.empty:
            flash(f'{symbol} 주식 데이터를 찾을 수 없습니다.')
            return redirect(url_for('index'))
            
        df = calculate_indicators(df)
        
        # 기술적 분석 수행
        analysis = perform_technical_analysis(df, symbol)
        
        # 세션에 분석 결과 저장
        session['ai_analysis'] = analysis
        session['ai_analysis_symbol'] = symbol
        
        return redirect(url_for('stock_detail', symbol=symbol))
        
    except Exception as e:
        app.logger.error(f"AI 분석 중 오류 발생: {str(e)}")
        flash('AI 분석 중 오류가 발생했습니다.')
        return redirect(url_for('stock_detail', symbol=symbol))

@app.route('/ai_deep_analysis/<symbol>')
def ai_deep_analysis(symbol):
    try:
        df = get_stock_data(symbol)
        if df.empty:
            flash(f'{symbol} 주식 데이터를 찾을 수 없습니다.')
            return redirect(url_for('index'))
            
        df = calculate_indicators(df)
        
        # AI 심층 분석 수행
        if groq_client:
            analysis = perform_ai_deep_analysis(df, symbol)
        else:
            analysis = perform_enhanced_technical_analysis(df, symbol)
        
        session['ai_deep_analysis'] = analysis
        session['ai_deep_analysis_symbol'] = symbol
        
        return redirect(url_for('stock_detail', symbol=symbol))
        
    except Exception as e:
        app.logger.error(f"AI 심층 분석 중 오류 발생: {str(e)}")
        flash('AI 심층 분석 중 오류가 발생했습니다.')
        return redirect(url_for('stock_detail', symbol=symbol))

if __name__ == '__main__':
    app.run(debug=True)