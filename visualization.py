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
                x=data['date'],
                y=data['close'],
                mode='lines',
                name="Price",
                line=dict(color=self.colors['primary'], width=2),
                hovertemplate='<b>Date:</b> %{x}<br><b>Price:</b> %{y:.2f}<extra></extra>'
            ),
            row=1, col=1
        )
        
        # Add moving averages
        if len(data) >= 5:
            ma5 = data['close'].rolling(window=5).mean()
            fig.add_trace(
                go.Scatter(
                    x=data['date'],
                    y=ma5,
                    mode='lines',
                    name='MA5',
                    line=dict(color=self.colors['primary'], width=1),
                    opacity=0.7
                ),
                row=1, col=1
            )
        
        if len(data) >= 10:
            ma10 = data['close'].rolling(window=10).mean()
            fig.add_trace(
                go.Scatter(
                    x=data['date'],
                    y=ma10,
                    mode='lines',
                    name='MA10',
                    line=dict(color=self.colors['secondary'], width=1),
                    opacity=0.7
                ),
                row=1, col=1
            )
        
        # Volume bars
        colors = ['red' if close < open else 'green' 
                 for close, open in zip(data['close'], data['open'])]
        
        fig.add_trace(
            go.Bar(
                x=data['date'],
                y=data['volume'],
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
        
        fig = go.Figure()
        
        # Historical prices - LINEAR STYLE
        fig.add_trace(
            go.Scatter(
                x=historical_data['date'],
                y=historical_data['close'],
                mode='lines+markers',
                name='Historical Prices',
                line=dict(color='#1f77b4', width=3),
                marker=dict(size=4, color='#1f77b4')
            )
        )
        
        # Forecast line - LINEAR STYLE
        fig.add_trace(
            go.Scatter(
                x=forecast_data['ds'],
                y=forecast_data['yhat'],
                mode='lines+markers',
                name='Linear Forecast',
                line=dict(color='#ff7f0e', width=3),
                marker=dict(size=6, color='#ff7f0e', symbol='diamond')
            )
        )
        
        # Confidence intervals
        fig.add_trace(
            go.Scatter(
                x=forecast_data['ds'],
                y=forecast_data['yhat_upper'],
                mode='lines',
                line=dict(width=0),
                showlegend=False,
                hoverinfo='skip'
            )
        )
        
        fig.add_trace(
            go.Scatter(
                x=forecast_data['ds'],
                y=forecast_data['yhat_lower'],
                mode='lines',
                line=dict(width=0),
                fillcolor='rgba(214, 39, 40, 0.2)',
                fill='tonexty',
                name='Confidence Interval',
                hoverinfo='skip'
            )
        )
        
        # Add vertical line to separate historical and forecast
        if len(historical_data) > 0:
            last_historical_date = historical_data['date'].max()
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
                # Normalize prices to percentage change from first value
                normalized_prices = (data['close'] / data['close'].iloc[0] - 1) * 100
                
                fig.add_trace(
                    go.Scatter(
                        x=data['date'],
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
