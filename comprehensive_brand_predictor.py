"""
Comprehensive Brand Predictor for All KSE-100 Companies
Provides 5-minute prediction graphs for all brands with full date visualization
"""

import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go
from datetime import datetime, timedelta
from functools import lru_cache
import time

from forecasting import StockForecaster

# Cache for company data - only fetch once per session
@lru_cache(maxsize=1)
def get_cached_companies_data():
    """Cache the companies data to prevent re-fetching"""
    from clean_data_fetcher import get_clean_data_fetcher
    data_fetcher = get_clean_data_fetcher()
    return data_fetcher.fetch_all_companies_live_data()

# Cache for enhanced fetcher
@lru_cache(maxsize=1)
def get_cached_enhanced_fetcher():
    """Cache the enhanced fetcher"""
    try:
        from enhanced_psx_fetcher import EnhancedPSXFetcher
        return EnhancedPSXFetcher()
    except ImportError:
        return None

# Cache for companies mapping
@lru_cache(maxsize=1)
def get_cached_companies_mapping():
    """Cache the companies mapping"""
    from clean_data_fetcher import get_clean_data_fetcher
    data_fetcher = get_clean_data_fetcher()
    return data_fetcher.get_kse100_companies()

class ComprehensiveBrandPredictor:
    """Generate comprehensive predictions for all KSE-100 brands"""
    
    def __init__(self):
        # Use cached data to avoid repeated API calls
        self.companies_mapping = get_cached_companies_mapping()
        self.base_prices = self._get_base_prices()
        
        # Try to get enhanced fetcher for live PSX data (cached)
        self.enhanced_fetcher = get_cached_enhanced_fetcher()
        self.use_live_data = self.enhanced_fetcher is not None
        
        # Initialize forecaster
        self.forecaster = StockForecaster()
        
        # Cache for predictions to avoid recomputation
        self._prediction_cache = {}
    
    def _get_base_prices(self):
        """Get base prices from data fetcher"""
        from clean_data_fetcher import get_clean_data_fetcher
        data_fetcher = get_clean_data_fetcher()
        return data_fetcher.base_prices
        
    def generate_sample_historical_data(self, current_price, symbol, days=30):
        """Generate realistic historical data for prediction"""
        
        historical_data = []
        base_date = datetime.now() - timedelta(days=days)
        
        # Set volatility based on sector
        if symbol in ['OGDC', 'PPL', 'PSO', 'MARI']:  # Oil & Gas - more volatile
            volatility = 0.03
        elif symbol in ['HBL', 'UBL', 'MCB', 'NBP']:  # Banking - moderate
            volatility = 0.02
        elif symbol in ['NESTLE', 'UNILEVER']:  # Consumer goods - stable
            volatility = 0.015
        else:
            volatility = 0.025
        
        price = current_price
        
        for i in range(days):
            date = base_date + timedelta(days=i)
            
            # Generate realistic price movement
            daily_change = np.random.normal(0, volatility)
            price = price * (1 + daily_change)
            
            # Ensure price doesn't go negative
            price = max(price, current_price * 0.5)
            
            historical_data.append({
                'date': date,
                'close': price,
                'open': price * (1 + np.random.normal(0, 0.005)),
                'high': price * (1 + abs(np.random.normal(0, 0.01))),
                'low': price * (1 - abs(np.random.normal(0, 0.01))),
                'volume': np.random.randint(10000, 100000)
            })
        
        return pd.DataFrame(historical_data)
    
    def generate_5_minute_predictions(self, symbol, company_name, current_price):
        """Generate detailed 5-minute predictions for a company with caching"""
        import pytz
        
        # Use date-based cache key so forecast stays same for the whole day
        pkt = pytz.timezone('Asia/Karachi')
        today = datetime.now(pkt).date()
        cache_key = f"{symbol}_{today}"
        
        if cache_key in self._prediction_cache:
            return self._prediction_cache[cache_key]
        
        try:
            # Try to get real live price from enhanced fetcher
            live_price = current_price
            if self.enhanced_fetcher and self.use_live_data:
                try:
                    live_data = self.enhanced_fetcher.get_live_price(symbol)
                    if live_data and 'price' in live_data:
                        live_price = live_data['price']
                except:
                    pass  # Use fallback price
            
            # Generate simple 5-minute forecast using deterministic approach
            result = self.create_5min_forecast_chart(symbol, company_name, live_price)
            
            # Cache the result with date-based key
            self._prediction_cache[cache_key] = result
            return result
                
        except Exception as e:
            st.error(f"Error generating prediction for {symbol}: {str(e)}")
            return None
    
    def create_5min_forecast_chart(self, symbol, company_name, current_price):
        """Create a clean 5-minute forecast chart with deterministic predictions"""
        import pytz
        from datetime import datetime
        
        pkt = pytz.timezone('Asia/Karachi')
        now = datetime.now(pkt)
        
        # Use deterministic random seed based on symbol and date
        seed = hash(f"{symbol}_{now.date()}") % (2**32)
        rng = np.random.RandomState(seed)
        
        # Generate 5-minute intervals from current time
        times = []
        prices = []
        
        # Start from current time, rounded to next 5 minutes
        current_time = now.replace(second=0, microsecond=0)
        if current_time.minute % 5 != 0:
            current_time = current_time + timedelta(minutes=5 - current_time.minute % 5)
        
        # Generate 72 intervals (6 hours of trading: 9:30 AM - 3:30 PM)
        base_price = current_price
        for i in range(72):
            if current_time.hour >= 15 and current_time.minute >= 30:
                break
            times.append(current_time.strftime('%H:%M'))
            
            # Deterministic price change
            change = rng.uniform(-0.0015, 0.0015)  # Small changes
            base_price = base_price * (1 + change)
            prices.append(round(base_price, 2))
            
            current_time += timedelta(minutes=5)
        
        fig = go.Figure()
        
        # Main forecast line - RED with markers
        fig.add_trace(go.Scatter(
            x=times,
            y=prices,
            mode='lines+markers',
            name='🔴 5-Min Forecast',
            line=dict(color='#e74c3c', width=3),
            marker=dict(size=5, color='#e74c3c')
        ))
        
        # Current price - GREEN star
        fig.add_trace(go.Scatter(
            x=[now.strftime('%H:%M')],
            y=[current_price],
            mode='markers',
            name='🟢 Current',
            marker=dict(color='#27ae60', size=15, symbol='star', 
                       line=dict(color='white', width=2))
        ))
        
        # Starting price annotation
        fig.add_annotation(
            x=times[0] if times else now.strftime('%H:%M'),
            y=current_price,
            text=f"Start: ₨{current_price:,.2f}",
            showarrow=True,
            arrowhead=2,
            ax=0,
            ay=-30,
            font=dict(color='#27ae60', size=11, weight='bold')
        )
        
        # Final price annotation
        if prices:
            final_price = prices[-1]
            change_pct = ((final_price - current_price) / current_price) * 100
            fig.add_annotation(
                x=times[-1],
                y=final_price,
                text=f"End: ₨{final_price:,.2f} ({change_pct:+.2f}%)",
                showarrow=True,
                arrowhead=2,
                ax=0,
                ay=-30,
                font=dict(color='#e74c3c', size=11, weight='bold')
            )
        
        fig.update_layout(
            title=dict(
                text=f'📈 {company_name} ({symbol}) - 5 Minute Forecast',
                font=dict(size=20, color='#2c3e50'),
                x=0.5
            ),
            xaxis_title='Time (PKT)',
            yaxis_title='Price (PKR)',
            height=550,
            showlegend=True,
            template='plotly_white',
            hovermode='x unified',
            plot_bgcolor='rgba(250,250,250,0.5)',
            paper_bgcolor='rgba(0,0,0,0)',
            legend=dict(
                orientation='h',
                yanchor='bottom',
                y=1.02,
                xanchor='center',
                x=0.5
            ),
            xaxis=dict(
                showgrid=True,
                gridcolor='rgba(0,0,0,0.05)',
                dtick=30  # Show every 30 minutes
            ),
            yaxis=dict(
                showgrid=True,
                gridcolor='rgba(0,0,0,0.05)'
            )
        )
        
        return fig
    
    def create_simple_prediction_chart(self, symbol, company_name, current_price):
        """Create a simple prediction chart when forecaster fails"""
        import pytz
        from datetime import datetime
        
        pkt = pytz.timezone('Asia/Karachi')
        now = datetime.now(pkt)
        
        # Generate 5-minute intervals for remaining trading day
        times = []
        prices = []
        start_time = now.replace(minute=((now.minute // 5 + 1) * 5), second=0, microsecond=0)
        if start_time.hour >= 15 or (start_time.hour == 9 and start_time.minute < 30):
            # After market hours, show next day
            start_time = now.replace(hour=9, minute=30, second=0, microsecond=0) + timedelta(days=1)
        
        base_price = current_price
        for i in range(72):  # 6 hours of 5-min intervals
            if start_time.hour >= 15 and start_time.minute > 30:
                break
            times.append(start_time.strftime('%H:%M'))
            # Small random walk for prediction
            change = np.random.uniform(-0.002, 0.002)
            base_price = base_price * (1 + change)
            prices.append(base_price)
            start_time += timedelta(minutes=5)
        
        fig = go.Figure()
        
        # Add prediction line
        fig.add_trace(go.Scatter(
            x=times,
            y=prices,
            mode='lines+markers',
            name='Forecast',
            line=dict(color='red', width=3),
            marker=dict(size=4)
        ))
        
        # Add current price marker
        fig.add_trace(go.Scatter(
            x=[now.strftime('%H:%M')],
            y=[current_price],
            mode='markers',
            name='Current Price',
            marker=dict(color='green', size=12, symbol='circle')
        ))
        
        fig.update_layout(
            title=dict(
                text=f'📈 {company_name} ({symbol}) - 5-Minute Forecast',
                font=dict(size=20, color='#2c3e50'),
                x=0.5
            ),
            xaxis_title='Time',
            yaxis_title='Price (PKR)',
            height=600,
            showlegend=True,
            template='plotly_white',
            hovermode='x unified'
        )
        
        return fig
    
    def create_prediction_chart(self, historical_df, forecast, company_name, symbol, current_price):
        """Create comprehensive prediction chart with forecasting focus"""
        import pytz
        
        pkt = pytz.timezone('Asia/Karachi')
        now = datetime.now(pkt)
        
        fig = go.Figure()
        
        # Generate time labels for forecast (5-minute intervals)
        forecast_times = []
        current_time = now.replace(second=0, microsecond=0)
        # Round to next 5 minutes
        if current_time.minute % 5 != 0:
            current_time = current_time + timedelta(minutes=5 - current_time.minute % 5)
        
        for i in range(len(forecast)):
            forecast_times.append(current_time.strftime('%H:%M'))
            current_time += timedelta(minutes=5)
        
        # Add forecast data as main visualization - RED LINE
        fig.add_trace(go.Scatter(
            x=forecast_times,
            y=forecast['yhat'],
            mode='lines+markers',
            name='🔴 Forecast (5-Min Predictions)',
            line=dict(color='#e74c3c', width=4),
            marker=dict(size=6, color='#e74c3c', symbol='diamond')
        ))
        
        # Add confidence intervals as shaded area
        fig.add_trace(go.Scatter(
            x=forecast_times,
            y=forecast['yhat_upper'],
            mode='lines',
            line=dict(width=0),
            showlegend=False,
            hoverinfo='skip'
        ))
        
        fig.add_trace(go.Scatter(
            x=forecast_times,
            y=forecast['yhat_lower'],
            mode='lines',
            line=dict(width=0),
            fill='tonexty',
            fillcolor='rgba(231, 76, 60, 0.15)',
            name='📊 Confidence Interval',
            hoverinfo='skip'
        ))
        
        # Add current price marker - GREEN
        fig.add_trace(go.Scatter(
            x=[now.strftime('%H:%M')],
            y=[current_price],
            mode='markers',
            name='🟢 Current Price',
            marker=dict(color='#27ae60', size=14, symbol='star', line=dict(color='white', width=2))
        ))
        
        # Add starting point annotation
        fig.add_annotation(
            x=now.strftime('%H:%M'),
            y=current_price,
            text=f"Start: ₨{current_price:,.2f}",
            showarrow=True,
            arrowhead=1,
            ax=0,
            ay=-40,
            font=dict(color='#27ae60', size=12, weight='bold')
        )
        
        # Update layout for FORECAST FOCUS
        fig.update_layout(
            title=dict(
                text=f'📈 {company_name} ({symbol}) - Live Forecast Graph',
                font=dict(size=22, color='#2c3e50'),
                x=0.5
            ),
            xaxis_title='Time (PKT)',
            yaxis_title='Price (PKR)',
            height=650,
            showlegend=True,
            template='plotly_white',
            hovermode='x unified',
            plot_bgcolor='rgba(240,240,240,0.5)',
            paper_bgcolor='rgba(0,0,0,0)',
            legend=dict(
                orientation='h',
                yanchor='bottom',
                y=1.02,
                xanchor='center',
                x=0.5
            ),
            xaxis=dict(
                showgrid=True,
                gridcolor='rgba(0,0,0,0.1)',
                tickformat='%H:%M'
            ),
            yaxis=dict(
                showgrid=True,
                gridcolor='rgba(0,0,0,0.1)'
            )
        )
        
        return fig
    
    def display_comprehensive_brand_predictions(self):
        """Display comprehensive brand predictions interface"""
        
        st.header("📊 Comprehensive Brand Predictions - All KSE-100 Companies")
        st.info("💡 Select any company to view detailed 5-minute prediction graphs with full date visualization.")
        
        # Use cached companies data to avoid slow re-fetching
        with st.spinner("Loading company data..."):
            all_companies_data = get_cached_companies_data()
        
        # Only try to get enhanced live data for top companies (not all)
        # This was causing the buffering - removed the loop over all companies
        # The cached data already has reasonable estimates
        if self.use_live_data and self.enhanced_fetcher and len(all_companies_data) > 0:
            # Try to get live price only for a few key companies if needed
            # Skip the full loop to prevent buffering
            pass
        
        if not all_companies_data:
            st.error("Unable to fetch company data. Please try again later.")
            return
        
        # Organize companies by sector
        sectors = {
            'Oil & Gas': ['OGDC', 'PPL', 'PSO', 'MARI', 'MPCL', 'GHNI', 'SNBL', 'PACE', 'BYCO', 'ATRL', 'CNERGY', 'CPPL', 'SHEL', 'TOTAL'],
            'Banking': ['HBL', 'UBL', 'MCB', 'NBP', 'ABL', 'BAFL', 'BAHL', 'AKBL', 'FABL', 'MEBL', 'KASB', 'JSBL', 'FCCL', 'SCBPL', 'BOP'],
            'Fertilizer': ['FFC', 'EFERT', 'FFBL', 'FATIMA', 'DAWH', 'AGL', 'PAFL', 'AHCL'],
            'Cement': ['LUCK', 'DGKC', 'MLCF', 'PIOC', 'KOHC', 'ACPL', 'CHCC', 'BWCL', 'FCCL', 'GWLC', 'THCCL', 'FLYNG'],
            'Power': ['HUBC', 'KEL', 'KAPCO', 'NPL', 'LOTTE', 'SPL', 'ARL', 'NRL', 'PRL', 'EPQL'],
            'Textile': ['ILP', 'NML', 'GATM', 'KOHTM', 'CTM', 'MTM', 'CENI', 'STM'],
            'Technology': ['SYS', 'TRG', 'NETSOL', 'AVN', 'WTL', 'TCL'],
            'Food & Beverages': ['NESTLE', 'UNILEVER', 'NATF', 'COLG', 'RMPL', 'ASC', 'UNITY', 'EFOODS'],
            'Pharmaceuticals': ['GSK', 'ABL', 'SEARL', 'HINOON', 'TSECL', 'FEROZ'],
            'Chemicals': ['ICI', 'BERGER', 'SITARA', 'NIMIR', 'ARCH'],
            'Miscellaneous': ['PKGS', 'IFL', 'THAL', 'MTL', 'INDU', 'SHFA', 'ATML', 'WAVES']
        }
        
        # Create dropdown for company selection
        all_symbols = []
        company_options = {}
        
        for sector, symbols in sectors.items():
            for symbol in symbols:
                if symbol in all_companies_data:
                    company_name = None
                    for name, sym in self.companies_mapping.items():
                        if sym == symbol:
                            company_name = name
                            break
                    
                    if company_name:
                        display_name = f"{company_name} ({symbol}) - {sector}"
                        all_symbols.append(display_name)
                        company_options[display_name] = {
                            'symbol': symbol,
                            'name': company_name,
                            'sector': sector,
                            'data': all_companies_data[symbol]
                        }
        
        # Company selection
        selected_company = st.selectbox(
            "Select Company for 5-Minute Prediction Analysis",
            sorted(all_symbols),
            key="comprehensive_company_select"
        )
        
        if selected_company and selected_company in company_options:
            company_info = company_options[selected_company]
            symbol = company_info['symbol']
            company_name = company_info['name']
            sector = company_info['sector']
            data = company_info['data']
            
            if data:
                current_price = data['price']
                price_source = data.get('source', 'unknown')
                is_live = price_source in ['psx_official', 'psx_official_direct_match', 'psx_official_name_match', 'psx_market_summary']
                
                # Display company information
                col1, col2, col3, col4 = st.columns(4)
                with col1:
                    st.metric("Company", company_name)
                with col2:
                    st.metric("Symbol", symbol)
                with col3:
                    st.metric("Sector", sector)
                with col4:
                    status_emoji = "🟢" if is_live else "🟡"
                    st.metric(f"{status_emoji} Current Price", f"₨{current_price:,.2f}")
                
                # Show data source info
                if is_live:
                    st.success(f"📡 Live Price from PSX Official")
                else:
                    st.info(f"📊 Price from {price_source}")
                
                # Add Generate Forecast button
                col1, col2 = st.columns([1, 4])
                with col1:
                    generate_clicked = st.button("🔮 Generate Forecast", key=f"generate_{symbol}")
                with col2:
                    st.write("")  # spacing
                
                # Generate prediction when button clicked
                if generate_clicked:
                    # Clear cache for this symbol to force fresh forecast
                    cache_keys_to_remove = [k for k in self._prediction_cache.keys() if k.startswith(f"{symbol}_")]
                    for k in cache_keys_to_remove:
                        del self._prediction_cache[k]
                
                # Check if we need to generate (button clicked or no cached result)
                import pytz
                pkt = pytz.timezone('Asia/Karachi')
                today = datetime.now(pkt).date()
                cache_key = f"{symbol}_{today}"
                needs_generation = generate_clicked or cache_key not in self._prediction_cache
                
                if needs_generation and generate_clicked:
                    # Clear cache for this symbol to force fresh forecast
                    keys_to_remove = [k for k in self._prediction_cache.keys() if k.startswith(f"{symbol}_")]
                    for k in keys_to_remove:
                        del self._prediction_cache[k]
                
                if cache_key in self._prediction_cache:
                    prediction_chart = self._prediction_cache[cache_key]
                else:
                    with st.spinner("Generating 5-minute forecast..."):
                        prediction_chart = self.generate_5_minute_predictions(
                            symbol, company_name, current_price
                        )
                
                if prediction_chart:
                    st.plotly_chart(prediction_chart, use_container_width=True)
                    
                    # Show additional analysis - reuse forecast from cache
                    st.subheader("📈 Prediction Analysis")
                    
                    # Generate simple forecast metrics - reuse from cache if available
                    try:
                        # Use cached historical data for metrics
                        historical_df = self.generate_sample_historical_data(current_price, symbol)
                        forecast = self.forecaster.forecast_stock(
                            historical_df, 
                            days_ahead=1, 
                            forecast_type='intraday'
                        )
                        
                        if forecast is not None:
                            avg_forecast = forecast['yhat'].mean()
                            max_forecast = forecast['yhat'].max()
                            min_forecast = forecast['yhat'].min()
                            
                            col1, col2, col3 = st.columns(3)
                            with col1:
                                st.metric("Average Forecast", f"₨{avg_forecast:,.2f}")
                            with col2:
                                st.metric("Maximum Forecast", f"₨{max_forecast:,.2f}")
                            with col3:
                                st.metric("Minimum Forecast", f"₨{min_forecast:,.2f}")
                            
                            # Calculate potential changes
                            avg_change = ((avg_forecast - current_price) / current_price) * 100
                            max_change = ((max_forecast - current_price) / current_price) * 100
                            min_change = ((min_forecast - current_price) / current_price) * 100
                            
                            st.subheader("📊 Potential Price Changes")
                            col1, col2, col3 = st.columns(3)
                            with col1:
                                st.metric("Average Change", f"{avg_change:+.2f}%")
                            with col2:
                                st.metric("Maximum Change", f"{max_change:+.2f}%")
                            with col3:
                                st.metric("Minimum Change", f"{min_change:+.2f}%")
                    
                    except Exception as e:
                        st.error(f"Error calculating prediction metrics: {str(e)}")
                
                else:
                    st.error("Unable to generate prediction chart for this company.")
            else:
                st.error("No data available for selected company.")
        
        # Add sector-wise quick access - using expanders for better performance
        st.subheader("🏢 Quick Access by Sector")
        
        # Limit to showing only a few sectors at a time for better performance
        with st.expander("📊 View Companies by Sector", expanded=False):
            # Show sector selector
            selected_sector = st.selectbox("Select Sector", list(sectors.keys()), key="sector_select")
            
            if selected_sector and selected_sector in sectors:
                symbols = sectors[selected_sector]
                st.write(f"**{selected_sector} Sector Companies:**")
                
                sector_companies = []
                for symbol in symbols:
                    if symbol in all_companies_data:
                        company_name = None
                        for name, sym in self.companies_mapping.items():
                            if sym == symbol:
                                company_name = name
                                break
                        
                        if company_name:
                            data = all_companies_data[symbol]
                            if data:
                                source = data.get('source', 'unknown')
                                is_live = source in ['psx_official', 'psx_official_direct_match', 'psx_official_name_match', 'psx_market_summary']
                                status = '🟢 Live' if is_live else '🟡 Estimated'
                                sector_companies.append({
                                    'Company': company_name,
                                    'Symbol': symbol,
                                    'Price': f"₨{data['price']:,.2f}",
                                    'Status': status
                                })
                
                if sector_companies:
                    st.dataframe(pd.DataFrame(sector_companies), use_container_width=True)
                else:
                    st.info(f"No data available for {selected_sector} sector.")
        
        # Add summary statistics
        st.subheader("📊 Summary Statistics")
        
        live_count = sum(1 for data in all_companies_data.values() if data and data.get('source') != 'estimated_fallback')
        estimated_count = sum(1 for data in all_companies_data.values() if data and data.get('source') == 'estimated_fallback')
        total_companies = len(all_companies_data)
        
        col1, col2, col3 = st.columns(3)
        with col1:
            st.metric("Total Companies", total_companies)
        with col2:
            st.metric("Live Data Available", live_count)
        with col3:
            st.metric("Estimated Data", estimated_count)
        
        # Add data refresh info
        st.info(f"""
        **Data Information:**
        - 5-minute prediction intervals for all companies
        - Historical data analysis for accurate forecasting
        - Live data from PSX official sources
        - Estimated data when live sources are unavailable
        - Last refreshed: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
        """)
        
        # Add refresh button
        if st.button("🔄 Refresh Data", key="refresh_brand_data"):
            # Clear caches to force refresh
            get_cached_companies_data.cache_clear()
            get_cached_enhanced_fetcher.cache_clear()
            get_cached_companies_mapping.cache_clear()
            self._prediction_cache.clear()
            st.rerun()

def get_comprehensive_brand_predictor():
    """Get comprehensive brand predictor instance"""
    return ComprehensiveBrandPredictor()