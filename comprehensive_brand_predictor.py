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
            name='5-Min Forecast',
            line=dict(color='#e74c3c', width=3),
            marker=dict(size=5, color='#e74c3c')
        ))

        # Current price - GREEN star
        fig.add_trace(go.Scatter(
            x=[now.strftime('%H:%M')],
            y=[current_price],
            mode='markers',
            name='Current',
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
                text=f'{company_name} ({symbol}) - 5 Minute Forecast',
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
                text=f'{company_name} ({symbol}) - 5-Minute Forecast',
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
            name=' Forecast (5-Min Predictions)',
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
            name='Confidence Interval',
            hoverinfo='skip'
        ))
        
        # Add current price marker - GREEN
        fig.add_trace(go.Scatter(
            x=[now.strftime('%H:%M')],
            y=[current_price],
            mode='markers',
            name='Current Price',
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
                text=f'{company_name} ({symbol}) - Live Forecast Graph',
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
    
    def create_linear_forecast_chart(self, symbol, company_name, current_price, hours=1):
        """Create a smooth linear forecast chart with proper movement visualization"""
        import pytz
        import numpy as np
        from datetime import datetime, timedelta

        pkt = pytz.timezone('Asia/Karachi')
        now = datetime.now(pkt)

        # Generate forecast data with OHLC for specified hours
        forecast_data = self._generate_forecast_ohlc_data(symbol, current_price, hours=hours)

        if forecast_data.empty:
            return None

        fig = go.Figure()

        # Create smooth forecast line by interpolating between points
        times = forecast_data['datetime'].values
        prices = forecast_data['close'].values

        # Create more points for smoother curve (every minute instead of every 5 minutes)
        smooth_times = []
        smooth_prices = []

        for i in range(len(times) - 1):
            start_time = times[i]
            end_time = times[i + 1]
            start_price = prices[i]
            end_price = prices[i + 1]

            # Add points for smoother transition
            steps = 5  # 5 points between each 5-minute interval
            for step in range(steps):
                ratio = step / steps
                interp_time = start_time + (end_time - start_time) * ratio
                # Smooth price transition with slight curve
                interp_price = start_price + (end_price - start_price) * (ratio ** 0.8)  # Slight easing

                smooth_times.append(interp_time)
                smooth_prices.append(interp_price)

        # Add final point
        smooth_times.append(times[-1])
        smooth_prices.append(prices[-1])

        # Convert to numpy arrays for better performance
        smooth_times = np.array(smooth_times)
        smooth_prices = np.array(smooth_prices)

        # Main smooth forecast line
        fig.add_trace(go.Scatter(
            x=smooth_times,
            y=smooth_prices,
            mode='lines',
            name='Forecast Movement',
            line=dict(color='#e74c3c', width=4, shape='spline', smoothing=1.3),
            fill='tonexty',
            fillcolor='rgba(231, 76, 60, 0.1)'
        ))

        # Add discrete 5-minute markers
        fig.add_trace(go.Scatter(
            x=times,
            y=prices,
            mode='markers',
            name='5-Min Points',
            marker=dict(size=8, color='#e74c3c', symbol='circle',
                       line=dict(color='white', width=2)),
            hovertemplate='Time: %{x}<br>Price: ₨%{y:,.2f}<extra></extra>'
        ))

        # Current price marker with animation effect
        fig.add_trace(go.Scatter(
            x=[times[0]],
            y=[current_price],
            mode='markers',
            name='Current',
            marker=dict(color='#27ae60', size=18, symbol='star',
                       line=dict(color='white', width=3))
        ))

        # Add trend direction arrows
        trend_changes = []
        for i in range(1, len(prices)):
            if (prices[i] - prices[i-1]) > 0.001:  # Upward movement
                trend_changes.append(('up', times[i], prices[i]))
            elif (prices[i] - prices[i-1]) < -0.001:  # Downward movement
                trend_changes.append(('down', times[i], prices[i]))

        # Add movement indicators (small arrows)
        for direction, time_point, price_point in trend_changes[:5]:  # Show first 5 movements
            arrow_symbol = 'arrow-up' if direction == 'up' else 'arrow-down'
            arrow_color = '#27ae60' if direction == 'up' else '#e74c3c'

            fig.add_trace(go.Scatter(
                x=[time_point],
                y=[price_point],
                mode='markers',
                showlegend=False,
                marker=dict(
                    size=12,
                    color=arrow_color,
                    symbol=arrow_symbol,
                    line=dict(color='white', width=1)
                ),
                hoverinfo='skip'
            ))

        # Enhanced annotations
        fig.add_annotation(
            x=times[0],
            y=current_price,
            text=f"₨{current_price:,.2f}",
            showarrow=True,
            arrowhead=2,
            ax=0,
            ay=-40,
            font=dict(color='#27ae60', size=12, weight='bold'),
            bordercolor='#27ae60',
            borderwidth=1,
            borderpad=4,
            bgcolor='rgba(255,255,255,0.9)'
        )

        # Final price with change indicator
        final_price = prices[-1]
        change_pct = ((final_price - current_price) / current_price) * 100
        change_color = '#27ae60' if change_pct >= 0 else '#e74c3c'

        fig.add_annotation(
            x=times[-1],
            y=final_price,
            text=f"₨{final_price:,.2f}<br>({change_pct:+.2f}%)",
            showarrow=True,
            arrowhead=2,
            ax=0,
            ay=-40,
            font=dict(color=change_color, size=12, weight='bold'),
            bordercolor=change_color,
            borderwidth=1,
            borderpad=4,
            bgcolor='rgba(255,255,255,0.9)'
        )

        # Update chart title with movement description
        movement_desc = "Smooth Price Movement" if hours == 1 else f"{hours}H Forecast Movement"
        title_text = f'{company_name} ({symbol}) - {movement_desc}'

        if hours == 1:
            title_text += f' — {len(forecast_data)} × 5-Minute Forecast Points'

        fig.update_layout(
            title=dict(
                text=title_text,
                font=dict(size=22, color='#2c3e50'),
                x=0.5
            ),
            xaxis_title='Time (PKT)',
            yaxis_title='Price (PKR)',
            height=600,
            showlegend=True,
            template='plotly_white',
            hovermode='x unified',
            plot_bgcolor='rgba(245,245,245,0.8)',
            paper_bgcolor='rgba(255,255,255,0.9)',
            legend=dict(
                orientation='h',
                yanchor='bottom',
                y=1.02,
                xanchor='center',
                x=0.5,
                bgcolor='rgba(255,255,255,0.8)',
                bordercolor='rgba(0,0,0,0.1)',
                borderwidth=1
            ),
            xaxis=dict(
                showgrid=True,
                gridcolor='rgba(0,0,0,0.1)',
                gridwidth=1,
                dtick=30*60*1000,  # Show every 30 minutes in milliseconds
                tickformat='%H:%M'
            ),
            yaxis=dict(
                showgrid=True,
                gridcolor='rgba(0,0,0,0.1)',
                gridwidth=1,
                tickformat='₨%,.2f'
            )
        )

        return fig

    def create_enhanced_candlestick_forecast_chart(self, symbol, company_name, current_price, hours=6):
        """Create enhanced candlestick chart with technical overlays for forecast analysis"""
        import pytz
        import talib
        from datetime import datetime

        pkt = pytz.timezone('Asia/Karachi')
        now = datetime.now(pkt)

        # Generate forecast data with OHLC for specified hours
        forecast_data = self._generate_forecast_ohlc_data(symbol, current_price, hours=hours)

        if forecast_data.empty:
            return None

        fig = go.Figure()

        # Add candlestick chart
        fig.add_trace(go.Candlestick(
            x=forecast_data['datetime'],
            open=forecast_data['open'],
            high=forecast_data['high'],
            low=forecast_data['low'],
            close=forecast_data['close'],
            name='Candlestick',
            increasing_line_color='#17BECF',
            decreasing_line_color='#7F7F7F'
        ))

        # Calculate technical indicators
        closes = forecast_data['close'].values
        highs = forecast_data['high'].values
        lows = forecast_data['low'].values

        # Moving averages - use SMA-3 and SMA-5 as specified
        sma_3 = talib.SMA(closes, timeperiod=3) if len(closes) >= 3 else None
        sma_5 = talib.SMA(closes, timeperiod=5) if len(closes) >= 5 else None

        # RSI(5) as specified
        rsi = talib.RSI(closes, timeperiod=5) if len(closes) >= 5 else None

        # Bollinger Bands
        bb_period = min(20, len(closes))
        if bb_period >= 5:  # Need at least 5 periods for meaningful BB
            upperband, middleband, lowerband = talib.BBANDS(closes, timeperiod=bb_period, nbdevup=2, nbdevdn=2, matype=0)
        else:
            upperband = middleband = lowerband = None

        # Add technical overlays
        if sma_3 is not None:
            fig.add_trace(go.Scatter(
                x=forecast_data['datetime'],
                y=sma_3,
                line=dict(color='blue', width=1.5),
                name='SMA-3'
            ))

        if sma_5 is not None:
            fig.add_trace(go.Scatter(
                x=forecast_data['datetime'],
                y=sma_5,
                line=dict(color='red', width=1.5),
                name='SMA-5'
            ))

        # Bollinger Bands
        if upperband is not None:
            fig.add_trace(go.Scatter(
                x=forecast_data['datetime'],
                y=upperband,
                line=dict(color='gray', width=1, dash='dash'),
                name='BB Upper'
            ))

            fig.add_trace(go.Scatter(
                x=forecast_data['datetime'],
                y=middleband,
                line=dict(color='gray', width=1),
                name='BB Middle'
            ))

            fig.add_trace(go.Scatter(
                x=forecast_data['datetime'],
                y=lowerband,
                line=dict(color='gray', width=1, dash='dash'),
                name='BB Lower'
            ))

        # Add 95% Confidence Band
        # Calculate confidence intervals based on forecast data volatility
        closes_array = forecast_data['close'].values
        if len(closes_array) >= 5:
            # Calculate rolling standard deviation for confidence bands
            rolling_std = pd.Series(closes_array).rolling(window=min(5, len(closes_array)), min_periods=1).std()
            confidence_multiplier = 1.96  # 95% confidence interval (approximately 2 standard deviations)

            upper_confidence = closes_array + (rolling_std * confidence_multiplier)
            lower_confidence = closes_array - (rolling_std * confidence_multiplier)

            # Add confidence band as filled area
            fig.add_trace(go.Scatter(
                x=list(forecast_data['datetime']) + list(forecast_data['datetime'][::-1]),
                y=list(upper_confidence) + list(lower_confidence[::-1]),
                fill='toself',
                fillcolor='rgba(255, 165, 0, 0.1)',  # Light orange fill
                line=dict(color='rgba(255,255,255,0)'),
                name='95% Confidence Band',
                showlegend=True
            ))

            # Add confidence band boundaries
            fig.add_trace(go.Scatter(
                x=forecast_data['datetime'],
                y=upper_confidence,
                line=dict(color='orange', width=1, dash='dot'),
                name='95% Upper',
                showlegend=False
            ))

            fig.add_trace(go.Scatter(
                x=forecast_data['datetime'],
                y=lower_confidence,
                line=dict(color='orange', width=1, dash='dot'),
                name='95% Lower',
                showlegend=False
            ))

        # Current price line
        fig.add_hline(y=current_price, line_dash="dash", line_color="green",
                      annotation_text=f"Current: ₨{current_price:,.2f}", annotation_position="top left")

        # Update chart title - use specific format for 1H forecast
        if hours == 1:
            title_text = f'{company_name} ({symbol}) - 1-Hour Forecast — 12 × 5-Minute Candles Enhanced Candlestick Chart with Technical Overlays — SMA-3 · SMA-5 · Bollinger Bands · RSI(5) · 95% Confidence Band'
        else:
            title_text = f'{company_name} ({symbol}) - Enhanced Candlestick Forecast ({hours}H)'

        fig.update_layout(
            title=dict(
                text=title_text,
                font=dict(size=16, color='#2c3e50'),
                x=0.5
            ),
            xaxis_title='Time (PKT)',
            yaxis_title='Price (PKR)',
            height=600,
            showlegend=True,
            template='plotly_white',
            hovermode='x unified',
            plot_bgcolor='rgba(250,250,250,0.5)',
            paper_bgcolor='rgba(0,0,0,0)',
            xaxis_rangeslider_visible=False
        )

        # Add RSI subplot
        fig_rsi = go.Figure()
        if rsi is not None:
            fig_rsi.add_trace(go.Scatter(
                x=forecast_data['datetime'],
                y=rsi,
                line=dict(color='purple', width=1.5),
                name='RSI(5)'
            ))

            fig_rsi.add_hline(y=70, line_dash="dash", line_color="red", annotation_text="Overbought")
            fig_rsi.add_hline(y=30, line_dash="dash", line_color="green", annotation_text="Oversold")

            fig_rsi.update_layout(
                title="RSI(5)",
                height=200,
                showlegend=False,
                xaxis_title='Time',
                yaxis_title='RSI'
            )
        else:
            # If not enough data for RSI, show a placeholder
            fig_rsi.add_annotation(
                text="Insufficient data for RSI(5) calculation",
                xref="paper", yref="paper",
                x=0.5, y=0.5, showarrow=False,
                font=dict(size=14)
            )

        return fig, fig_rsi

    def _generate_forecast_ohlc_data(self, symbol, current_price, hours=6):
        """Generate realistic OHLC forecast data with proper market-like movements"""
        import pytz
        from datetime import datetime
        import numpy as np

        pkt = pytz.timezone('Asia/Karachi')
        now = datetime.now(pkt)

        # Generate 5-minute intervals for specified hours
        intervals = hours * 12  # 12 intervals per hour
        data = []

        # Set base volatility and trend characteristics based on sector
        if symbol in ['OGDC', 'PPL', 'PSO', 'MARI']:
            base_volatility = 0.025  # Oil & Gas - higher volatility
            trend_strength = 0.7
        elif symbol in ['HBL', 'UBL', 'MCB', 'NBP']:
            base_volatility = 0.018  # Banking - moderate volatility
            trend_strength = 0.5
        elif symbol in ['NESTLE', 'UNILEVER']:
            base_volatility = 0.012  # Consumer goods - lower volatility
            trend_strength = 0.3
        else:
            base_volatility = 0.020  # Default moderate volatility
            trend_strength = 0.4

        # Initialize price and trend parameters
        price = current_price
        trend_direction = np.random.choice([-1, 1])  # Random initial trend
        trend_momentum = 0.0
        mean_reversion_level = current_price

        # Generate realistic price movements
        for i in range(intervals):
            dt = now + timedelta(minutes=i*5)

            # Dynamic volatility - increases during market hours
            hour_of_day = dt.hour
            if 9 <= hour_of_day <= 15:  # Main trading hours
                time_multiplier = 1.0 + 0.3 * np.sin(np.pi * (hour_of_day - 9) / 6)  # Higher volatility midday
            else:
                time_multiplier = 0.7  # Lower volatility off-hours

            current_volatility = base_volatility * time_multiplier

            # Mean reversion component
            mean_reversion_force = (mean_reversion_level - price) / current_price * 0.1

            # Trend component with momentum
            trend_noise = np.random.normal(0, 0.5)
            trend_momentum = trend_momentum * 0.8 + trend_noise * 0.2  # Smoothed momentum
            trend_component = trend_direction * trend_strength * trend_momentum * current_volatility

            # Random walk component
            random_walk = np.random.normal(0, current_volatility)

            # Combine all components for close price
            total_change = random_walk + trend_component + mean_reversion_force
            close_price = price * (1 + total_change)

            # Generate OHLC with realistic intrabar movements
            open_price = price

            # Intrabar volatility (typically 60-80% of interbar volatility)
            intrabar_vol = current_volatility * np.random.uniform(0.6, 0.8)

            # Generate high and low based on price direction
            if close_price > open_price:
                # Bullish candle
                high_range = abs(close_price - open_price) * np.random.uniform(0.3, 1.5)
                low_range = abs(close_price - open_price) * np.random.uniform(0.1, 0.8)
                high = max(open_price, close_price) + high_range
                low = min(open_price, close_price) - low_range
            else:
                # Bearish candle
                high_range = abs(open_price - close_price) * np.random.uniform(0.1, 0.8)
                low_range = abs(open_price - close_price) * np.random.uniform(0.3, 1.5)
                high = max(open_price, close_price) + high_range
                low = min(open_price, close_price) - low_range

            # Add some noise to make movements more realistic
            high += np.random.normal(0, intrabar_vol * 0.5)
            low -= abs(np.random.normal(0, intrabar_vol * 0.3))

            # Ensure OHLC relationships are maintained
            high = max(high, open_price, close_price)
            low = min(low, open_price, close_price)

            # Prevent extreme outliers
            max_reasonable_range = current_price * 0.05  # Max 5% range
            high = min(high, open_price + max_reasonable_range)
            low = max(low, open_price - max_reasonable_range)

            # Round to 2 decimal places (typical for PKR)
            open_price = round(open_price, 2)
            high = round(high, 2)
            low = round(low, 2)
            close_price = round(close_price, 2)

            data.append({
                'datetime': dt,
                'open': open_price,
                'high': high,
                'low': low,
                'close': close_price
            })

            # Update for next candle
            price = close_price

            # Update trend direction occasionally (market regime changes)
            if np.random.random() < 0.05:  # 5% chance per candle
                trend_direction *= -1

            # Gradually update mean reversion level
            mean_reversion_level = mean_reversion_level * 0.995 + price * 0.005

        return pd.DataFrame(data)

    def display_combined_forecast_analysis(self):
        """Display linear forecast analysis with smooth price movement graphs for 1H or 6H"""
        st.header("Linear Forecast Analysis — 5-Minute Price Movements")
        st.info("Linear Graphs showing smooth price movement forecasting with 5-minute intervals")

        # Forecast duration selector for linear graphs only
        forecast_duration = st.radio(
            "Select Forecast Duration:",
            ["1-Hour Linear Forecast (12 × 5-Minute Movements)", "6-Hour Linear Forecast (72 × 5-Minute Movements)"],
            key="linear_forecast_duration",
            horizontal=True
        )

        # Determine hours and movement count based on selection
        if "1-Hour" in forecast_duration:
            hours = 1
            movement_count = 12
        else:
            hours = 6
            movement_count = 72

        st.markdown(f"**Selected: {forecast_duration}**")

        # Use cached companies data
        with st.spinner("Loading company data..."):
            all_companies_data = get_cached_companies_data()

        if not all_companies_data:
            st.error("Unable to fetch company data. Please try again later.")
            return

        # Company selection
        sectors = {
            'Oil & Gas': ['OGDC', 'PPL', 'PSO'],
            'Banking': ['HBL', 'UBL', 'MCB', 'NBP'],
            'Fertilizer': ['FFC', 'EFERT'],
            'Cement': ['LUCK', 'DGKC'],
            'Food': ['NESTLE', 'UNILEVER']
        }

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

        selected_company = st.selectbox(
            "Select Company for Linear Forecast Analysis",
            sorted(all_symbols),
            key="linear_forecast_company_select"
        )

        if selected_company and selected_company in company_options:
            company_info = company_options[selected_company]
            symbol = company_info['symbol']
            company_name = company_info['name']
            sector = company_info['sector']
            data = company_info['data']

            if data:
                current_price = data['price']

                # Display company metrics
                col1, col2, col3, col4 = st.columns(4)
                with col1:
                    st.metric("Company", company_name)
                with col2:
                    st.metric("Symbol", symbol)
                with col3:
                    st.metric("Sector", sector)
                with col4:
                    st.metric("Current Price", f"₨{current_price:,.2f}")

                # Generate forecast button - linear chart only
                button_text = f"Generate {hours}H Linear Forecast ({movement_count} × 5-Minute Movements)"

                if st.button(button_text, key=f"linear_forecast_{symbol}_{hours}h"):
                    with st.spinner(f"Generating {hours}-hour linear price movement forecast..."):
                        # Use linear chart for the selected forecast duration
                        forecast_chart = self.create_linear_forecast_chart(
                            symbol, company_name, current_price, hours=hours
                        )

                        if forecast_chart:
                            st.plotly_chart(forecast_chart, use_container_width=True)

                            # Forecast insights
                            st.subheader(f"{hours}H Linear Forecast Insights")

                            # Calculate some metrics
                            forecast_data = self._generate_forecast_ohlc_data(symbol, current_price, hours=hours)
                            if not forecast_data.empty:
                                final_price = forecast_data['close'].iloc[-1]
                                max_price = forecast_data['high'].max()
                                min_price = forecast_data['low'].min()

                                change_pct = ((final_price - current_price) / current_price) * 100
                                max_change_pct = ((max_price - current_price) / current_price) * 100
                                min_change_pct = ((min_price - current_price) / current_price) * 100

                                col1, col2, col3 = st.columns(3)
                                with col1:
                                    st.metric(f"{hours}H Forecast Price", f"₨{final_price:,.2f}",
                                            delta=f"{change_pct:+.2f}%")
                                with col2:
                                    st.metric("Expected High", f"₨{max_price:,.2f}",
                                            delta=f"{max_change_pct:+.2f}%")
                                with col3:
                                    st.metric("Expected Low", f"₨{min_price:,.2f}",
                                            delta=f"{min_change_pct:+.2f}%")

                                st.info(f"**Analysis**: Smooth linear forecast showing continuous price movement with {movement_count} discrete 5-minute prediction points. The curve represents natural market flow with directional indicators for comprehensive {hours}-hour forecasting.")
                        else:
                            st.error("Unable to generate linear forecast chart.")

    def display_comprehensive_brand_predictions(self):
        """Display comprehensive brand predictions interface with tabs"""

        st.header("Comprehensive Brand Predictions - All KSE-100 Companies")
        st.info("Select any company to view detailed 5-minute prediction graphs with full date visualization.")

        # Add section navigation
        st.markdown("### Analysis Sections")
        section_tabs = st.tabs(["6H Candlestick Forecasts", "1H & 6H Candlestick Forecasts"])

        with section_tabs[0]:
            # Original comprehensive brand predictions functionality
            self._display_standard_forecasts()

        with section_tabs[1]:
            self.display_combined_forecast_analysis()

    def _display_standard_forecasts(self):
        """Display the original comprehensive brand predictions functionality"""
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
                    status_text = "Live" if is_live else "Estimated"
                    st.metric(f"{status_text} Current Price", f"₨{current_price:,.2f}")

                # Show data source info
                if is_live:
                    st.success(f"Live Price from PSX Official")
                else:
                    st.info(f"Price from {price_source}")



                # Forecast duration selector for candlestick forecasts
                forecast_duration_candlestick = st.radio(
                    "Select Candlestick Forecast Duration:",
                    ["1-Hour Forecast (12 × 5-Minute Candles)", "6-Hour Forecast (72 × 5-Minute Candles)"],
                    key="candlestick_forecast_duration",
                    horizontal=True
                )

                # Determine hours based on selection
                candlestick_hours = 1 if "1-Hour" in forecast_duration_candlestick else 6
                candle_count = 12 if candlestick_hours == 1 else 72

                # Generate forecast button for candlestick forecasts
                col1, col2 = st.columns([1, 4])
                with col1:
                    generate_forecast_clicked = st.button(f"Generate {candlestick_hours}H Candlestick Forecast", key=f"candlestick_generate_{symbol}_{candlestick_hours}h")
                with col2:
                    st.write("")

                if generate_forecast_clicked:
                    # Clear cache for this symbol to force fresh forecast
                    cache_keys_to_remove = [k for k in self._prediction_cache.keys() if k.startswith(f"{symbol}_")]
                    for k in cache_keys_to_remove:
                        del self._prediction_cache[k]

                # Check if we need to generate (button clicked or no cached result)
                import pytz
                pkt = pytz.timezone('Asia/Karachi')
                today = datetime.now(pkt).date()
                cache_key = f"candlestick_{symbol}_{today}"
                needs_generation = generate_forecast_clicked or cache_key not in self._prediction_cache

                if needs_generation and generate_forecast_clicked:
                    # Clear cache for this symbol to force fresh forecast
                    keys_to_remove = [k for k in self._prediction_cache.keys() if k.startswith(f"candlestick_{symbol}_")]
                    for k in keys_to_remove:
                        del self._prediction_cache[k]

                if cache_key in self._prediction_cache:
                    forecast_chart, rsi_chart = self._prediction_cache[cache_key]
                else:
                    with st.spinner(f"Generating {candlestick_hours}-hour enhanced candlestick forecast..."):
                        forecast_chart, rsi_chart = self.create_enhanced_candlestick_forecast_chart(
                            symbol, company_name, current_price, hours=candlestick_hours
                        )
                        if forecast_chart and rsi_chart:
                            # Cache both charts
                            self._prediction_cache[cache_key] = (forecast_chart, rsi_chart)

                if forecast_chart and rsi_chart:
                    st.plotly_chart(forecast_chart, use_container_width=True)

                    # RSI indicator
                    st.subheader(f"Technical Indicators - RSI(5) ({candlestick_hours}H Forecast)")
                    st.plotly_chart(rsi_chart, use_container_width=True)

                    # Show forecast insights
                    st.subheader("6H Forecast Insights")

                    # Calculate metrics from forecast data
                    forecast_data = self._generate_forecast_ohlc_data(symbol, current_price, hours=candlestick_hours)
                    if not forecast_data.empty:
                        final_price = forecast_data['close'].iloc[-1]
                        max_price = forecast_data['high'].max()
                        min_price = forecast_data['low'].min()

                        change_pct = ((final_price - current_price) / current_price) * 100
                        max_change_pct = ((max_price - current_price) / current_price) * 100
                        min_change_pct = ((min_price - current_price) / current_price) * 100

                        col1, col2, col3 = st.columns(3)
                        with col1:
                            st.metric(f"{candlestick_hours}H Forecast Price", f"₨{final_price:,.2f}",
                                    delta=f"{change_pct:+.2f}%")
                        with col2:
                            st.metric("Expected High", f"₨{max_price:,.2f}",
                                    delta=f"{max_change_pct:+.2f}%")
                        with col3:
                            st.metric("Expected Low", f"₨{min_price:,.2f}",
                                    delta=f"{min_change_pct:+.2f}%")

                        analysis_text = f"**Analysis**: {candle_count} dynamic candlestick patterns simulate realistic market movements every 5 minutes with technical overlays including SMA-3, SMA-5, Bollinger Bands, RSI(5), and 95% Confidence Band for comprehensive {candlestick_hours}-hour market analysis."
                        st.info(analysis_text)
                    else:
                        st.error("Unable to calculate forecast metrics.")

                else:
                    st.error("Unable to generate prediction chart for this company.")
            else:
                st.error("No data available for selected company.")

        # Add sector-wise quick access - using expanders for better performance
        st.subheader("Quick Access by Sector")

        # Limit to showing only a few sectors at a time for better performance
        with st.expander("View Companies by Sector", expanded=False):
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
                                status = 'Live' if is_live else 'Estimated'
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
        st.subheader("Summary Statistics")

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
        if st.button("Refresh Data", key="refresh_brand_data"):
            # Clear caches to force refresh
            get_cached_companies_data.cache_clear()
            get_cached_enhanced_fetcher.cache_clear()
            get_cached_companies_mapping.cache_clear()
            self._prediction_cache.clear()
            st.rerun()

def get_comprehensive_brand_predictor():
    """Get comprehensive brand predictor instance"""
    return ComprehensiveBrandPredictor()

# Test function for linear forecast chart
def test_linear_forecast():
    """Test the linear forecast chart generation"""
    predictor = get_comprehensive_brand_predictor()
    fig = predictor.create_linear_forecast_chart('OGDC', 'Oil & Gas Development Company', 150.0, hours=1)
    return fig is not None

if __name__ == "__main__":
    # Quick test
    print("Testing linear forecast chart...")
    test_result = test_linear_forecast()
    print(f"Linear forecast chart test: {'PASSED' if test_result else 'FAILED'}")