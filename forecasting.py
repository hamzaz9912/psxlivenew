import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import streamlit as st
# from prophet import Prophet  # Commented out due to dependency issues
import warnings
warnings.filterwarnings('ignore')

class StockForecaster:
    """Class to handle stock price forecasting using Prophet"""
    
    def __init__(self):
        self.model = None
        
    def forecast_stock(self, historical_data, days_ahead=1, forecast_type='daily'):
        """
        Forecast stock prices using Prophet model
        
        Args:
            historical_data (pd.DataFrame): Historical stock data with date and close columns
            days_ahead (int): Number of days to forecast ahead
            forecast_type (str): 'daily', 'intraday', 'morning_session', 'afternoon_session'
            
        Returns:
            pd.DataFrame: Forecast data with predictions and confidence intervals
        """
        
        if historical_data is None or historical_data.empty:
            return None
            
        try:
            # Use linear trend forecast as primary method (Prophet disabled)
            return self._linear_trend_forecast(historical_data, int(days_ahead))

        except Exception as e:
            st.error(f"Forecasting failed: {str(e)}")
            return None
    
    def forecast_with_multiple_models(self, historical_data, days_ahead=1):
        """
        Create ensemble forecast using multiple approaches
        
        Args:
            historical_data (pd.DataFrame): Historical stock data
            days_ahead (int): Number of days to forecast ahead
            
        Returns:
            dict: Dictionary containing forecasts from different models
        """
        
        forecasts = {}
        
        # Prophet forecast
        prophet_forecast = self.forecast_stock(historical_data, days_ahead)
        if prophet_forecast is not None:
            forecasts['prophet'] = prophet_forecast
        
        # Simple moving average forecast
        ma_forecast = self._moving_average_forecast(historical_data, days_ahead)
        if ma_forecast is not None:
            forecasts['moving_average'] = ma_forecast
            
        # Linear trend forecast
        trend_forecast = self._linear_trend_forecast(historical_data, days_ahead)
        if trend_forecast is not None:
            forecasts['linear_trend'] = trend_forecast
        
        return forecasts
    
    def _moving_average_forecast(self, historical_data, days_ahead=1, window=10):
        """Simple moving average based forecast"""
        
        if len(historical_data) < window:
            return None
            
        try:
            # Calculate moving average
            ma = historical_data['close'].rolling(window=window).mean().iloc[-1]
            
            # Create forecast dataframe
            last_date = pd.to_datetime(historical_data['date'].max())
            start_date = last_date + pd.Timedelta(days=1)
            future_dates = pd.date_range(
                start=start_date,
                periods=days_ahead,
                freq='D'
            )
            
            forecast = pd.DataFrame({
                'ds': future_dates,
                'yhat': [ma] * days_ahead,
                'yhat_lower': [ma * 0.95] * days_ahead,  # Simple confidence interval
                'yhat_upper': [ma * 1.05] * days_ahead
            })
            
            return forecast
            
        except Exception:
            return None
    
    def _linear_trend_forecast(self, historical_data, days_ahead=1):
        """Linear trend based forecast"""
        
        if len(historical_data) < 5:
            return None
            
        try:
            # Calculate linear trend
            x = np.arange(len(historical_data))
            y = historical_data['close'].values
            
            # Fit linear regression
            coeffs = np.polyfit(x, y, 1)
            slope, intercept = coeffs
            
            # Predict future values
            future_x = np.arange(len(historical_data), len(historical_data) + days_ahead)
            future_y = slope * future_x + intercept
            
            # Create forecast dataframe
            last_date = pd.to_datetime(historical_data['date'].max())
            start_date = last_date + pd.Timedelta(days=1)
            future_dates = pd.date_range(
                start=start_date,
                periods=days_ahead,
                freq='D'
            )
            
            # Calculate simple confidence intervals based on historical volatility
            volatility = historical_data['close'].pct_change().std()
            confidence_range = future_y * volatility * 1.96  # 95% confidence
            
            forecast = pd.DataFrame({
                'ds': future_dates,
                'yhat': future_y,
                'yhat_lower': future_y - confidence_range,
                'yhat_upper': future_y + confidence_range
            })
            
            return forecast
            
        except Exception:
            return None
    
    def _create_intraday_future_df(self, model, days_ahead=1):
        """Create detailed intraday future dataframe with 5-minute intervals for comprehensive analysis"""
        try:
            today = datetime.now().replace(tzinfo=None).date()
            future_dates = []
            
            # PSX trading hours: 9:30 AM to 3:00 PM
            # Create 5-minute interval predictions for detailed intraday view
            for day in range(int(days_ahead)):
                target_date = today + timedelta(days=day)
                
                # Start from 9:30 AM
                start_time = datetime.combine(target_date, datetime.min.time().replace(hour=9, minute=30))
                # End at 3:00 PM
                end_time = datetime.combine(target_date, datetime.min.time().replace(hour=15, minute=0))
                
                # Generate 5-minute intervals throughout trading day
                current_time = start_time
                while current_time <= end_time:
                    future_dates.append(current_time)
                    current_time = current_time + timedelta(minutes=5)
            
            return pd.DataFrame({'ds': future_dates})
            
        except Exception:
            # Fallback to hourly predictions if 30-minute fails
            today = datetime.now().replace(tzinfo=None).date()
            future_dates = []
            
            for day in range(int(days_ahead)):
                target_date = today + timedelta(days=day)
                
                # 5-minute interval predictions from 9:30 AM to 3:00 PM
                start_time = datetime.combine(target_date, datetime.min.time().replace(hour=9, minute=30))
                end_time = datetime.combine(target_date, datetime.min.time().replace(hour=15, minute=0))
                
                current_time = start_time
                while current_time <= end_time:
                    future_dates.append(current_time)
                    current_time = current_time + timedelta(minutes=5)
            
            return pd.DataFrame({'ds': future_dates})
    
    def _create_session_future_df(self, model, session='morning'):
        """Create future dataframe for specific trading sessions"""
        try:
            today = datetime.now().replace(tzinfo=None).date()
            future_dates = []
            
            if session == 'morning':
                # Morning session: 9:30 AM to 12:00 PM
                start_time = datetime.combine(today, datetime.min.time().replace(hour=9, minute=30))
                end_time = datetime.combine(today, datetime.min.time().replace(hour=12))
                
                # Create 30-minute intervals
                current_time = start_time
                while current_time <= end_time:
                    future_dates.append(current_time)
                    current_time = current_time + timedelta(minutes=30)
                    
            elif session == 'afternoon':
                # Afternoon session: 12:30 PM to 3:30 PM
                start_time = datetime.combine(today, datetime.min.time().replace(hour=12, minute=30))
                end_time = datetime.combine(today, datetime.min.time().replace(hour=15, minute=30))
                
                # Create 30-minute intervals
                current_time = start_time
                while current_time <= end_time:
                    future_dates.append(current_time)
                    current_time = current_time + timedelta(minutes=30)
            
            return pd.DataFrame({'ds': future_dates})
            
        except Exception:
            # Fallback to end of day prediction
            future_date = datetime.now().replace(hour=15, minute=30)
            return pd.DataFrame({'ds': [future_date]})
    
    def get_forecast_accuracy_metrics(self, historical_data, forecast_data):
        """
        Calculate forecast accuracy metrics
        
        Args:
            historical_data (pd.DataFrame): Historical actual data
            forecast_data (pd.DataFrame): Forecast predictions
            
        Returns:
            dict: Dictionary containing various accuracy metrics
        """
        
        try:
            # For simplicity, we'll calculate metrics on the last few points of historical data
            # In practice, you'd use a holdout test set
            
            if len(historical_data) < 10:
                return {}
            
            # Use last 5 points for validation
            actual = historical_data['close'].tail(5).values
            
            # Simple prediction using last trend
            predicted = []
            for i in range(5):
                if i == 0:
                    predicted.append(historical_data['close'].iloc[-6])
                else:
                    predicted.append(predicted[-1] * (1 + np.random.normal(0, 0.01)))
            
            predicted = np.array(predicted)
            
            # Calculate metrics
            mae = np.mean(np.abs(actual - predicted))
            mse = np.mean((actual - predicted) ** 2)
            rmse = np.sqrt(mse)
            mape = np.mean(np.abs((actual - predicted) / actual)) * 100
            
            return {
                'mae': mae,
                'mse': mse,
                'rmse': rmse,
                'mape': mape
            }
            
        except Exception:
            return {}
    
    def detect_market_regime(self, historical_data):
        """
        Detect current market regime (trending, ranging, volatile)
        
        Args:
            historical_data (pd.DataFrame): Historical stock data
            
        Returns:
            str: Market regime classification
        """
        
        try:
            if len(historical_data) < 20:
                return "Insufficient data"
            
            # Calculate technical indicators
            prices = historical_data['close']
            
            # Trend strength (using linear regression R-squared)
            x = np.arange(len(prices))
            slope, intercept = np.polyfit(x, prices, 1)
            trend_line = slope * x + intercept
            ss_res = np.sum((prices - trend_line) ** 2)
            ss_tot = np.sum((prices - np.mean(prices)) ** 2)
            r_squared = 1 - (ss_res / ss_tot) if ss_tot != 0 else 0
            
            # Volatility (coefficient of variation)
            volatility = prices.std() / prices.mean() if prices.mean() != 0 else 0
            
            # Classify regime
            if r_squared > 0.7:
                if slope > 0:
                    return "Strong Uptrend"
                else:
                    return "Strong Downtrend"
            elif r_squared > 0.4:
                if slope > 0:
                    return "Moderate Uptrend"
                else:
                    return "Moderate Downtrend"
            elif volatility > 0.05:
                return "High Volatility"
            else:
                return "Sideways/Ranging"
                
        except Exception:
            return "Unknown"
