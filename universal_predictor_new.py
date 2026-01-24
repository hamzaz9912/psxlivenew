"""
Universal File Upload Predictor Module - Simplified and Robust
Handles any uploaded financial data (CSV, Excel) and generates predictions
Supports any brand: XAUSD, PSX companies, forex, commodities, etc.
"""

import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import io
import re
import pytz
from simple_file_reader import read_any_file, analyze_dataframe

class UniversalPredictor:
    """Universal predictor for any uploaded financial data"""
    
    def __init__(self):
        self.supported_formats = ['.csv', '.xlsx', '.xls']
        
    def process_uploaded_file(self, uploaded_file, brand_name="Unknown"):
        """Process uploaded file and extract financial data"""
        try:
            # Use robust file reader
            df, error_message = read_any_file(uploaded_file)
            
            if df is None:
                return {'error': error_message}
            
            # Analyze the dataframe structure
            analysis = analyze_dataframe(df, brand_name)
            
            if 'error' in analysis:
                return analysis
            
            # Add success flag and dataframe
            analysis['success'] = True
            analysis['dataframe'] = df
            
            return analysis
            
        except Exception as e:
            return {'error': f'Error processing file: {str(e)}'}
    
    def _detect_market_timezone(self, brand_name):
        """Detect market and timezone based on brand name"""
        brand_lower = brand_name.lower()
        
        # Define market mappings
        markets = {
            'PSX': {'country': 'Pakistan', 'timezone': 'Asia/Karachi', 'currency': 'PKR', 'session': '09:30-15:30'},
            'NYSE': {'country': 'United States', 'timezone': 'America/New_York', 'currency': 'USD', 'session': '09:30-16:00'},
            'NASDAQ': {'country': 'United States', 'timezone': 'America/New_York', 'currency': 'USD', 'session': '09:30-16:00'},
            'LSE': {'country': 'United Kingdom', 'timezone': 'Europe/London', 'currency': 'GBP', 'session': '08:00-16:30'},
            'NSE': {'country': 'India', 'timezone': 'Asia/Kolkata', 'currency': 'INR', 'session': '09:15-15:30'},
            'TSE': {'country': 'Japan', 'timezone': 'Asia/Tokyo', 'currency': 'JPY', 'session': '09:00-15:00'},
            'FOREX': {'country': 'Global', 'timezone': 'UTC', 'currency': 'USD', 'session': '24/7'},
            'CRYPTO': {'country': 'Global', 'timezone': 'UTC', 'currency': 'USD', 'session': '24/7'},
            'GOLD': {'country': 'Global', 'timezone': 'UTC', 'currency': 'USD', 'session': '24/7'}
        }
        
        # Detect based on brand patterns
        if any(psx in brand_lower for psx in ['kse', 'psx', 'ogdc', 'ppl', 'pso', 'mari', 'engro', 'luck', 'ubl', 'mcb', 'hbl']):
            return markets['PSX']
        elif any(gold in brand_lower for gold in ['xauusd', 'gold', 'xau', 'gld']):
            return markets['GOLD']
        elif any(forex in brand_lower for forex in ['usd', 'eur', 'gbp', 'jpy', 'cad', 'aud', 'chf', 'forex']):
            return markets['FOREX']
        elif any(crypto in brand_lower for crypto in ['btc', 'eth', 'crypto', 'bitcoin', 'ethereum']):
            return markets['CRYPTO']
        elif any(us in brand_lower for us in ['nasdaq', 'nyse', 'sp500', 'dow']):
            return markets['NYSE']
        elif any(uk in brand_lower for uk in ['ftse', 'lse', 'london']):
            return markets['LSE']
        elif any(india in brand_lower for india in ['nse', 'sensex', 'nifty']):
            return markets['NSE']
        elif any(japan in brand_lower for japan in ['nikkei', 'tse', 'tokyo']):
            return markets['TSE']
        else:
            # Default to PSX for unknown brands
            return markets['PSX']
    
    def _get_market_status(self, market_time, market_info):
        """Determine if market is open based on time and trading session"""
        try:
            if market_info['session'] == '24/7':
                return 'Open (24/7 Trading)'
            
            # Parse trading session
            session_parts = market_info['session'].split('-')
            if len(session_parts) != 2:
                return 'Unknown'
            
            start_time_str, end_time_str = session_parts
            start_hour, start_min = map(int, start_time_str.split(':'))
            end_hour, end_min = map(int, end_time_str.split(':'))
            
            current_time = market_time.time()
            start_time = market_time.replace(hour=start_hour, minute=start_min).time()
            end_time = market_time.replace(hour=end_hour, minute=end_min).time()
            
            # Check if current time is within trading session
            if start_time <= current_time <= end_time:
                # Also check if it's a weekday (Mon-Fri)
                if market_time.weekday() < 5:  # 0-4 are Mon-Fri
                    return 'Open'
                else:
                    return 'Closed (Weekend)'
            else:
                return 'Closed (After Hours)'
                
        except Exception as e:
            return f'Unknown (Error: {str(e)})'
    
    def generate_predictions(self, df, brand_name, price_column, date_column=None):
        """Generate predictions based on uploaded data"""
        try:
            # Validate price column
            if price_column not in df.columns:
                return {'error': f'Price column "{price_column}" not found in data'}
            
            # Detect market and timezone
            market_info = self._detect_market_timezone(brand_name)
            
            # Get timezone information
            market_tz = pytz.timezone(market_info['timezone'])
            utc_now = datetime.now(pytz.UTC)
            market_time = utc_now.astimezone(market_tz)
            
            # Convert price column to numeric
            try:
                price_data = pd.to_numeric(df[price_column], errors='coerce')
                price_data = price_data.dropna()
                
                if len(price_data) == 0:
                    return {'error': f'No valid numeric data found in price column "{price_column}"'}
                    
            except Exception as e:
                return {'error': f'Cannot convert price column to numeric: {str(e)}'}
            
            # Get current price from FIRST ROW (most recent data)
            current_price = float(price_data.iloc[0])  # Use first row instead of last
            volatility = float(price_data.pct_change().std()) if len(price_data) > 1 else 0.02
            trend = float((price_data.iloc[-1] - price_data.iloc[0]) / price_data.iloc[0]) if len(price_data) > 1 else 0.0
            
            # Process date column if available
            date_data = None
            if date_column and date_column in df.columns:
                try:
                    date_data = pd.to_datetime(df[date_column], errors='coerce')
                    date_data = date_data.dropna()
                except:
                    date_data = None
            
            # Generate predictions
            predictions = {
                'current_price': current_price,
                'volatility': volatility,
                'trend': trend,
                'data_points': len(price_data),
                'market_info': {
                    'country': market_info['country'],
                    'timezone': market_info['timezone'],
                    'currency': market_info['currency'],
                    'trading_session': market_info['session'],
                    'upload_time_utc': utc_now.strftime('%Y-%m-%d %H:%M:%S UTC'),
                    'upload_time_market': market_time.strftime('%Y-%m-%d %H:%M:%S %Z'),
                    'market_status': self._get_market_status(market_time, market_info)
                },
                'historical_data': {
                    'prices': price_data.tolist(),
                    'dates': date_data.dt.strftime('%Y-%m-%d').tolist() if date_data is not None else []
                },
                'predictions': {
                    'next_7_days': self._generate_next_7_days_prediction(current_price, trend, volatility, brand_name),
                    'intraday_5min': self._generate_intraday_5min_prediction(current_price, volatility, brand_name),
                    'short_term': self._generate_short_term_prediction(current_price, trend, volatility, brand_name),
                    'medium_term': self._generate_medium_term_prediction(current_price, trend, volatility, brand_name),
                    'long_term': self._generate_long_term_prediction(current_price, trend, volatility, brand_name)
                },
                'technical_analysis': self._perform_technical_analysis(price_data)
            }
            
            return predictions
            
        except Exception as e:
            return {'error': f'Error generating predictions: {str(e)}'}
    
    def _generate_short_term_prediction(self, current_price, trend, volatility, brand_name):
        """Generate short-term predictions (1-7 days)"""
        predictions = []
        
        for i in range(1, 8):  # Next 7 days
            # Simple prediction model with trend and volatility
            daily_change = trend + np.random.normal(0, volatility) * 0.1
            predicted_price = current_price * (1 + daily_change)
            
            predictions.append({
                'date': (datetime.now() + timedelta(days=i)).strftime('%Y-%m-%d'),
                'predicted_price': round(predicted_price, 4),
                'confidence': max(0.5, 1 - abs(daily_change))
            })
            
            current_price = predicted_price
        
        return predictions
    
    def _generate_medium_term_prediction(self, current_price, trend, volatility, brand_name):
        """Generate medium-term predictions (1-4 weeks)"""
        predictions = []
        
        for i in range(1, 5):  # Next 4 weeks
            weekly_change = trend * 7 + np.random.normal(0, volatility) * 0.3
            predicted_price = current_price * (1 + weekly_change)
            
            predictions.append({
                'week': i,
                'date': (datetime.now() + timedelta(weeks=i)).strftime('%Y-%m-%d'),
                'predicted_price': round(predicted_price, 4),
                'confidence': max(0.3, 1 - abs(weekly_change))
            })
            
            current_price = predicted_price
        
        return predictions
    
    def _generate_long_term_prediction(self, current_price, trend, volatility, brand_name):
        """Generate long-term predictions (1-3 months)"""
        predictions = []
        
        for i in range(1, 4):  # Next 3 months
            monthly_change = trend * 30 + np.random.normal(0, volatility) * 0.5
            predicted_price = current_price * (1 + monthly_change)
            
            predictions.append({
                'month': i,
                'date': (datetime.now() + timedelta(days=30*i)).strftime('%Y-%m-%d'),
                'predicted_price': round(predicted_price, 4),
                'confidence': max(0.2, 1 - abs(monthly_change))
            })
            
            current_price = predicted_price
        
        return predictions
    
    def _generate_next_7_days_prediction(self, current_price, trend, volatility, brand_name):
        """Generate next 7 days specific predictions with detailed analysis"""
        predictions = []
        working_price = current_price
        
        for i in range(1, 8):  # Next 7 days
            # Enhanced prediction model with trend and volatility
            daily_trend = trend * 0.1  # Daily trend component
            daily_volatility = np.random.normal(0, volatility * 0.05)  # Daily volatility
            market_sentiment = np.random.uniform(-0.02, 0.02)  # Random market sentiment
            
            daily_change = daily_trend + daily_volatility + market_sentiment
            predicted_price = working_price * (1 + daily_change)
            
            # Calculate confidence based on volatility
            confidence = max(0.6, 1 - abs(daily_change * 10))
            
            predictions.append({
                'day': i,
                'date': (datetime.now() + timedelta(days=i)).strftime('%Y-%m-%d'),
                'predicted_price': round(predicted_price, 4),
                'change_from_current': round(((predicted_price - current_price) / current_price) * 100, 2),
                'daily_change': round(daily_change * 100, 2),
                'confidence': round(confidence, 2),
                'trend': 'Bullish' if daily_change > 0 else 'Bearish' if daily_change < -0.005 else 'Neutral'
            })
            
            working_price = predicted_price
        
        return predictions
    
    def _generate_intraday_5min_prediction(self, current_price, volatility, brand_name):
        """Generate intraday 5-minute predictions for selected trading day"""
        predictions = {}
        
        # Generate predictions for next 3 days
        for day_offset in range(3):
            day_predictions = []
            target_date = datetime.now() + timedelta(days=day_offset)
            day_key = target_date.strftime('%Y-%m-%d')
            
            # Trading session from 9:30 AM to 3:30 PM (6 hours = 72 intervals of 5 minutes)
            session_start = target_date.replace(hour=9, minute=30, second=0, microsecond=0)
            working_price = current_price
            
            # Add small daily adjustment
            daily_adjustment = np.random.uniform(-0.01, 0.01)
            working_price = working_price * (1 + daily_adjustment)
            
            for interval in range(72):  # 72 intervals of 5 minutes = 6 hours
                timestamp = session_start + timedelta(minutes=interval * 5)
                
                # 5-minute price movement (smaller volatility)
                interval_change = np.random.normal(0, volatility * 0.01)  # Very small 5-min changes
                predicted_price = working_price * (1 + interval_change)
                
                day_predictions.append({
                    'time': timestamp.strftime('%H:%M'),
                    'datetime': timestamp.strftime('%Y-%m-%d %H:%M'),
                    'predicted_price': round(predicted_price, 4),
                    'change_from_prev': round(((predicted_price - working_price) / working_price) * 100, 3),
                    'volume_indicator': np.random.randint(1000, 10000)  # Simulated volume
                })
                
                working_price = predicted_price
            
            predictions[day_key] = {
                'date': day_key,
                'day_name': target_date.strftime('%A'),
                'session_start': '09:30',
                'session_end': '15:30',
                'total_intervals': len(day_predictions),
                'predictions': day_predictions,
                'day_summary': {
                    'opening_price': day_predictions[0]['predicted_price'],
                    'closing_price': day_predictions[-1]['predicted_price'],
                    'high_price': max(p['predicted_price'] for p in day_predictions),
                    'low_price': min(p['predicted_price'] for p in day_predictions),
                    'daily_change': round(((day_predictions[-1]['predicted_price'] - day_predictions[0]['predicted_price']) / day_predictions[0]['predicted_price']) * 100, 2)
                }
            }
        
        return predictions
    
    def _perform_technical_analysis(self, price_data):
        """Perform basic technical analysis"""
        try:
            if len(price_data) < 5:
                return {'error': 'Not enough data for technical analysis'}
            
            # Moving averages
            ma_5 = price_data.rolling(5).mean().iloc[-1] if len(price_data) >= 5 else None
            ma_10 = price_data.rolling(10).mean().iloc[-1] if len(price_data) >= 10 else None
            ma_20 = price_data.rolling(20).mean().iloc[-1] if len(price_data) >= 20 else None
            
            # RSI calculation (simplified)
            delta = price_data.diff()
            gain = delta.where(delta > 0, 0)
            loss = -delta.where(delta < 0, 0)
            
            if len(gain) >= 14:
                avg_gain = gain.rolling(14).mean().iloc[-1]
                avg_loss = loss.rolling(14).mean().iloc[-1]
                rs = avg_gain / avg_loss if avg_loss != 0 else 0
                rsi = 100 - (100 / (1 + rs))
            else:
                rsi = 50  # Neutral RSI
            
            # Support and resistance levels
            support_level = float(price_data.min())
            resistance_level = float(price_data.max())
            
            return {
                'moving_averages': {
                    'ma_5': float(ma_5) if ma_5 is not None else None,
                    'ma_10': float(ma_10) if ma_10 is not None else None,
                    'ma_20': float(ma_20) if ma_20 is not None else None
                },
                'rsi': float(rsi),
                'support_level': support_level,
                'resistance_level': resistance_level
            }
            
        except Exception as e:
            return {'error': f'Technical analysis failed: {str(e)}'}
    
    def create_prediction_chart(self, df, predictions, price_column, date_column=None):
        """Create interactive prediction chart with timezone information"""
        try:
            fig = go.Figure()
            
            # Historical data
            if date_column and date_column in df.columns:
                x_data = df[date_column]
            else:
                x_data = range(len(df))
            
            fig.add_trace(go.Scatter(
                x=x_data,
                y=df[price_column],
                mode='lines',
                name='Historical Data',
                line=dict(color='blue', width=2)
            ))
            
            # Short-term predictions
            short_term = predictions['predictions']['short_term']
            pred_dates = [pred['date'] for pred in short_term]
            pred_prices = [pred['predicted_price'] for pred in short_term]
            
            fig.add_trace(go.Scatter(
                x=pred_dates,
                y=pred_prices,
                mode='lines+markers',
                name='Short-term Predictions',
                line=dict(color='red', width=2, dash='dash'),
                marker=dict(size=6)
            ))
            
            # Get timezone information for chart annotation
            timezone_info = ""
            if 'market_info' in predictions:
                market_info = predictions['market_info']
                timezone_info = f"Market: {market_info['country']} ({market_info['timezone']})<br>Upload Time: {market_info['upload_time_market']}<br>Status: {market_info['market_status']}"
            
            # Chart title with brand name
            brand_name = predictions.get('brand_name', 'Unknown')
            
            fig.update_layout(
                title=f'Price Predictions for {brand_name}',
                xaxis_title='Date',
                yaxis_title='Price',
                height=500,
                annotations=[
                    dict(
                        text=timezone_info,
                        showarrow=False,
                        xref="paper", yref="paper",
                        x=1.02, y=0.02,
                        xanchor="left", yanchor="bottom",
                        font=dict(size=10, color="gray"),
                        bgcolor="rgba(255,255,255,0.8)",
                        bordercolor="gray",
                        borderwidth=1
                    )
                ] if timezone_info else []
            )
            
            return fig
            
        except Exception as e:
            return None

# Global instance
_universal_predictor = None

def get_universal_predictor():
    """Get universal predictor instance"""
    global _universal_predictor
    if _universal_predictor is None:
        _universal_predictor = UniversalPredictor()
    return _universal_predictor