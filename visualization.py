import plotly.graph_objects as go
from plotly.subplots import make_subplots
import pandas as pd
import numpy as np
from datetime import datetime, timedelta

class ChartVisualizer:
    """Class to handle chart visualizations for stock data"""
    
    def __init__(self):
        self.colors = {
            'primary': '#1f77b4',
            'secondary': '#ff7f0e',
            'success': '#2ca02c',
            'danger': '#d62728',
            'warning': '#ff7f0e',
            'info': '#17a2b8',
            'light': '#f8f9fa',
            'dark': '#343a40'
        }
    
    def create_price_chart(self, data, title="Stock Price Chart"):
        """
        Create an interactive price chart with OHLC data

        Args:
            data (pd.DataFrame): Stock data with OHLC values
            title (str): Chart title

        Returns:
            plotly.graph_objects.Figure: Interactive chart
        """

        # Get column names
        date_col = self._get_column(data, 'date') or self._get_column(data, 'datetime') or self._get_column(data, 'time')
        close_col = self._get_column(data, 'close')
        open_col = self._get_column(data, 'open')
        volume_col = self._get_column(data, 'volume') or self._get_column(data, 'vol')

        if not date_col or not close_col:
            # Return empty chart if essential columns missing
            fig = go.Figure()
            fig.add_annotation(
                text="Insufficient data for price chart",
                xref="paper", yref="paper",
                x=0.5, y=0.5,
                showarrow=False,
                font=dict(size=16)
            )
            return fig

        fig = make_subplots(
            rows=2, cols=1,
            shared_xaxes=True,
            vertical_spacing=0.1,
            subplot_titles=(title, "Volume"),
            row_width=[0.7, 0.3]
        )

        # Linear price chart (replacing candlestick with linear line)
        fig.add_trace(
            go.Scatter(
                x=data[date_col],
                y=data[close_col],
                mode='lines',
                name="Price",
                line=dict(color=self.colors['primary'], width=2),
                hovertemplate='<b>Date:</b> %{x}<br><b>Price:</b> %{y:.2f}<extra></extra>'
            ),
            row=1, col=1
        )

        # Add moving averages
        if len(data) >= 5:
            ma5 = data[close_col].rolling(window=5).mean()
            fig.add_trace(
                go.Scatter(
                    x=data[date_col],
                    y=ma5,
                    mode='lines',
                    name='MA5',
                    line=dict(color=self.colors['primary'], width=1),
                    opacity=0.7
                ),
                row=1, col=1
            )

        if len(data) >= 10:
            ma10 = data[close_col].rolling(window=10).mean()
            fig.add_trace(
                go.Scatter(
                    x=data[date_col],
                    y=ma10,
                    mode='lines',
                    name='MA10',
                    line=dict(color=self.colors['secondary'], width=1),
                    opacity=0.7
                ),
                row=1, col=1
            )

        # Volume bars
        if volume_col:
            if open_col:
                colors = ['red' if close < open_val else 'green'
                         for close, open_val in zip(data[close_col], data[open_col])]
            else:
                colors = ['green'] * len(data)  # Default to green if no open data

            fig.add_trace(
                go.Bar(
                    x=data[date_col],
                    y=data[volume_col],
                    name="Volume",
                    marker_color=colors,
                    opacity=0.6
                ),
                row=2, col=1
            )

        # Update layout
        fig.update_layout(
            title=dict(
                text=title,
                font=dict(size=20),
                x=0.5
            ),
            xaxis_rangeslider_visible=False,
            height=600,
            showlegend=True,
            legend=dict(
                orientation="h",
                yanchor="bottom",
                y=1.02,
                xanchor="right",
                x=1
            )
        )

        # Update axes
        fig.update_xaxes(title_text="Date", row=2, col=1)
        fig.update_yaxes(title_text="Price (PKR)", row=1, col=1)
        fig.update_yaxes(title_text="Volume", row=2, col=1)

        return fig
    
    def create_forecast_chart(self, historical_data, forecast_data, title="Stock Price Forecast"):
        """
        Create forecast visualization with confidence intervals

        Args:
            historical_data (pd.DataFrame): Historical stock data
            forecast_data (pd.DataFrame): Forecast predictions
            title (str): Chart title

        Returns:
            plotly.graph_objects.Figure: Interactive forecast chart
        """

        # Get column names for historical data
        hist_date_col = self._get_column(historical_data, 'date') or self._get_column(historical_data, 'datetime')
        hist_close_col = self._get_column(historical_data, 'close')

        # Get column names for forecast data
        forecast_date_col = 'ds' if 'ds' in forecast_data.columns else self._get_column(forecast_data, 'date')
        forecast_col = 'yhat' if 'yhat' in forecast_data.columns else self._get_column(forecast_data, 'forecast')
        upper_col = 'yhat_upper' if 'yhat_upper' in forecast_data.columns else self._get_column(forecast_data, 'upper')
        lower_col = 'yhat_lower' if 'yhat_lower' in forecast_data.columns else self._get_column(forecast_data, 'lower')

        fig = go.Figure()

        # Historical prices - LINEAR STYLE
        if hist_date_col and hist_close_col:
            fig.add_trace(
                go.Scatter(
                    x=historical_data[hist_date_col],
                    y=historical_data[hist_close_col],
                    mode='lines+markers',
                    name='Historical Prices',
                    line=dict(color='#1f77b4', width=3),
                    marker=dict(size=4, color='#1f77b4')
                )
            )

        # Forecast line - LINEAR STYLE
        if forecast_date_col and forecast_col and forecast_date_col in forecast_data.columns and forecast_col in forecast_data.columns:
            fig.add_trace(
                go.Scatter(
                    x=forecast_data[forecast_date_col],
                    y=forecast_data[forecast_col],
                    mode='lines+markers',
                    name='Linear Forecast',
                    line=dict(color='#ff7f0e', width=3),
                    marker=dict(size=6, color='#ff7f0e', symbol='diamond')
                )
            )

            # Confidence intervals
            if upper_col and lower_col and upper_col in forecast_data.columns and lower_col in forecast_data.columns:
                fig.add_trace(
                    go.Scatter(
                        x=forecast_data[forecast_date_col],
                        y=forecast_data[upper_col],
                        mode='lines',
                        line=dict(width=0),
                        showlegend=False,
                        hoverinfo='skip'
                    )
                )

                fig.add_trace(
                    go.Scatter(
                        x=forecast_data[forecast_date_col],
                        y=forecast_data[lower_col],
                        mode='lines',
                        line=dict(width=0),
                        fillcolor='rgba(214, 39, 40, 0.2)',
                        fill='tonexty',
                        name='Confidence Interval',
                        hoverinfo='skip'
                    )
                )

            # Add vertical line to separate historical and forecast
            if hist_date_col and len(historical_data) > 0:
                last_historical_date = historical_data[hist_date_col].max()
                fig.add_vline(
                    x=last_historical_date,
                    line_dash="dash",
                    line_color="gray",
                    annotation_text="Forecast Start",
                    annotation_position="top"
                )

        # Update layout for LINEAR GRAPH
        fig.update_layout(
            title=dict(
                text=f"📈 {title} - Linear Forecast Graph",
                font=dict(size=22, color='#2c3e50'),
                x=0.5
            ),
            xaxis_title="Date",
            yaxis_title="Price (PKR)",
            height=600,
            showlegend=True,
            legend=dict(
                orientation="h",
                yanchor="bottom",
                y=1.02,
                xanchor="center",
                x=0.5,
                font=dict(size=12)
            ),
            plot_bgcolor='white',
            paper_bgcolor='#f8f9fa',
            font=dict(family="Arial, sans-serif", size=12),
            hovermode='x unified'
        )

        # Enhanced grid for linear visualization
        fig.update_xaxes(
            showgrid=True,
            gridwidth=1,
            gridcolor='#e1e5e9',
            title_font=dict(size=14, color='#2c3e50')
        )
        fig.update_yaxes(
            showgrid=True,
            gridwidth=1,
            gridcolor='#e1e5e9',
            title_font=dict(size=14, color='#2c3e50')
        )

        return fig
    
    def create_comparison_chart(self, companies_data, title="Companies Comparison"):
        """
        Create comparison chart for multiple companies

        Args:
            companies_data (dict): Dictionary of company data
            title (str): Chart title

        Returns:
            plotly.graph_objects.Figure: Interactive comparison chart
        """

        fig = go.Figure()

        colors = [self.colors['primary'], self.colors['secondary'], self.colors['success'],
                  self.colors['danger'], self.colors['warning'], self.colors['info']]

        for i, (company, data) in enumerate(companies_data.items()):
            if data is not None and not data.empty:
                # Get column names
                date_col = self._get_column(data, 'date') or self._get_column(data, 'datetime')
                close_col = self._get_column(data, 'close')

                if date_col and close_col and len(data) > 1:
                    # Normalize prices to percentage change from first value
                    normalized_prices = (data[close_col] / data[close_col].iloc[0] - 1) * 100

                    fig.add_trace(
                        go.Scatter(
                            x=data[date_col],
                            y=normalized_prices,
                            mode='lines',
                            name=company,
                            line=dict(color=colors[i % len(colors)], width=2)
                        )
                    )

        fig.update_layout(
            title=dict(
                text=title,
                font=dict(size=20),
                x=0.5
            ),
            xaxis_title="Date",
            yaxis_title="Price Change (%)",
            height=500,
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

        return fig
    
    def create_performance_metrics_chart(self, metrics_data, title="Performance Metrics"):
        """
        Create performance metrics visualization
        
        Args:
            metrics_data (dict): Performance metrics data
            title (str): Chart title
            
        Returns:
            plotly.graph_objects.Figure: Performance metrics chart
        """
        
        if not metrics_data:
            # Create empty chart with message
            fig = go.Figure()
            fig.add_annotation(
                text="No metrics data available",
                xref="paper", yref="paper",
                x=0.5, y=0.5,
                showarrow=False,
                font=dict(size=16)
            )
            fig.update_layout(
                title=title,
                height=300,
                xaxis=dict(visible=False),
                yaxis=dict(visible=False)
            )
            return fig
        
        # Create bar chart for metrics
        metrics_names = list(metrics_data.keys())
        metrics_values = list(metrics_data.values())
        
        fig = go.Figure(data=[
            go.Bar(
                x=metrics_names,
                y=metrics_values,
                marker_color=self.colors['primary'],
                text=[f"{v:.2f}" for v in metrics_values],
                textposition='auto'
            )
        ])
        
        fig.update_layout(
            title=dict(
                text=title,
                font=dict(size=20),
                x=0.5
            ),
            xaxis_title="Metrics",
            yaxis_title="Values",
            height=400,
            showlegend=False
        )
        
        return fig
    
    def create_market_sentiment_gauge(self, sentiment_score, title="Market Sentiment"):
        """
        Create market sentiment gauge chart
        
        Args:
            sentiment_score (float): Sentiment score between -1 and 1
            title (str): Chart title
            
        Returns:
            plotly.graph_objects.Figure: Gauge chart
        """
        
        # Convert sentiment score to 0-100 scale
        gauge_value = (sentiment_score + 1) * 50
        
        fig = go.Figure(go.Indicator(
            mode = "gauge+number+delta",
            value = gauge_value,
            domain = {'x': [0, 1], 'y': [0, 1]},
            title = {'text': title},
            delta = {'reference': 50},
            gauge = {
                'axis': {'range': [None, 100]},
                'bar': {'color': "darkblue"},
                'steps': [
                    {'range': [0, 25], 'color': "red"},
                    {'range': [25, 50], 'color': "orange"},
                    {'range': [50, 75], 'color': "yellow"},
                    {'range': [75, 100], 'color': "green"}
                ],
                'threshold': {
                    'line': {'color': "black", 'width': 4},
                    'thickness': 0.75,
                    'value': 90
                }
            }
        ))
        
        fig.update_layout(height=400)

        return fig

    def _get_column(self, data, col_name):
        """Get column by flexible name matching"""
        for col in data.columns:
            if col_name.lower() in col.lower():
                return col
        return None

    def calculate_sma(self, data, period):
        """Calculate Simple Moving Average"""
        close_col = self._get_column(data, 'close')
        if close_col:
            return data[close_col].rolling(window=period).mean()
        else:
            return pd.Series([np.nan] * len(data), index=data.index)

    def calculate_ema(self, data, period):
        """Calculate Exponential Moving Average"""
        close_col = self._get_column(data, 'close')
        if close_col:
            return data[close_col].ewm(span=period, adjust=False).mean()
        else:
            return pd.Series([np.nan] * len(data), index=data.index)

    def calculate_rsi(self, data, period=14):
        """Calculate Relative Strength Index"""
        close_col = self._get_column(data, 'close')
        if close_col:
            delta = data[close_col].diff()
            gain = (delta.where(delta > 0, 0)).rolling(window=period).mean()
            loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()
            rs = gain / loss
            rsi = 100 - (100 / (1 + rs))
            return rsi
        else:
            return pd.Series([np.nan] * len(data), index=data.index)

    def calculate_macd(self, data, fast_period=12, slow_period=26, signal_period=9):
        """Calculate MACD (Moving Average Convergence Divergence)"""
        ema_fast = self.calculate_ema(data, fast_period)
        ema_slow = self.calculate_ema(data, slow_period)
        macd = ema_fast - ema_slow
        signal = macd.ewm(span=signal_period, adjust=False).mean()
        histogram = macd - signal
        return macd, signal, histogram

    def calculate_bollinger_bands(self, data, period=20, std_dev=2):
        """Calculate Bollinger Bands"""
        if len(data) < period:
            # Return empty series if not enough data
            empty = pd.Series([np.nan] * len(data), index=data.index)
            return empty, empty, empty

        sma = self.calculate_sma(data, period)
        close_col = self._get_column(data, 'close')
        if close_col:
            std = data[close_col].rolling(window=period).std()
            upper_band = sma + (std * std_dev)
            lower_band = sma - (std * std_dev)
            return upper_band, sma, lower_band
        else:
            empty = pd.Series([np.nan] * len(data), index=data.index)
            return empty, empty, empty

    def calculate_stochastic(self, data, k_period=14, d_period=3):
        """Calculate Stochastic Oscillator"""
        low_col = self._get_column(data, 'low')
        high_col = self._get_column(data, 'high')
        close_col = self._get_column(data, 'close')

        if low_col and high_col and close_col:
            low_min = data[low_col].rolling(window=k_period).min()
            high_max = data[high_col].rolling(window=k_period).max()
            k_percent = 100 * ((data[close_col] - low_min) / (high_max - low_min))
            d_percent = k_percent.rolling(window=d_period).mean()
            return k_percent, d_percent
        else:
            empty = pd.Series([np.nan] * len(data), index=data.index)
            return empty, empty

    def create_technical_analysis_chart(self, data, title="Technical Analysis"):
        """
        Create comprehensive technical analysis chart with candlestick and multiple indicators

        Args:
            data (pd.DataFrame): Stock data with OHLC values
            title (str): Chart title

        Returns:
            plotly.graph_objects.Figure: Interactive technical analysis chart
        """

        # Find the date column or use index
        date_col = None
        for col in data.columns:
            if ('date' in col.lower() or 'datetime' in col.lower() or 'time' in col.lower() or
                'timestamp' in col.lower()):
                date_col = col
                break

        # If no date column found, check if index is datetime
        if date_col is None:
            if isinstance(data.index, pd.DatetimeIndex) or pd.api.types.is_datetime64_any_dtype(data.index):
                # Use index as date column
                data = data.reset_index()
                date_col = data.columns[0]  # The reset index creates a new column
                # Ensure all columns are lowercase for consistency
                data.columns = [col.lower() if isinstance(col, str) else str(col).lower()
                              for col in data.columns]
                date_col = date_col.lower()
            elif len(data.columns) > 0:
                # Try to use first column as date if it looks like datetime
                first_col = data.columns[0]
                try:
                    pd.to_datetime(data[first_col].iloc[0])
                    date_col = first_col
                except:
                    pass

        if date_col is None:
            raise ValueError(f"No date column found in data. Available columns: {list(data.columns)}. Index type: {type(data.index)}")

        # Find OHLC columns
        open_col = None
        high_col = None
        low_col = None
        close_col = None
        volume_col = None

        for col in data.columns:
            col_lower = col.lower()
            if 'open' in col_lower:
                open_col = col
            elif 'high' in col_lower:
                high_col = col
            elif 'low' in col_lower:
                low_col = col
            elif 'close' in col_lower:
                close_col = col
            elif 'volume' in col_lower or 'vol' in col_lower:
                volume_col = col

        if close_col is None:
            raise ValueError("No close price column found in data. Available columns: " + ", ".join(data.columns.tolist()))

        # Create subplots: Price (candlestick), Bollinger Bands, RSI, MACD, Stochastic, Volume
        fig = make_subplots(
            rows=6, cols=1,
            shared_xaxes=True,
            vertical_spacing=0.03,
            subplot_titles=('Candlestick Price Chart', 'Bollinger Bands', 'RSI (14)', 'MACD', 'Stochastic Oscillator', 'Volume'),
            row_width=[0.25, 0.15, 0.15, 0.15, 0.15, 0.1]
        )

        # 1. Candlestick chart with Moving Averages
        fig.add_trace(
            go.Candlestick(
                x=data[date_col],
                open=data[open_col] if open_col else data[close_col],
                high=data[high_col] if high_col else data[close_col],
                low=data[low_col] if low_col else data[close_col],
                close=data[close_col],
                name='Candlestick',
                increasing_line_color='green',
                decreasing_line_color='red'
            ),
            row=1, col=1
        )

        # Add Moving Averages to candlestick chart
        if len(data) >= 20:
            sma20 = self.calculate_sma(data, 20)
            ema20 = self.calculate_ema(data, 20)
            fig.add_trace(
                go.Scatter(x=data[date_col], y=sma20, line=dict(color='orange', width=2), name='SMA 20'),
                row=1, col=1
            )
            fig.add_trace(
                go.Scatter(x=data[date_col], y=ema20, line=dict(color='purple', width=2), name='EMA 20'),
                row=1, col=1
            )

        # 2. Bollinger Bands - Dedicated subplot with proper fill
        bb_upper, bb_middle, bb_lower = self.calculate_bollinger_bands(data)

        # Add traces in correct order for proper fill
        # First: Upper band (no fill)
        fig.add_trace(
            go.Scatter(x=data[date_col], y=bb_upper, mode='lines', line=dict(color='red', width=2), name='BB Upper Band', showlegend=True),
            row=2, col=1
        )

        # Second: Lower band with fill to upper band
        fig.add_trace(
            go.Scatter(x=data[date_col], y=bb_lower, mode='lines', line=dict(color='green', width=2),
                      fill='tonexty', fillcolor='rgba(255, 165, 0, 0.1)', name='BB Lower Band', showlegend=True),
            row=2, col=1
        )

        # Third: Middle band (SMA 20)
        fig.add_trace(
            go.Scatter(x=data[date_col], y=bb_middle, mode='lines', line=dict(color='blue', width=2, dash='dash'), name='BB Middle (SMA 20)', showlegend=True),
            row=2, col=1
        )

        # Fourth: Price line
        fig.add_trace(
            go.Scatter(x=data[date_col], y=data[close_col], mode='lines', line=dict(color='black', width=1), name='Price', showlegend=True),
            row=2, col=1
        )

        # 3. RSI - Dedicated subplot
        rsi = self.calculate_rsi(data)
        fig.add_trace(
            go.Scatter(x=data[date_col], y=rsi, mode='lines', line=dict(color='blue', width=2), name='RSI'),
            row=3, col=1
        )

        # RSI levels using shapes
        fig.add_shape(type="line", x0=data[date_col].min(), x1=data[date_col].max(), y0=70, y1=70,
                     line=dict(color='red', width=2, dash='dash'), row=3, col=1)
        fig.add_shape(type="line", x0=data[date_col].min(), x1=data[date_col].max(), y0=50, y1=50,
                     line=dict(color='gray', width=1, dash='dot'), row=3, col=1)
        fig.add_shape(type="line", x0=data[date_col].min(), x1=data[date_col].max(), y0=30, y1=30,
                     line=dict(color='green', width=2, dash='dash'), row=3, col=1)

        # 4. MACD - Dedicated subplot
        macd, signal, histogram = self.calculate_macd(data)
        fig.add_trace(
            go.Scatter(x=data[date_col], y=macd, mode='lines', line=dict(color='blue', width=2), name='MACD'),
            row=4, col=1
        )
        fig.add_trace(
            go.Scatter(x=data[date_col], y=signal, mode='lines', line=dict(color='red', width=2), name='Signal'),
            row=4, col=1
        )

        # MACD histogram as bars
        colors_macd = ['green' if h >= 0 else 'red' for h in histogram]
        fig.add_trace(
            go.Bar(x=data[date_col], y=histogram, name='MACD Histogram', marker_color=colors_macd, opacity=0.7),
            row=4, col=1
        )

        # 5. Stochastic Oscillator - Dedicated subplot
        k_percent, d_percent = self.calculate_stochastic(data)
        fig.add_trace(
            go.Scatter(x=data[date_col], y=k_percent, mode='lines', line=dict(color='blue', width=2), name='%K'),
            row=5, col=1
        )
        fig.add_trace(
            go.Scatter(x=data[date_col], y=d_percent, mode='lines', line=dict(color='red', width=2), name='%D'),
            row=5, col=1
        )

        # Stochastic levels using shapes
        fig.add_shape(type="line", x0=data[date_col].min(), x1=data[date_col].max(), y0=80, y1=80,
                     line=dict(color='red', width=2, dash='dash'), row=5, col=1)
        fig.add_shape(type="line", x0=data[date_col].min(), x1=data[date_col].max(), y0=20, y1=20,
                     line=dict(color='green', width=2, dash='dash'), row=5, col=1)

        # 6. Volume - Dedicated subplot
        if open_col:
            colors = ['red' if close < open else 'green'
                     for close, open in zip(data[close_col], data[open_col])]
        else:
            colors = ['green'] * len(data)  # Default to green if no open data

        if volume_col:
            fig.add_trace(
                go.Bar(
                    x=data[date_col],
                    y=data[volume_col],
                    name="Volume",
                    marker_color=colors,
                    opacity=0.8
                ),
                row=6, col=1
            )

        # Update layout
        fig.update_layout(
            title=dict(
                text=f"📈 {title} - Complete Technical Analysis Dashboard",
                font=dict(size=24, color='#2c3e50'),
                x=0.5
            ),
            xaxis_rangeslider_visible=False,
            height=1500,
            showlegend=True,
            legend=dict(
                orientation="h",
                yanchor="bottom",
                y=1.02,
                xanchor="center",
                x=0.5,
                font=dict(size=10)
            ),
            plot_bgcolor='white',
            paper_bgcolor='#f8f9fa'
        )

        # Update axes labels and styling
        fig.update_yaxes(title_text="Price (PKR)", title_font=dict(size=12), row=1, col=1)
        fig.update_yaxes(title_text="Bollinger Bands", title_font=dict(size=12), row=2, col=1)
        fig.update_yaxes(title_text="RSI Value", title_font=dict(size=12), row=3, col=1)
        fig.update_yaxes(title_text="MACD Value", title_font=dict(size=12), row=4, col=1)
        fig.update_yaxes(title_text="Stochastic Value", title_font=dict(size=12), row=5, col=1)
        fig.update_yaxes(title_text="Volume", title_font=dict(size=12), row=6, col=1)
        fig.update_xaxes(title_text="Date", title_font=dict(size=12), row=6, col=1)

        # Add grid lines for better readability
        for i in range(1, 7):
            fig.update_xaxes(showgrid=True, gridwidth=1, gridcolor='#e1e5e9', row=i, col=1)
            fig.update_yaxes(showgrid=True, gridwidth=1, gridcolor='#e1e5e9', row=i, col=1)

        return fig
