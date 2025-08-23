col1, col2 = st.columns(2)
                with col1:
                    shares = st.number_input("수량", min_value=0.0, value=0.0, step=0.01)
                with col2:
                    buy_price = st.number_input("매수가", min_value=0.0, value=0.0, step=0.01)
                
                if st.button("💾 포트폴리오 저장", use_container_width=True):
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
        with st.expander("🗑️ 자산 삭제"):
            if all_assets:
                remove_asset = st.selectbox("삭제할 자산", all_assets)
                if st.button("🗑️ 삭제", use_container_width=True):
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
        tab_titles = ["🏠 Dashboard", "📰 Market News", "💼 Portfolio"] + [f"📊 {asset}" for asset in all_assets]
        tabs = st.tabs(tab_titles)
        
        # Dashboard 탭
        with tabs[0]:
            st.markdown("""
            <div style="text-align: center; margin-bottom: 2rem;">
                <h2 style="color: white;">📊 Investment Dashboard</h2>
            </div>
            """, unsafe_allow_html=True)
            
            # 포트폴리오 요약 (있는 경우)
            if st.session_state.portfolio:
                # 현재 가격 가져오기
                current_prices = {}
                for symbol in st.session_state.portfolio.keys():
                    df, _ = get_stock_data(symbol, "1d")
                    if not df.empty:
                        current_prices[symbol] = df['Close'].iloc[-1]
                
                if current_prices:
                    total_value, total_cost, portfolio_details = calculate_portfolio_value(
                        st.session_state.portfolio, current_prices
                    )
                    
                    # 포트폴리오 메트릭
                    st.markdown("""
                    <div class="portfolio-card">
                        <h3 style="margin-bottom: 1.5rem;">💼 Portfolio Overview</h3>
                    </div>
                    """, unsafe_allow_html=True)
                    
                    col1, col2, col3, col4 = st.columns(4)
                    with col1:
                        st.metric(
                            "총 가치",
                            f"${total_value:,.2f}",
                            f"${total_value - total_cost:+,.2f}"
                        )
                    with col2:
                        profit_pct = ((total_value - total_cost) / total_cost * 100) if total_cost > 0 else 0
                        st.metric(
                            "총 수익률",
                            f"{profit_pct:+.2f}%",
                            "수익" if profit_pct > 0 else "손실"
                        )
                    with col3:
                        st.metric("보유 종목", len(st.session_state.portfolio))
                    with col4:
                        avg_profit = np.mean([d['Profit %'] for d in portfolio_details])
                        st.metric("평균 수익률", f"{avg_profit:+.2f}%")
                    
                    st.markdown("<br>", unsafe_allow_html=True)
            
            # 자산 현황 그리드
            st.markdown("""
            <div style="margin-bottom: 1rem;">
                <h3 style="color: white;">📈 Asset Overview</h3>
            </div>
            """, unsafe_allow_html=True)
            
            # 자산을 3열로 표시
            cols = st.columns(3)
            for i, symbol in enumerate(all_assets):
                with cols[i % 3]:
                    df, info = get_stock_data(symbol, "5d")
                    if not df.empty:
                        current = df['Close'].iloc[-1]
                        prev = df['Close'].iloc[-2] if len(df) > 1 else current
                        change = ((current - prev) / prev) * 100
                        
                        # 자산 타입 결정
                        if symbol in st.session_state.crypto_list:
                            icon = "🪙"
                            asset_type = "Crypto"
                        elif symbol in st.session_state.etf_list:
                            icon = "📦"
                            asset_type = "ETF"
                        else:
                            icon = "📈"
                            asset_type = "Stock"
                        
                        # 가격 포맷
                        price_format = f"${current:.2f}" if current > 1 else f"${current:.6f}"
                        
                        # 메트릭 카드
                        st.markdown(f"""
                        <div class="metric-card" style="text-align: center;">
                            <h4 style="color: #667eea; margin-bottom: 0.5rem;">{icon} {symbol}</h4>
                            <p style="font-size: 0.8rem; color: rgba(255,255,255,0.6); margin: 0;">{asset_type}</p>
                            <h2 class="price-highlight" style="color: white; margin: 0.5rem 0;">{price_format}</h2>
                            <p style="color: {'#00ff88' if change >= 0 else '#ff3366'}; font-weight: bold;">
                                {change:+.2f}%
                            </p>
                        </div>
                        """, unsafe_allow_html=True)
                        
                        # 미니 스파크라인 차트
                        fig = go.Figure()
                        fig.add_trace(go.Scatter(
                            x=df.index[-20:],
                            y=df['Close'][-20:],
                            mode='lines',
                            line=dict(
                                color='#00ff88' if change >= 0 else '#ff3366',
                                width=2
                            ),
                            showlegend=False,
                            hoverinfo='none'
                        ))
                        
                        fig.update_layout(
                            height=80,
                            margin=dict(l=0, r=0, t=0, b=0),
                            xaxis=dict(visible=False),
                            yaxis=dict(visible=False),
                            paper_bgcolor='rgba(0,0,0,0)',
                            plot_bgcolor='rgba(0,0,0,0)'
                        )
                        
                        st.plotly_chart(fig, use_container_width=True, config={'displayModeBar': False})
        
        # Market News 탭
        with tabs[1]:
            st.markdown("""
            <div style="text-align: center; margin-bottom: 2rem;">
                <h2 style="color: white;">📰 Latest Market News</h2>
            </div>
            """, unsafe_allow_html=True)
            
            # 뉴스 가져오기
            with st.spinner("Loading latest news..."):
                market_news = get_market_news()
            
            if market_news:
                # 2열로 뉴스 표시
                cols = st.columns(2)
                for i, news_item in enumerate(market_news):
                    with cols[i % 2]:
                        display_news_card(news_item)
            else:
                st.info("📰 뉴스를 불러올 수 없습니다. 나중에 다시 시도해주세요.")
        
        # Portfolio 탭
        with tabs[2]:
            st.markdown("""
            <div style="text-align: center; margin-bottom: 2rem;">
                <h2 style="color: white;">💼 Portfolio Analysis</h2>
            </div>
            """, unsafe_allow_html=True)
            
            if st.session_state.portfolio and current_prices:
                # 포트폴리오 상세 테이블
                portfolio_df = pd.DataFrame(portfolio_details)
                
                # 스타일링된 데이터프레임
                st.dataframe(
                    portfolio_df.style.format({
                        'Buy Price': '${:.2f}',
                        'Current Price': '${:.2f}',
                        'Value': '${:,.2f}',
                        'Cost': '${:,.2f}',
                        'Profit': '${:+,.2f}',
                        'Profit %': '{:+.2f}%',
                        'Weight %': '{:.1f}%'
                    }).background_gradient(subset=['Profit %'], cmap='RdYlGn', vmin=-20, vmax=20),
                    use_container_width=True,
                    height=400
                )
                
                # 포트폴리오 차트
                col1, col2 = st.columns(2)
                
                with col1:
                    # 파이 차트 (포트폴리오 구성)
                    fig = go.Figure(data=[go.Pie(
                        labels=portfolio_df['Symbol'],
                        values=portfolio_df['Value'],
                        hole=.4,
                        marker=dict(
                            colors=['#667eea', '#764ba2', '#f093fb', '#f5576c', '#4facfe', '#00f2fe'],
                            line=dict(color='white', width=2)
                        ),
                        textposition='inside',
                        textinfo='label+percent'
                    )])
                    
                    fig.update_layout(
                        title="Portfolio Composition",
                        height=400,
                        paper_bgcolor='rgba(0,0,0,0)',
                        plot_bgcolor='rgba(0,0,0,0)',
                        font=dict(color='white'),
                        showlegend=False
                    )
                    
                    st.plotly_chart(fig, use_container_width=True)
                
                with col2:
                    # 수익률 바 차트
                    colors_profit = ['#00ff88' if x > 0 else '#ff3366' for x in portfolio_df['Profit %']]
                    
                    fig = go.Figure(data=[
                        go.Bar(
                            x=portfolio_df['Symbol'],
                            y=portfolio_df['Profit %'],
                            marker_color=colors_profit,
                            text=[f"{x:+.1f}%" for x in portfolio_df['Profit %']],
                            textposition='outside'
                        )
                    ])
                    
                    fig.update_layout(
                        title="Individual Returns (%)",
                        height=400,
                        paper_bgcolor='rgba(0,0,0,0)',
                        plot_bgcolor='rgba(0,0,0,0)',
                        font=dict(color='white'),
                        yaxis=dict(
                            gridcolor='rgba(255,255,255,0.1)',
                            zerolinecolor='rgba(255,255,255,0.3)'
                        ),
                        xaxis=dict(gridcolor='rgba(255,255,255,0.1)')
                    )
                    
                    st.plotly_chart(fig, use_container_width=True)
            else:
                st.info("💼 포트폴리오에 자산을 추가하여 분석을 시작하세요.")
        
        # 개별 자산 탭
        for idx, symbol in enumerate(all_assets):
            with tabs[idx + 3]:
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
                    st.markdown(f"""
                    <div>
                        <h2 style="color: white; margin: 0;">{icon} {symbol}</h2>
                        <p style="color: rgba(255,255,255,0.6); margin: 0;">{asset_type} Technical Analysis</p>
                    </div>
                    """, unsafe_allow_html=True)
                
                with col2:
                    period = st.selectbox(
                        "Period",
                        ["1d", "5d", "1mo", "3mo", "6mo", "1y", "2y", "5y"],
                        index=2,
                        key=f"period_{symbol}"
                    )
                
                with col3:
                    if st.button("🔄 Refresh", key=f"refresh_{symbol}"):
                        st.cache_data.clear()
                        st.rerun()
                
                # 데이터 로드
                with st.spinner(f"Loading {symbol} data..."):
                    df, info = get_stock_data(symbol, period)
                
                if not df.empty:
                    # 지표 계산
                    df = calculate_indicators(df)
                    
                    # 기본 정보 메트릭
                    st.markdown("<br>", unsafe_allow_html=True)
                    
                    col1, col2, col3, col4, col5, col6 = st.columns(6)
                    
                    current_price = df['Close'].iloc[-1]
                    prev_close = df['Close'].iloc[-2] if len(df) > 1 else current_price
                    change = current_price - prev_close
                    change_pct = (change / prev_close * 100) if prev_close != 0 else 0
                    
                    with col1:
                        st.metric(
                            "현재가",
                            f"${current_price:.2f}" if current_price > 1 else f"${current_price:.6f}",
                            f"{change_pct:+.2f}%"
                        )
                    
                    with col2:
                        st.metric(
                            "거래량",
                            f"{df['Volume'].iloc[-1]:,.0f}",
                            f"{((df['Volume'].iloc[-1] / df['Volume'].iloc[-2]) - 1) * 100:+.1f}%" if len(df) > 1 else "0%"
                        )
                    
                    with col3:
                        high_52w = df['High'].tail(252).max() if len(df) >= 252 else df['High'].max()
                        st.metric("52주 최고", f"${high_52w:.2f}")
                    
                    with col4:
                        low_52w = df['Low'].tail(252).min() if len(df) >= 252 else df['Low'].min()
                        st.metric("52주 최저", f"${low_52w:.2f}")
                    
                    with col5:
                        if info.get('marketCap'):
                            cap = info['marketCap']
                            if cap > 1e12:
                                cap_str = f"${cap/1e12:.1f}T"
                            elif cap > 1e9:
                                cap_str = f"${cap/1e9:.1f}B"
                            else:
                                cap_str = f"${cap/1e6:.1f}M"
                            st.metric("시가총액", cap_str)
                        else:
                            st.metric("시가총액", "N/A")
                    
                    with col6:
                        if symbol in st.session_state.portfolio:
                            shares = st.session_state.portfolio[symbol]['shares']
                            value = shares * current_price
                            st.metric("보유 가치", f"${value:,.2f}")
                        else:
                            st.metric("보유 가치", "$0")
                    
                    # 고급 차트
                    st.markdown("<br>", unsafe_allow_html=True)
                    chart = create_advanced_chart(df, symbol)
                    st.plotly_chart(chart, use_container_width=True)
                    
                    # 기술적 지표 상세
                    st.markdown("""
                    <div style="margin: 2rem 0;">
                        <h3 style="color: white;">📊 Technical Indicators</h3>
                    </div>
                    """, unsafe_allow_html=True)
                    
                    col1, col2, col3, col4, col5, col6 = st.columns(6)
                    
                    with col1:
                        rsi_val = df['RSI'].iloc[-1] if 'RSI' in df.columns else 50
                        rsi_color = "#ff3366" if rsi_val > 70 else "#00ff88" if rsi_val < 30 else "#ffa500"
                        st.markdown(f"""
                        <div style="text-align: center;">
                            <p style="color: rgba(255,255,255,0.6); margin: 0;">RSI (14)</p>
                            <h3 style="color: {rsi_color}; margin: 0;">{rsi_val:.2f}</h3>
                        </div>
                        """, unsafe_allow_html=True)
                    
                    with col2:
                        if 'MACD' in df.columns and not df['MACD'].isna().all():
                            macd_val = df['MACD'].iloc[-1]
                            macd_signal = df['MACD_signal'].iloc[-1]
                            macd_status = "Buy" if macd_val > macd_signal else "Sell"
                            macd_color = "#00ff88" if macd_status == "Buy" else "#ff3366"
                            st.markdown(f"""
                            <div style="text-align: center;">
                                <p style="color: rgba(255,255,255,0.6); margin: 0;">MACD</p>
                                <h3 style="color: {macd_color}; margin: 0;">{macd_status}</h3>
                            </div>
                            """, unsafe_allow_html=True)
                    
                    with col3:
                        cci_val = df['CCI'].iloc[-1] if 'CCI' in df.columns else 0
                        cci_color = "#ff3366" if cci_val > 100 else "#00ff88" if cci_val < -100 else "#ffa500"
                        st.markdown(f"""
                        <div style="text-align: center;">
                            <p style="color: rgba(255,255,255,0.6); margin: 0;">CCI</p>
                            <h3 style="color: {cci_color}; margin: 0;">{cci_val:.2f}</h3>
                        </div>
                        """, unsafe_allow_html=True)
                    
                    with col4:
                        mfi_val = df['MFI'].iloc[-1] if 'MFI' in df.columns else 50
                        mfi_color = "#ff3366" if mfi_val > 80 else "#00ff88" if mfi_val < 20 else "#ffa500"
                        st.markdown(f"""
                        <div style="text-align: center;">
                            <p style="color: rgba(255,255,255,0.6); margin: 0;">MFI</p>
                            <h3 style="color: {mfi_color}; margin: 0;">{mfi_val:.2f}</h3>
                        </div>
                        """, unsafe_allow_html=True)
                    
                    with col5:
                        if 'Stoch_K' in df.columns:
                            stoch_val = df['Stoch_K'].iloc[-1]
                            stoch_color = "#ff3366" if stoch_val > 80 else "#00ff88" if stoch_val < 20 else "#ffa500"
                            st.markdown(f"""
                            <div style="text-align: center;">
                                <p style="color: rgba(255,255,255,0.6); margin: 0;">Stoch %K</p>
                                <h3 style="color: {stoch_color}; margin: 0;">{stoch_val:.2f}</h3>
                            </div>
                            """, unsafe_allow_html=True)
                    
                    with col6:
                        if 'ATR' in df.columns:
                            atr_val = df['ATR'].iloc[-1]
                            atr_pct = (atr_val / current_price) * 100
                            st.markdown(f"""
                            <div style="text-align: center;">
                                <p style="color: rgba(255,255,255,0.6); margin: 0;">ATR</p>
                                <h3 style="color: white; margin: 0;">{atr_pct:.1f}%</h3>
                            </div>
                            """, unsafe_allow_html=True)
                    
                    # 뉴스 섹션
                    st.markdown("""
                    <div style="margin: 2rem 0;">
                        <h3 style="color: white;">📰 Latest News</h3>
                    </div>
                    """, unsafe_allow_html=True)
                    
                    news = get_stock_news(symbol)
                    if news:
                        news_cols = st.columns(2)
                        for i, article in enumerate(news[:4]):
                            with news_cols[i % 2]:
                                st.markdown(f"""
                                <div class="news-card">
                                    <h5 style="color: #667eea; margin-bottom: 0.5rem;">
                                        {article.get('title', 'N/A')[:80]}...
                                    </h5>
                                    <div style="display: flex; justify-content: space-between; align-items: center;">
                                        <span style="color: rgba(255,255,255,0.5); font-size: 0.8rem;">
                                            {article.get('publisher', '')}
                                        </span>
                                        <a href="{article.get('link', '#')}" target="_blank" 
                                           style="color: #667eea; text-decoration: none; font-size: 0.9rem;">
                                            Read →
                                        </a>
                                    </div>
                                </div>
                                """, unsafe_allow_html=True)
                    else:
                        st.info("📰 이 종목의 최신 뉴스가 없습니다.")
                    
                    # 예측 섹션
                    st.markdown("""
                    <div style="margin: 2rem 0;">
                        <h3 style="color: white;">🔮 Price Prediction (7 Days)</h3>
                    </div>
                    """, unsafe_allow_html=True)
                    
                    predictions = predict_price(df, days=7)
                    if predictions is not None:
                        col1, col2 = st.columns([3, 1])
                        
                        with col1:
                            # 예측 차트
                            pred_fig = go.Figure()
                            
                            # 실제 가격 (최근 30일)
                            pred_fig.add_trace(go.Scatter(
                                x=df.index[-30:],
                                y=df['Close'][-30:],
                                mode='lines',
                                name='Actual Price',
                                line=dict(color='#667eea', width=3)
                            ))
                            
                            # 예측 가격
                            future_dates = pd.date_range(
                                start=df.index[-1] + timedelta(days=1),
                                periods=7
                            )
                            
                            pred_fig.add_trace(go.Scatter(
                                x=future_dates,
                                y=predictions,
                                mode='lines+markers',
                                name='Predicted Price',
                                line=dict(color='#f093fb', width=3, dash='dash'),
                                marker=dict(size=8, color='#f093fb')
                            ))
                            
                            # 신뢰구간 (임의)
                            upper_bound = predictions * 1.02
                            lower_bound = predictions * 0.98
                            
                            pred_fig.add_trace(go.Scatter(
                                x=future_dates,
                                y=upper_bound,
                                mode='lines',
                                name='Upper Bound',
                                line=dict(color='rgba(240, 147, 251, 0.3)', width=1),
                                showlegend=False
                            ))
                            
                            pred_fig.add_trace(go.Scatter(
                                x=future_dates,
                                y=lower_bound,
                                mode='lines',
                                name='Lower Bound',
                                line=dict(color='rgba(240, 147, 251, 0.3)', width=1),
                                fill='tonexty',
                                fillcolor='rgba(240, 147, 251, 0.1)',
                                showlegend=False
                            ))
                            
                            pred_fig.update_layout(
                                height=400,
                                paper_bgcolor='rgba(0,0,0,0)',
                                plot_bgcolor='rgba(15, 12, 41, 0.8)',
                                font=dict(color='white'),
                                xaxis=dict(gridcolor='rgba(255,255,255,0.1)'),
                                yaxis=dict(gridcolor='rgba(255,255,255,0.1)'),
                                legend=dict(
                                    bgcolor='rgba(255,255,255,0.05)',
                                    bordercolor='rgba(255,255,255,0.2)'
                                )
                            )
                            
                            st.plotly_chart(pred_fig, use_container_width=True)
                        
                        with col2:
                            pred_change = ((predictions[-1] - current_price) / current_price) * 100
                            
                            st.markdown(f"""
                            <div class="metric-card">
                                <h4 style="color: white;">Prediction Summary</h4>
                                <hr style="border-color: rgba(255,255,255,0.2);">
                                <p>Current: ${current_price:.2f}</p>
                                <p>7-Day Target: ${predictions[-1]:.2f}</p>
                                <p style="color: {'#00ff88' if pred_change > 0 else '#ff3366'}; font-size: 1.2rem; font-weight: bold;">
                                    Expected: {pred_change:+.2f}%
                                </p>
                                <hr style="border-color: rgba(255,255,255,0.2);">
                                <p style="font-size: 0.8rem; color: rgba(255,255,255,0.6);">
                                    ⚠️ AI prediction for reference only
                                </p>
                            </div>
                            """, unsafe_allow_html=True)
                    
                    # 분석 버튼
                    st.markdown("<br>", unsafe_allow_html=True)
                    
                    col1, col2, col3, col4 = st.columns(4)
                    
                    with col1:
                        if st.button("📊 Technical Analysis", key=f"tech_{symbol}", use_container_width=True):
                            with st.spinner("Analyzing..."):
                                analysis = perform_technical_analysis(df, symbol)
                                st.session_state.analysis_results[f"{symbol}_tech"] = analysis
                    
                    with col2:
                        if st.button("🤖 AI Deep Analysis", key=f"ai_{symbol}", use_container_width=True):
                            with st.spinner("AI is analyzing..."):
                                analysis = perform_ai_analysis(df, symbol, info, asset_type, news)
                                st.session_state.analysis_results[f"{symbol}_ai"] = analysis
                    
                    with col3:
                        if st.button("📄 Generate PDF Report", key=f"pdf_{symbol}", use_container_width=True):
                            with st.spinner("Generating PDF..."):
                                # AI 분석 먼저 수행
                                if f"{symbol}_ai" not in st.session_state.analysis_results:
                                    analysis = perform_ai_analysis(df, symbol, info, asset_type, news)
                                    st.session_state.analysis_results[f"{symbol}_ai"] = analysis
                                
                                pdf_buffer = generate_pdf_report(
                                    df, symbol, info,
                                    st.session_state.analysis_results.get(f"{symbol}_ai")
                                )
                                
                                if pdf_buffer:
                                    st.download_button(
                                        label="📥 Download PDF",
                                        data=pdf_buffer,
                                        file_name=f"{symbol}_report_{datetime.now().strftime('%Y%m%d_%H%M')}.pdf",
                                        mime="application/pdf",
                                        use_container_width=True
                                    )
                    
                    with col4:
                        if st.button("🔄 Clear Analysis", key=f"clear_{symbol}", use_container_width=True):
                            keys_to_remove = [k for k in st.session_state.analysis_results.keys() if k.startswith(symbol)]
                            for key in keys_to_remove:
                                del st.session_state.analysis_results[key]
                            st.success("✅ Analysis cleared")
                    
                    # 분석 결과 표시
                    if f"{symbol}_tech" in st.session_state.analysis_results:
                        with st.expander("📊 Technical Analysis Results", expanded=True):
                            st.markdown(st.session_state.analysis_results[f"{symbol}_tech"])
                    
                    if f"{symbol}_ai" in st.session_state.analysis_results:
                        with st.expander("🤖 AI Analysis Results", expanded=True):
                            st.markdown(st.session_state.analysis_results[f"{symbol}_ai"])
                
                else:
                    st.error(f"❌ Unable to load data for {symbol}")
    
    else:
        # 자산이 없을 때 대시보드
        st.markdown("""
        <div style="text-align: center; padding: 5rem;">
            <h1 style="color: white; font-size: 3rem;">👋 Welcome to SmartInvestor Pro!</h1>
            <p style="color: rgba(255,255,255,0.7); font-size: 1.2rem; margin: 2rem 0;">
                Start building your investment portfolio by adding assets from the sidebar.
            </p>
            <div style="background: linear-gradient(135deg, rgba(255,255,255,0.1) 0%, rgba(255,255,255,0.05) 100%);
                        border: 1px solid rgba(255,255,255,0.2);
                        border-radius: 20px;
                        padding: 2rem;
                        margin: 2rem auto;
                        max-width: 800px;">
                <h3 style="color: #667eea; margin-bottom: 1rem;">🚀 Quick Start Guide</h3>
                <div style="text-align: left;">
                    <p style="color: rgba(255,255,255,0.8); margin: 0.5rem 0;">
                        1️⃣ Click <strong>➕ 자산 추가</strong> in the sidebar
                    </p>
                    <p style="color: rgba(255,255,255,0.8); margin: 0.5rem 0;">
                        2️⃣ Choose asset type: Stocks, Crypto, or ETF
                    </p>
                    <p style="color: rgba(255,255,255,0.8); margin: 0.5rem 0;">
                        3️⃣ Enter symbol or select from trending picks
                    </p>
                    <p style="color: rgba(255,255,255,0.8); margin: 0.5rem 0;">
                        4️⃣ Track your portfolio and analyze with AI
                    </p>
                </div>
            </div>
            <div style="display: flex; justify-content: center; gap: 2rem; margin-top: 3rem;">
                <div style="text-align: center;">
                    <h2 style="color: #667eea;">📈</h2>
                    <p style="color: rgba(255,255,255,0.6);">Stocks</p>
                </div>
                <div style="text-align: center;">
                    <h2 style="color: #764ba2;">🪙</h2>
                    <p style="color: rgba(255,255,255,0.6);">Crypto</p>
                </div>
                <div style="text-align: center;">
                    <h2 style="color: #f093fb;">📦</h2>
                    <p style="color: rgba(255,255,255,0.6);">ETFs</p>
                </div>
            </div>
        </div>
        """, unsafe_allow_html=True)

# 푸터
st.markdown("---")
st.markdown("""
<div style="text-align: center; padding: 2rem;">
    <p style="color: rgba(255,255,255,0.6); margin: 0;">
        💎 SmartInvestor Pro | AI-Powered Investment Analysis Platform
    </p>
    <p style="color: rgba(255,255,255,0.4); font-size: 0.9rem; margin: 0.5rem 0;">
        Last updated: {datetime.now().strftime('%Y-%m-%d %H:%M')} | Made with ❤️ by SmartInvestor Team
    </p>
</div>
""".format(datetime=datetime), unsafe_allow_html=True)    fig.update_yaxes(title_text="가격", row=1, col=1, secondary_y=False)
    fig.update_yaxes(title_text="거래량", row=1, col=1, secondary_y=True)
    fig.update_yaxes(title_text="RSI", row=2, col=1)
    fig.update_yaxes(title_text="MACD", row=3, col=1)
    fig.update_yaxes(title_text="Stochastic", row=4, col=1)
    fig.update_yaxes(title_text="MFI", row=5, col=1)
    
    return fig

def predict_price(df, days=7):
    """AI 기반 가격 예측"""
    if df is None or df.empty or len(df) < 50:
        return None
    
    try:
        prices = df['Close'].values
        
        # 1. 트렌드 분석
        x = np.arange(len(prices))
        z = np.polyfit(x, prices, 2)  # 2차 다항식
        p = np.poly1d(z)
        
        # 2. 계절성 분석 (주기적 패턴)
        from scipy import signal
        detrended = signal.detrend(prices)
        
        # 3. 변동성 분석
        returns = np.diff(prices) / prices[:-1]
        volatility = np.std(returns) * np.sqrt(252)  # 연간 변동성
        
        # 4. 예측 생성
        future_x = np.arange(len(prices), len(prices) + days)
        trend_pred = p(future_x)
        
        # 5. 몬테카를로 시뮬레이션
        predictions = []
        for i in range(days):
            if i == 0:
                last_price = prices[-1]
            else:
                last_price = predictions[-1]
            
            # 일일 수익률 시뮬레이션
            daily_return = np.random.normal(0.0005, volatility/np.sqrt(252))
            pred_price = last_price * (1 + daily_return)
            
            # 트렌드 조정
            trend_factor = trend_pred[i] / trend_pred[0]
            pred_price = pred_price * trend_factor
            
            predictions.append(pred_price)
        
        return np.array(predictions)
    except:
        return None

def calculate_portfolio_value(portfolio, current_prices):
    """포트폴리오 가치 계산"""
    total_value = 0
    total_cost = 0
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
            total_cost += cost
            
            portfolio_details.append({
                'Symbol': symbol,
                'Shares': shares,
                'Buy Price': buy_price,
                'Current Price': current_price,
                'Value': value,
                'Cost': cost,
                'Profit': profit,
                'Profit %': profit_pct,
                'Weight %': 0  # 나중에 계산
            })
    
    # 포트폴리오 비중 계산
    if total_value > 0:
        for detail in portfolio_details:
            detail['Weight %'] = (detail['Value'] / total_value) * 100
    
    return total_value, total_cost, portfolio_details

def display_news_card(news_item):
    """뉴스 카드 표시"""
    with st.container():
        st.markdown(f"""
        <div class="news-card">
            <h4 style="color: #667eea; margin-bottom: 0.5rem;">{news_item['title']}</h4>
            <p style="color: rgba(255,255,255,0.7); font-size: 0.9rem; margin-bottom: 0.5rem;">
                {news_item.get('summary', '')}
            </p>
            <div style="display: flex; justify-content: space-between; align-items: center;">
                <span style="color: rgba(255,255,255,0.5); font-size: 0.8rem;">
                    {news_item.get('publisher', news_item.get('source', ''))}
                </span>
                <a href="{news_item['link']}" target="_blank" style="color: #667eea; text-decoration: none;">
                    Read More →
                </a>
            </div>
        </div>
        """, unsafe_allow_html=True)

def perform_ai_analysis(df, symbol, info, asset_type="주식", news=None):
    """AI 기반 종합 분석"""
    if not groq_client:
        return perform_technical_analysis(df, symbol)
    
    try:
        latest = df.iloc[-1]
        
        # 뉴스 요약
        news_summary = ""
        if news and len(news) > 0:
            news_summary = "\n[최신 뉴스 헤드라인]\n"
            for i, article in enumerate(news[:5]):
                news_summary += f"{i+1}. {article.get('title', '')}\n"
        
        # 기술적 지표 준비
        indicators = {
            'RSI': latest.get('RSI', 0),
            'MACD': latest.get('MACD', 0),
            'MACD_signal': latest.get('MACD_signal', 0),
            'CCI': latest.get('CCI', 0),
            'MFI': latest.get('MFI', 0),
            'ATR': latest.get('ATR', 0),
            'BB_upper': latest.get('BB_upper', 0),
            'BB_lower': latest.get('BB_lower', 0)
        }
        
        # 추세 분석
        sma_20 = df['SMA_20'].iloc[-1] if 'SMA_20' in df.columns else 0
        sma_50 = df['SMA_50'].iloc[-1] if 'SMA_50' in df.columns and not pd.isna(df['SMA_50'].iloc[-1]) else 0
        
        # 변동성
        volatility = df['Close'].pct_change().std() * np.sqrt(252) * 100
        
        prompt = f"""
        당신은 한국의 최고 투자 전문가입니다. {symbol} {asset_type}에 대한 종합적인 분석을 제공해주세요.
        
        [기본 정보]
        - 자산: {symbol} ({asset_type})
        - 현재가: ${latest['Close']:.2f}
        - 거래량: {latest['Volume']:,.0f}
        - 52주 최고/최저: ${df['High'].tail(252).max():.2f} / ${df['Low'].tail(252).min():.2f}
        
        [기술적 지표]
        - RSI: {indicators['RSI']:.2f}
        - MACD: {indicators['MACD']:.2f} (Signal: {indicators['MACD_signal']:.2f})
        - CCI: {indicators['CCI']:.2f}
        - MFI: {indicators['MFI']:.2f}
        - ATR (변동성): {indicators['ATR']:.2f}
        - 볼린저 밴드: ${indicators['BB_lower']:.2f} - ${indicators['BB_upper']:.2f}
        
        [이동평균]
        - 20일: ${sma_20:.2f} ({'상승' if latest['Close'] > sma_20 else '하락'} 추세)
        - 50일: ${sma_50:.2f} ({'상승' if latest['Close'] > sma_50 else '하락'} 추세)
        
        [시장 상황]
        - 연간 변동성: {volatility:.2f}%
        {news_summary}
        
        다음 항목들을 포함하여 전문적이고 실용적인 분석을 한국어로 제공해주세요:
        
        1. 📊 현재 시장 상태 진단
           - 기술적 지표들의 종합적 해석
           - 현재 추세와 모멘텀 평가
           
        2. 📈 가격 전망
           - 단기 (1-2주): 구체적인 목표 가격대
           - 중기 (1-3개월): 예상 시나리오
           
        3. 🎯 매매 전략
           - 진입 가격: 구체적인 수치
           - 1차 목표가: +X%
           - 2차 목표가: +X%
           - 손절가: -X%
           
        4. ⚠️ 리스크 분석
           - 주요 리스크 요인 3가지
           - 리스크 관리 방안
           
        5. 💡 투자 포인트
           - 이 종목의 핵심 투자 포인트
           - 투자 시 주의사항
        
        구체적인 숫자와 명확한 의견을 제시하고, 실제 투자에 도움이 되는 실용적인 조언을 제공해주세요.
        """
        
        completion = groq_client.chat.completions.create(
            model="llama3-8b-8192",
            messages=[
                {
                    "role": "system",
                    "content": "당신은 20년 경력의 한국 최고의 투자 전문가입니다. 기술적 분석, 시장 심리, 리스크 관리에 정통하며, 구체적이고 실용적인 투자 조언을 제공합니다. 모든 답변은 한국어로 작성하며, 전문 용어는 이해하기 쉽게 설명합니다."
                },
                {
                    "role": "user",
                    "content": prompt
                }
            ],
            temperature=0.7,
            max_tokens=2000
        )
        
        return f"""
## 🤖 AI 투자 분석 리포트

### 📅 분석 일시: {datetime.now().strftime('%Y-%m-%d %H:%M')}

{completion.choices[0].message.content}

---
*이 분석은 AI가 생성한 참고 자료이며, 투자 결정은 본인의 판단에 따라 신중히 내리시기 바랍니다.*
"""
        
    except Exception as e:
        return perform_technical_analysis(df, symbol)

def perform_technical_analysis(df, symbol):
    """기본 기술적 분석"""
    if df.empty:
        return "데이터가 부족합니다."
    
    latest = df.iloc[-1]
    
    # 지표 계산
    rsi = latest.get('RSI', 50)
    macd = latest.get('MACD', 0)
    macd_signal = latest.get('MACD_signal', 0)
    cci = latest.get('CCI', 0)
    mfi = latest.get('MFI', 50)
    
    # 추세 판단
    sma_20 = df['SMA_20'].iloc[-1] if 'SMA_20' in df.columns else latest['Close']
    trend = "상승" if latest['Close'] > sma_20 else "하락"
    
    # 매매 신호
    signals = []
    if rsi < 30:
        signals.append("🟢 RSI 과매도 - 매수 신호")
    elif rsi > 70:
        signals.append("🔴 RSI 과매수 - 매도 신호")
    
    if macd > macd_signal:
        signals.append("🟢 MACD 골든크로스 - 매수 신호")
    else:
        signals.append("🔴 MACD 데드크로스 - 매도 신호")
    
    if cci < -100:
        signals.append("🟢 CCI 과매도 - 매수 신호")
    elif cci > 100:
        signals.append("🔴 CCI 과매수 - 매도 신호")
    
    # 종합 점수
    buy_signals = len([s for s in signals if "🟢" in s])
    sell_signals = len([s for s in signals if "🔴" in s])
    
    if buy_signals > sell_signals:
        overall = "💚 매수 우위"
    elif sell_signals > buy_signals:
        overall = "❤️ 매도 우위"
    else:
        overall = "💛 중립/관망"
    
    return f"""
## 📊 {symbol} 기술적 분석

### 📈 현재 상태
- **현재가**: ${latest['Close']:.2f}
- **추세**: {trend} (20일 이동평균 기준)
- **종합 판단**: {overall}

### 📉 주요 지표
- **RSI (14)**: {rsi:.2f}
- **MACD**: {macd:.2f} (Signal: {macd_signal:.2f})
- **CCI**: {cci:.2f}
- **MFI**: {mfi:.2f}

### 🎯 매매 신호
{chr(10).join(signals)}

### 💡 투자 제안
- 단기: {'매수 타이밍 관찰' if buy_signals > sell_signals else '매도 타이밍 관찰' if sell_signals > buy_signals else '관망 권장'}
- 중기: 추세 전환 신호 주시 필요

---
*기술적 분석은 참고용이며, 펀더멘털과 시장 상황을 종합적으로 고려하여 투자하시기 바랍니다.*
"""

def generate_pdf_report(df, symbol, info, analysis=None):
    """전문적인 PDF 리포트 생성"""
    try:
        buffer = BytesIO()
        doc = SimpleDocTemplate(buffer, pagesize=letter, topMargin=50, bottomMargin=50)
        story = []
        
        # 스타일 정의
        styles = getSampleStyleSheet()
        
        # 커스텀 스타일
        title_style = ParagraphStyle(
            'CustomTitle',
            parent=styles['Title'],
            fontSize=24,
            textColor=colors.HexColor('#1e3a8a'),
            spaceAfter=30,
            alignment=TA_CENTER
        )
        
        heading_style = ParagraphStyle(
            'CustomHeading',
            parent=styles['Heading2'],
            fontSize=16,
            textColor=colors.HexColor('#3b82f6'),
            spaceAfter=12,
            spaceBefore=20
        )
        
        # 제목 페이지
        story.append(Paragraph(f"{symbol} Investment Analysis Report", title_style))
        story.append(Spacer(1, 20))
        story.append(Paragraph(f"Generated on {datetime.now().strftime('%Y-%m-%d %H:%M')}", styles['Normal']))
        story.append(Paragraph(f"Analyst: {st.session_state.get('username', 'SmartInvestor AI')}", styles['Normal']))
        story.append(PageBreak())
        
        # 요약 정보
        story.append(Paragraph("Executive Summary", heading_style))
        
        current_price = df['Close'].iloc[-1]
        prev_close = df['Close'].iloc[-2] if len(df) > 1 else current_price
        change_pct = ((current_price - prev_close) / prev_close * 100) if prev_close != 0 else 0
        
        summary_data = [
            ["Metric", "Value"],
            ["Current Price", f"${current_price:.2f}"],
            ["Daily Change", f"{change_pct:+.2f}%"],
            ["Volume", f"{df['Volume'].iloc[-1]:,.0f}"],
            ["52-Week High", f"${df['High'].tail(252).max():.2f}" if len(df) >= 252 else "N/A"],
            ["52-Week Low", f"${df['Low'].tail(252).min():.2f}" if len(df) >= 252 else "N/A"],
            ["Market Cap", f"${info.get('marketCap', 0):,.0f}" if info.get('marketCap') else "N/A"]
        ]
        
        summary_table = Table(summary_data, colWidths=[150, 200])
        summary_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#3b82f6')),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, 0), 12),
            ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
            ('BACKGROUND', (0, 1), (-1, -1), colors.beige),
            ('GRID', (0, 0), (-1, -1), 1, colors.black)
        ]))
        story.append(summary_table)
        
        # 기술적 지표
        story.append(Paragraph("Technical Indicators", heading_style))
        
        latest = df.iloc[-1]
        indicators_data = [
            ["Indicator", "Value", "Signal"],
            ["RSI (14)", f"{latest.get('RSI', 0):.2f}", "Overbought" if latest.get('RSI', 50) > 70 else "Oversold" if latest.get('RSI', 50) < 30 else "Neutral"],
            ["MACD", f"{latest.get('MACD', 0):.2f}", "Buy" if latest.get('MACD', 0) > latest.get('MACD_signal', 0) else "Sell"],
            ["CCI", f"{latest.get('CCI', 0):.2f}", "Overbought" if latest.get('CCI', 0) > 100 else "Oversold" if latest.get('CCI', 0) < -100 else "Neutral"],
            ["MFI", f"{latest.get('MFI', 0):.2f}", "Overbought" if latest.get('MFI', 50) > 80 else "Oversold" if latest.get('MFI', 50) < 20 else "Neutral"]
        ]
        
        indicators_table = Table(indicators_data, colWidths=[100, 100, 150])
        indicators_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#3b82f6')),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, 0), 12),
            ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
            ('BACKGROUND', (0, 1), (-1, -1), colors.lightgrey),
            ('GRID', (0, 0), (-1, -1), 1, colors.black)
        ]))
        story.append(indicators_table)
        
        # AI 분석 추가 (있는 경우)
        if analysis:
            story.append(PageBreak())
            story.append(Paragraph("AI Analysis", heading_style))
            
            # 분석 내용을 단락으로 나누어 추가
            analysis_lines = analysis.split('\n')
            for line in analysis_lines:
                if line.strip():
                    if line.startswith('##'):
                        story.append(Paragraph(line.replace('##', '').strip(), heading_style))
                    elif line.startswith('###'):
                        story.append(Paragraph(line.replace('###', '').strip(), styles['Heading3']))
                    else:
                        story.append(Paragraph(line, styles['Normal']))
                    story.append(Spacer(1, 6))
        
        # 면책 조항
        story.append(PageBreak())
        story.append(Paragraph("Disclaimer", heading_style))
        disclaimer_text = """
        This report is for informational purposes only and should not be considered as investment advice. 
        Past performance is not indicative of future results. Always conduct your own research and consult 
        with qualified financial advisors before making investment decisions.
        """
        story.append(Paragraph(disclaimer_text, styles['Normal']))
        
        doc.build(story)
        buffer.seek(0)
        return buffer
        
    except Exception as e:
        st.error(f"PDF 생성 오류: {str(e)}")
        return None

# 로그인 페이지
if not st.session_state.authenticated:
    # 배경 애니메이션
    st.markdown("""
    <div style="text-align: center; padding: 3rem;">
        <h1 style="color: white; font-size: 3rem; margin-bottom: 0.5rem;">
            💎 SmartInvestor Pro
        </h1>
        <p style="color: rgba(255,255,255,0.7); font-size: 1.2rem;">
            AI-Powered Investment Analysis Platform
        </p>
    </div>
    """, unsafe_allow_html=True)
    
    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        with st.form("login_form"):
            st.markdown("<h2 style='text-align: center; color: white;'>🔐 로그인</h2>", unsafe_allow_html=True)
            username = st.text_input("사용자명", placeholder="Username")
            password = st.text_input("비밀번호", type="password", placeholder="Password")
            
            col1, col2 = st.columns(2)
            with col1:
                login_button = st.form_submit_button("로그인", use_container_width=True)
            with col2:
                register_button = st.form_submit_button("회원가입", use_container_width=True)
            
            if login_button:
                if login(username, password):
                    st.success("✅ 로그인 성공!")
                    st.rerun()
                else:
                    st.error("❌ 로그인 실패. 사용자명과 비밀번호를 확인하세요.")
            
            if register_button:
                if username and password:
                    if username not in st.session_state.user_data:
                        st.session_state.user_data[username] = {
                            "password": hash_password(password),
                            "is_admin": False,
                            "created_at": datetime.now().isoformat(),
                            "portfolios": {"stocks": [], "crypto": [], "etf": []},
                            "portfolio": {},
                            "theme": "dark"
                        }
                        save_user_data(st.session_state.user_data)
                        st.success("✅ 회원가입 완료! 로그인해주세요.")
                    else:
                        st.error("❌ 이미 존재하는 사용자명입니다.")
                else:
                    st.error("❌ 사용자명과 비밀번호를 입력해주세요.")
        
        with st.expander("📌 Demo Account"):
            st.info("""
            **테스트 계정**
            - Username: admin
            - Password: admin123
            """)

# 메인 앱
else:
    # 상단 헤더
    header_col1, header_col2, header_col3 = st.columns([1, 3, 1])
    with header_col1:
        st.markdown(f"""
        <div style="text-align: center;">
            <h3 style="color: white; margin: 0;">👤 {st.session_state.username}</h3>
            <p style="color: rgba(255,255,255,0.6); font-size: 0.9rem; margin: 0;">
                {'🔧 Admin' if st.session_state.is_admin else '📊 Investor'}
            </p>
        </div>
        """, unsafe_allow_html=True)
    
    with header_col2:
        st.markdown("""
        <div style="text-align: center;">
            <h1 style="color: white; margin: 0;">💎 SmartInvestor Pro</h1>
            <p style="color: rgba(255,255,255,0.6); font-size: 1rem; margin: 0;">
                Real-time Market Analysis & Portfolio Management
            </p>
        </div>
        """, unsafe_allow_html=True)
    
    with header_col3:
        col1, col2 = st.columns(2)
        with col1:
            if st.button("💾 저장"):
                save_current_user_data()
                st.success("✅ 저장됨")
        with col2:
            if st.button("🚪 로그아웃"):
                logout()
                st.rerun()
    
    st.markdown("---")
    
    # 사이드바
    with st.sidebar:
        st.markdown("""
        <div style="text-align: center; padding: 1rem;">
            <h2 style="color: white;">📊 Portfolio Manager</h2>
        </div>
        """, unsafe_allow_html=True)
        
        # 자산 추가 섹션
        with st.expander("➕ 자산 추가", expanded=True):
            asset_type = st.selectbox(
                "자산 유형",
                ["📈 주식", "🪙 암호화폐", "📦 ETF"],
                format_func=lambda x: x
            )
            
            if "암호화폐" in asset_type:
                symbol_input = st.text_input("심볼", placeholder="BTC-USD")
                
                # 트렌딩 크립토
                st.markdown("### 🔥 Trending Cryptos")
                for category, cryptos in TRENDING_CRYPTOS.items():
                    st.markdown(f"**{category}**")
                    cols = st.columns(3)
                    for i, crypto in enumerate(cryptos):
                        with cols[i % 3]:
                            if st.button(crypto.split('-')[0], key=f"add_{crypto}"):
                                if crypto not in st.session_state.crypto_list:
                                    st.session_state.crypto_list.append(crypto)
                                    save_current_user_data()
                                    st.success(f"✅ {crypto}")
            
            elif "주식" in asset_type:
                symbol_input = st.text_input("심볼", placeholder="AAPL")
                
                # 인기 주식
                st.markdown("### 🌟 Popular Stocks")
                selected_category = st.selectbox("카테고리", list(POPULAR_STOCKS.keys()))
                cols = st.columns(3)
                for i, stock in enumerate(POPULAR_STOCKS[selected_category]):
                    with cols[i % 3]:
                        if st.button(stock, key=f"add_{stock}"):
                            if stock not in st.session_state.stock_list:
                                st.session_state.stock_list.append(stock)
                                save_current_user_data()
                                st.success(f"✅ {stock}")
            
            else:  # ETF
                symbol_input = st.text_input("심볼", placeholder="SPY")
            
            if st.button("➕ 추가", use_container_width=True):
                if symbol_input:
                    symbol = symbol_input.upper()
                    if "암호화폐" in asset_type and not symbol.endswith("-USD"):
                        symbol += "-USD"
                    
                    target_list = (st.session_state.stock_list if "주식" in asset_type 
                                  else st.session_state.crypto_list if "암호화폐" in asset_type
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
                            st.error("❌ 유효하지 않은 심볼입니다.")
                    else:
                        st.warning("⚠️ 이미 추가된 심볼입니다.")
        
        # 포트폴리오 관리
        with st.expander("💼 포트폴리오 관리"):
            all_assets = st.session_state.stock_list + st.session_state.crypto_list + st.session_state.etf_list
            
            if all_assets:
                selected_asset = st.selectbox("자산 선택", all_assets)
                
                col1, col2 = st.columns(2)
                with col1:
                    shares = st.number_input("import streamlit as st
import yfinance as yf
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import ta
from datetime import datetime, timedelta
from io import BytesIO
from reportlab.lib.pagesizes import letter
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, PageBreak
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib import colors
from reportlab.lib.units import inch
from reportlab.lib.enums import TA_CENTER, TA_JUSTIFY
import os
import numpy as np
import json
import hashlib
import requests
from bs4 import BeautifulSoup
import feedparser

try:
    from groq import Groq
    GROQ_AVAILABLE = True
except ImportError:
    GROQ_AVAILABLE = False

# 페이지 설정
st.set_page_config(
    page_title="SmartInvestor Pro - AI 투자 분석 플랫폼",
    page_icon="💎",
    layout="wide",
    initial_sidebar_state="expanded"
)

# 모던 UI CSS
st.markdown("""
<style>
    /* 전체 배경 및 폰트 */
    .stApp {
        background: linear-gradient(to bottom, #0f0c29, #302b63, #24243e);
    }
    
    /* 메인 컨테이너 */
    .main > div {
        padding: 2rem;
        background: rgba(255, 255, 255, 0.02);
        border-radius: 20px;
        backdrop-filter: blur(10px);
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
        box-shadow: 0 4px 15px rgba(102, 126, 234, 0.4);
    }
    
    .stButton > button:hover {
        transform: translateY(-2px);
        box-shadow: 0 6px 20px rgba(102, 126, 234, 0.6);
    }
    
    /* 메트릭 카드 */
    div[data-testid="metric-container"] {
        background: linear-gradient(135deg, rgba(255,255,255,0.1) 0%, rgba(255,255,255,0.05) 100%);
        border: 1px solid rgba(255,255,255,0.1);
        padding: 1.5rem;
        border-radius: 15px;
        box-shadow: 0 8px 32px rgba(0,0,0,0.1);
        backdrop-filter: blur(10px);
    }
    
    div[data-testid="metric-container"] > div {
        color: white !important;
    }
    
    /* 탭 스타일 */
    .stTabs [data-baseweb="tab-list"] {
        background: rgba(255,255,255,0.05);
        border-radius: 15px;
        padding: 0.5rem;
        gap: 0.5rem;
    }
    
    .stTabs [data-baseweb="tab"] {
        background: transparent;
        color: rgba(255,255,255,0.7);
        border-radius: 10px;
        padding: 0.75rem 1.5rem;
        font-weight: 500;
    }
    
    .stTabs [aria-selected="true"] {
        background: linear-gradient(45deg, #667eea 0%, #764ba2 100%);
        color: white;
    }
    
    /* 사이드바 */
    .css-1d391kg {
        background: rgba(15, 12, 41, 0.9);
        backdrop-filter: blur(10px);
    }
    
    /* 입력 필드 */
    .stTextInput > div > div > input,
    .stSelectbox > div > div > select,
    .stNumberInput > div > div > input {
        background: rgba(255,255,255,0.1);
        border: 1px solid rgba(255,255,255,0.2);
        color: white;
        border-radius: 10px;
    }
    
    /* Expander */
    .streamlit-expanderHeader {
        background: rgba(255,255,255,0.05);
        border-radius: 10px;
        color: white;
    }
    
    /* 헤더 스타일 */
    h1, h2, h3 {
        color: white !important;
        font-weight: 700 !important;
    }
    
    /* 뉴스 카드 */
    .news-card {
        background: linear-gradient(135deg, rgba(255,255,255,0.1) 0%, rgba(255,255,255,0.05) 100%);
        border: 1px solid rgba(255,255,255,0.1);
        border-radius: 15px;
        padding: 1.5rem;
        margin: 1rem 0;
        transition: all 0.3s ease;
    }
    
    .news-card:hover {
        transform: translateY(-2px);
        box-shadow: 0 8px 32px rgba(102, 126, 234, 0.3);
    }
    
    /* 차트 배경 */
    .js-plotly-plot {
        background: rgba(255,255,255,0.02) !important;
        border-radius: 15px;
        padding: 1rem;
    }
    
    /* 로딩 애니메이션 */
    .stSpinner > div {
        border-color: #667eea !important;
    }
    
    /* Success/Error/Warning/Info 박스 */
    .stAlert {
        background: rgba(255,255,255,0.1);
        border: 1px solid rgba(255,255,255,0.2);
        border-radius: 10px;
        color: white;
    }
    
    /* 포트폴리오 카드 */
    .portfolio-card {
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        border-radius: 20px;
        padding: 2rem;
        color: white;
        box-shadow: 0 10px 40px rgba(102, 126, 234, 0.3);
    }
    
    /* 가격 애니메이션 */
    @keyframes pulse {
        0% { transform: scale(1); }
        50% { transform: scale(1.05); }
        100% { transform: scale(1); }
    }
    
    .price-highlight {
        animation: pulse 2s infinite;
    }
</style>
""", unsafe_allow_html=True)

# 사용자 데이터 파일
USER_DATA_FILE = "user_data.json"
ADMIN_USERNAME = "admin"

# 뉴스 소스
NEWS_SOURCES = {
    'investing': 'https://www.investing.com/rss/news.rss',
    'cnbc': 'https://www.cnbc.com/id/100003114/device/rss/rss.html',
    'yahoo': 'https://finance.yahoo.com/rss/',
    'reuters': 'http://feeds.reuters.com/reuters/businessNews'
}

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
                "watchlist": [],
                "theme": "dark"
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
if 'news_cache' not in st.session_state:
    st.session_state.news_cache = {}

# Groq 클라이언트
groq_client = None
if GROQ_AVAILABLE and st.secrets.get("GROQ_API_KEY"):
    groq_client = Groq(api_key=st.secrets["GROQ_API_KEY"])

# 추천 목록
TRENDING_CRYPTOS = {
    "🔥 핫 밈코인": ["DOGE-USD", "SHIB-USD", "PEPE-USD", "FLOKI-USD", "BONK-USD"],
    "🤖 AI & 메타버스": ["FET-USD", "RNDR-USD", "SAND-USD", "MANA-USD", "AXS-USD"],
    "⚡ DeFi 블루칩": ["UNI-USD", "AAVE-USD", "SUSHI-USD", "COMP-USD", "CRV-USD"],
    "🌟 Layer 1&2": ["ETH-USD", "SOL-USD", "AVAX-USD", "MATIC-USD", "ARB-USD"],
    "💎 거래소 토큰": ["BNB-USD", "FTT-USD", "CRO-USD", "KCS-USD", "OKB-USD"]
}

POPULAR_STOCKS = {
    "🚀 테크 대장주": ["AAPL", "GOOGL", "MSFT", "AMZN", "META", "NVDA", "TSLA"],
    "🇰🇷 한국 대표주": ["005930.KS", "000660.KS", "035720.KS", "051910.KS", "035420.KS"],
    "💊 헬스케어": ["JNJ", "UNH", "PFE", "ABBV", "LLY", "MRK", "TMO"],
    "🏦 금융": ["JPM", "BAC", "WFC", "GS", "MS", "BRK-B", "V"],
    "🎮 게임 & 엔터": ["ATVI", "EA", "TTWO", "NFLX", "DIS", "WBD"]
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
    for key in ['authenticated', 'username', 'is_admin', 'stock_list', 
                'crypto_list', 'etf_list', 'portfolio', 'analysis_results']:
        if key in st.session_state:
            st.session_state[key] = [] if key.endswith('list') else {} if key.endswith('results') or key == 'portfolio' else False

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

# 뉴스 가져오기 함수들
@st.cache_data(ttl=1800)  # 30분 캐시
def fetch_rss_news(feed_url, limit=5):
    """RSS 피드에서 뉴스 가져오기"""
    try:
        feed = feedparser.parse(feed_url)
        news_items = []
        
        for entry in feed.entries[:limit]:
            news_item = {
                'title': entry.title,
                'link': entry.link,
                'published': entry.get('published', ''),
                'summary': entry.get('summary', '')[:200] + '...' if entry.get('summary') else '',
                'source': feed.feed.title if hasattr(feed.feed, 'title') else 'RSS Feed'
            }
            news_items.append(news_item)
        
        return news_items
    except:
        return []

@st.cache_data(ttl=600)  # 10분 캐시
def get_stock_news(symbol):
    """주식 관련 뉴스 가져오기"""
    try:
        ticker = yf.Ticker(symbol)
        news = ticker.news
        
        news_items = []
        for item in news[:10]:
            news_items.append({
                'title': item.get('title', ''),
                'link': item.get('link', ''),
                'publisher': item.get('publisher', ''),
                'providerPublishTime': item.get('providerPublishTime', 0),
                'type': item.get('type', ''),
                'thumbnail': item.get('thumbnail', {}).get('resolutions', [{}])[0].get('url', '') if item.get('thumbnail') else ''
            })
        
        return news_items
    except:
        return []

@st.cache_data(ttl=1800)
def get_market_news():
    """전체 시장 뉴스 가져오기"""
    all_news = []
    
    for source, url in NEWS_SOURCES.items():
        news_items = fetch_rss_news(url, 3)
        all_news.extend(news_items)
    
    # 시간순 정렬
    all_news.sort(key=lambda x: x.get('published', ''), reverse=True)
    
    return all_news[:15]

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
        
        # 볼린저 밴드
        bollinger = ta.volatility.BollingerBands(df['Close'])
        df['BB_upper'] = bollinger.bollinger_hband()
        df['BB_middle'] = bollinger.bollinger_mavg()
        df['BB_lower'] = bollinger.bollinger_lband()
        
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
        df['SMA_50'] = ta.trend.sma_indicator(df['Close'], window=50) if len(df) >= 50 else None
        df['SMA_200'] = ta.trend.sma_indicator(df['Close'], window=200) if len(df) >= 200 else None
        
        # EMA
        df['EMA_12'] = ta.trend.ema_indicator(df['Close'], window=12)
        df['EMA_26'] = ta.trend.ema_indicator(df['Close'], window=26)
        
        return df
    except Exception as e:
        st.error(f"지표 계산 오류: {str(e)}")
        return df

def create_advanced_chart(df, symbol):
    """고급 인터랙티브 차트 생성"""
    fig = make_subplots(
        rows=5, cols=1,
        shared_xaxes=True,
        vertical_spacing=0.03,
        row_heights=[0.5, 0.15, 0.15, 0.1, 0.1],
        subplot_titles=("", "", "", "", ""),
        specs=[[{"secondary_y": True}],
               [{"secondary_y": False}],
               [{"secondary_y": False}],
               [{"secondary_y": False}],
               [{"secondary_y": False}]]
    )
    
    # 색상 테마
    colors_theme = {
        'bg': '#0f0c29',
        'grid': 'rgba(255,255,255,0.1)',
        'text': 'rgba(255,255,255,0.9)',
        'up': '#00ff88',
        'down': '#ff3366',
        'ma20': '#ffa500',
        'ma50': '#00bfff',
        'ma200': '#ff1493',
        'bb': 'rgba(255,255,255,0.2)'
    }
    
    # 1. 메인 가격 차트 (캔들스틱 + 볼린저 밴드 + 이동평균)
    fig.add_trace(
        go.Candlestick(
            x=df.index,
            open=df['Open'],
            high=df['High'],
            low=df['Low'],
            close=df['Close'],
            name='가격',
            increasing_line_color=colors_theme['up'],
            decreasing_line_color=colors_theme['down'],
            increasing_fillcolor=colors_theme['up'],
            decreasing_fillcolor=colors_theme['down']
        ),
        row=1, col=1, secondary_y=False
    )
    
    # 볼린저 밴드
    if 'BB_upper' in df.columns:
        fig.add_trace(
            go.Scatter(
                x=df.index, y=df['BB_upper'],
                name='BB Upper',
                line=dict(color=colors_theme['bb'], width=1, dash='dash'),
                showlegend=False
            ),
            row=1, col=1
        )
        
        fig.add_trace(
            go.Scatter(
                x=df.index, y=df['BB_lower'],
                name='BB Lower',
                line=dict(color=colors_theme['bb'], width=1, dash='dash'),
                fill='tonexty',
                fillcolor='rgba(255,255,255,0.05)',
                showlegend=False
            ),
            row=1, col=1
        )
    
    # 이동평균선
    if 'SMA_20' in df.columns:
        fig.add_trace(
            go.Scatter(
                x=df.index, y=df['SMA_20'],
                name='MA20',
                line=dict(color=colors_theme['ma20'], width=2)
            ),
            row=1, col=1
        )
    
    if 'SMA_50' in df.columns and df['SMA_50'].notna().any():
        fig.add_trace(
            go.Scatter(
                x=df.index, y=df['SMA_50'],
                name='MA50',
                line=dict(color=colors_theme['ma50'], width=2)
            ),
            row=1, col=1
        )
    
    # 거래량 (보조 y축)
    volume_colors = [colors_theme['up'] if df['Close'].iloc[i] >= df['Open'].iloc[i] 
                     else colors_theme['down'] for i in range(len(df))]
    
    fig.add_trace(
        go.Bar(
            x=df.index, y=df['Volume'],
            name='거래량',
            marker_color=volume_colors,
            opacity=0.3,
            yaxis='y2'
        ),
        row=1, col=1, secondary_y=True
    )
    
    # 2. RSI
    if 'RSI' in df.columns:
        fig.add_trace(
            go.Scatter(
                x=df.index, y=df['RSI'],
                name='RSI',
                line=dict(color='#ff9800', width=2)
            ),
            row=2, col=1
        )
        
        # RSI 레벨
        fig.add_hline(y=70, line_width=1, line_dash="dash", line_color="rgba(255,255,255,0.3)", row=2, col=1)
        fig.add_hline(y=30, line_width=1, line_dash="dash", line_color="rgba(255,255,255,0.3)", row=2, col=1)
        
        # RSI 영역 채우기
        fig.add_hrect(y0=70, y1=100, fillcolor="rgba(255,51,102,0.1)", line_width=0, row=2, col=1)
        fig.add_hrect(y0=0, y1=30, fillcolor="rgba(0,255,136,0.1)", line_width=0, row=2, col=1)
    
    # 3. MACD
    if 'MACD' in df.columns and not df['MACD'].isna().all():
        fig.add_trace(
            go.Scatter(
                x=df.index, y=df['MACD'],
                name='MACD',
                line=dict(color='#00bfff', width=2)
            ),
            row=3, col=1
        )
        
        if 'MACD_signal' in df.columns:
            fig.add_trace(
                go.Scatter(
                    x=df.index, y=df['MACD_signal'],
                    name='Signal',
                    line=dict(color='#ff6347', width=2)
                ),
                row=3, col=1
            )
        
        if 'MACD_diff' in df.columns:
            colors_diff = [colors_theme['up'] if val >= 0 else colors_theme['down'] 
                          for val in df['MACD_diff']]
            fig.add_trace(
                go.Bar(
                    x=df.index, y=df['MACD_diff'],
                    name='MACD Histogram',
                    marker_color=colors_diff,
                    opacity=0.5
                ),
                row=3, col=1
            )
    
    # 4. Stochastic
    if 'Stoch_K' in df.columns:
        fig.add_trace(
            go.Scatter(
                x=df.index, y=df['Stoch_K'],
                name='%K',
                line=dict(color='#9c27b0', width=2)
            ),
            row=4, col=1
        )
        
        if 'Stoch_D' in df.columns:
            fig.add_trace(
                go.Scatter(
                    x=df.index, y=df['Stoch_D'],
                    name='%D',
                    line=dict(color='#e91e63', width=2)
                ),
                row=4, col=1
            )
        
        fig.add_hline(y=80, line_width=1, line_dash="dash", line_color="rgba(255,255,255,0.3)", row=4, col=1)
        fig.add_hline(y=20, line_width=1, line_dash="dash", line_color="rgba(255,255,255,0.3)", row=4, col=1)
    
    # 5. MFI
    if 'MFI' in df.columns:
        fig.add_trace(
            go.Scatter(
                x=df.index, y=df['MFI'],
                name='MFI',
                line=dict(color='#4caf50', width=2),
                fill='tozeroy',
                fillcolor='rgba(76,175,80,0.1)'
            ),
            row=5, col=1
        )
        
        fig.add_hline(y=80, line_width=1, line_dash="dash", line_color="rgba(255,255,255,0.3)", row=5, col=1)
        fig.add_hline(y=20, line_width=1, line_dash="dash", line_color="rgba(255,255,255,0.3)", row=5, col=1)
    
    # 레이아웃 업데이트
    fig.update_layout(
        title={
            'text': f'<b>{symbol}</b> Technical Analysis Dashboard',
            'font': {'size': 24, 'color': 'white'},
            'x': 0.5,
            'xanchor': 'center'
        },
        height=1000,
        plot_bgcolor=colors_theme['bg'],
        paper_bgcolor=colors_theme['bg'],
        font=dict(color=colors_theme['text']),
        showlegend=True,
        legend=dict(
            bgcolor='rgba(255,255,255,0.05)',
            bordercolor='rgba(255,255,255,0.2)',
            borderwidth=1,
            font=dict(color='white'),
            yanchor="top",
            y=0.99,
            xanchor="left",
            x=0.01
        ),
        hovermode='x unified',
        margin=dict(t=100, b=50, l=50, r=50)
    )
    
    # X축 설정
    fig.update_xaxes(
        showgrid=True,
        gridwidth=1,
        gridcolor=colors_theme['grid'],
        showline=True,
        linewidth=1,
        linecolor=colors_theme['grid'],
        rangeslider_visible=False
    )
    
    # Y축 설정
    fig.update_yaxes(
        showgrid=True,
        gridwidth=1,
        gridcolor=colors_theme['grid'],
        showline=True,
        linewidth=1,
        linecolor=colors_theme['grid']
    )
    
    # 주 차트 y축 라벨
    fig.update_yaxes(title_text="가격", row=1, col=1, secondary_y=False)
    fig.update_yaxes(title_text="거래량", row=1, col=1, secondary_y=True)
    fig.update_yaxes(title_text="RSI", row=2, col=1)
    fig.update_yaxes(title_text="MACD", row=3, col=1)
    fig.update_yaxes(title_
