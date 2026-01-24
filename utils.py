import pandas as pd
import numpy as np
from datetime import datetime
import io

def format_currency(amount, currency_symbol="PKR"):
    """
    Format currency values with proper thousand separators
    
    Args:
        amount (float): Currency amount
        currency_symbol (str): Currency symbol
        
    Returns:
        str: Formatted currency string
    """
    if pd.isna(amount) or amount is None:
        return f"{currency_symbol} 0.00"
    
    try:
        return f"{currency_symbol} {amount:,.2f}"
    except (ValueError, TypeError):
        return f"{currency_symbol} 0.00"

def format_percentage(value, decimal_places=2):
    """
    Format percentage values
    
    Args:
        value (float): Percentage value
        decimal_places (int): Number of decimal places
        
    Returns:
        str: Formatted percentage string
    """
    if pd.isna(value) or value is None:
        return "0.00%"
    
    try:
        return f"{value:.{decimal_places}f}%"
    except (ValueError, TypeError):
        return "0.00%"

def format_volume(volume):
    """
    Format volume values with appropriate units
    
    Args:
        volume (int/float): Volume value
        
    Returns:
        str: Formatted volume string
    """
    if pd.isna(volume) or volume is None:
        return "0"
    
    try:
        volume = float(volume)
        if volume >= 1_000_000_000:
            return f"{volume/1_000_000_000:.1f}B"
        elif volume >= 1_000_000:
            return f"{volume/1_000_000:.1f}M"
        elif volume >= 1_000:
            return f"{volume/1_000:.1f}K"
        else:
            return f"{volume:.0f}"
    except (ValueError, TypeError):
        return "0"

def calculate_technical_indicators(data):
    """
    Calculate common technical indicators
    
    Args:
        data (pd.DataFrame): Stock data with OHLC values
        
    Returns:
        pd.DataFrame: Data with technical indicators added
    """
    if data is None or data.empty:
        return data
    
    try:
        df = data.copy()
        
        # Simple Moving Averages
        df['SMA_5'] = df['close'].rolling(window=5).mean()
        df['SMA_10'] = df['close'].rolling(window=10).mean()
        df['SMA_20'] = df['close'].rolling(window=20).mean()
        
        # Exponential Moving Averages
        df['EMA_5'] = df['close'].ewm(span=5).mean()
        df['EMA_10'] = df['close'].ewm(span=10).mean()
        
        # RSI (Relative Strength Index)
        delta = df['close'].diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
        rs = gain / loss
        df['RSI'] = 100 - (100 / (1 + rs))
        
        # MACD (Moving Average Convergence Divergence)
        ema12 = df['close'].ewm(span=12).mean()
        ema26 = df['close'].ewm(span=26).mean()
        df['MACD'] = ema12 - ema26
        df['MACD_Signal'] = df['MACD'].ewm(span=9).mean()
        df['MACD_Histogram'] = df['MACD'] - df['MACD_Signal']
        
        # Bollinger Bands
        bb_period = 20
        bb_std = 2
        bb_ma = df['close'].rolling(window=bb_period).mean()
        bb_std_dev = df['close'].rolling(window=bb_period).std()
        df['BB_Upper'] = bb_ma + (bb_std_dev * bb_std)
        df['BB_Lower'] = bb_ma - (bb_std_dev * bb_std)
        df['BB_Middle'] = bb_ma
        
        return df
        
    except Exception as e:
        return data

def calculate_portfolio_metrics(returns):
    """
    Calculate portfolio performance metrics
    
    Args:
        returns (pd.Series): Portfolio returns
        
    Returns:
        dict: Portfolio metrics
    """
    if returns is None or returns.empty:
        return {}
    
    try:
        metrics = {}
        
        # Basic metrics
        metrics['Total Return'] = (returns + 1).prod() - 1
        metrics['Annualized Return'] = (returns + 1).prod() ** (252 / len(returns)) - 1
        metrics['Volatility'] = returns.std() * np.sqrt(252)
        
        # Risk metrics
        metrics['Sharpe Ratio'] = metrics['Annualized Return'] / metrics['Volatility'] if metrics['Volatility'] != 0 else 0
        metrics['Max Drawdown'] = ((returns + 1).cumprod() / (returns + 1).cumprod().expanding().max() - 1).min()
        
        # Downside metrics
        negative_returns = returns[returns < 0]
        if not negative_returns.empty:
            metrics['Downside Deviation'] = negative_returns.std() * np.sqrt(252)
            metrics['Sortino Ratio'] = metrics['Annualized Return'] / metrics['Downside Deviation'] if metrics['Downside Deviation'] != 0 else 0
        else:
            metrics['Downside Deviation'] = 0
            metrics['Sortino Ratio'] = float('inf') if metrics['Annualized Return'] > 0 else 0
        
        return metrics
        
    except Exception:
        return {}

def export_to_csv(data, filename_prefix="stock_data"):
    """
    Export data to CSV format
    
    Args:
        data (pd.DataFrame): Data to export
        filename_prefix (str): Prefix for filename
        
    Returns:
        str: CSV string
    """
    if data is None or data.empty:
        return ""
    
    try:
        return data.to_csv(index=False)
    except Exception:
        return ""

def validate_data_quality(data):
    """
    Validate data quality and return quality metrics
    
    Args:
        data (pd.DataFrame): Stock data to validate
        
    Returns:
        dict: Data quality metrics
    """
    if data is None or data.empty:
        return {'status': 'failed', 'issues': ['No data available']}
    
    issues = []
    
    try:
        # Check for required columns
        required_columns = ['date', 'open', 'high', 'low', 'close', 'volume']
        missing_columns = [col for col in required_columns if col not in data.columns]
        if missing_columns:
            issues.append(f"Missing columns: {missing_columns}")
        
        # Check for null values
        null_counts = data.isnull().sum()
        if null_counts.sum() > 0:
            issues.append(f"Null values found: {null_counts.to_dict()}")
        
        # Check for negative prices
        price_columns = ['open', 'high', 'low', 'close']
        for col in price_columns:
            if col in data.columns and (data[col] <= 0).any():
                issues.append(f"Non-positive values in {col}")
        
        # Check price consistency (high >= low, etc.)
        if 'high' in data.columns and 'low' in data.columns:
            if (data['high'] < data['low']).any():
                issues.append("High prices lower than low prices")
        
        # Check for duplicate dates
        if 'date' in data.columns:
            if data['date'].duplicated().any():
                issues.append("Duplicate dates found")
        
        # Data completeness
        data_completeness = len(data) / 30 * 100  # Assuming 30 days is complete
        
        quality_metrics = {
            'status': 'passed' if not issues else 'warning',
            'issues': issues,
            'data_points': len(data),
            'completeness': min(data_completeness, 100),
            'null_percentage': (data.isnull().sum().sum() / (len(data) * len(data.columns))) * 100
        }
        
        return quality_metrics
        
    except Exception as e:
        return {'status': 'failed', 'issues': [f'Validation error: {str(e)}']}

def generate_market_summary(kse_data, companies_data):
    """
    Generate market summary statistics
    
    Args:
        kse_data (pd.DataFrame): KSE-100 index data
        companies_data (dict): Individual companies data
        
    Returns:
        dict: Market summary statistics
    """
    summary = {}
    
    try:
        # KSE-100 summary
        if kse_data is not None and not kse_data.empty:
            current_price = kse_data['close'].iloc[-1]
            start_price = kse_data['close'].iloc[0]
            
            summary['kse100'] = {
                'current_level': current_price,
                'period_change': current_price - start_price,
                'period_change_pct': ((current_price - start_price) / start_price) * 100,
                'high_52w': kse_data['high'].max(),
                'low_52w': kse_data['low'].min(),
                'avg_volume': kse_data['volume'].mean()
            }
        
        # Companies summary
        if companies_data:
            gainers = []
            losers = []
            
            for company, data in companies_data.items():
                if data is not None and not data.empty and len(data) > 1:
                    current = data['close'].iloc[-1]
                    previous = data['close'].iloc[-2]
                    change_pct = ((current - previous) / previous) * 100
                    
                    if change_pct > 0:
                        gainers.append((company, change_pct))
                    elif change_pct < 0:
                        losers.append((company, change_pct))
            
            # Sort by change percentage
            gainers.sort(key=lambda x: x[1], reverse=True)
            losers.sort(key=lambda x: x[1])
            
            summary['market_movers'] = {
                'top_gainers': gainers[:5],
                'top_losers': losers[:5],
                'total_companies': len(companies_data)
            }
        
        return summary
        
    except Exception:
        return {}

def format_market_status():
    """
    Determine and format current market status with accurate PSX timing
    
    Returns:
        dict: Market status information
    """
    import pytz
    from datetime import datetime
    
    # Pakistan timezone (PKT)
    pkt = pytz.timezone('Asia/Karachi')
    now = datetime.now(pkt)
    
    # Get current Pakistan time components
    current_hour = now.hour
    current_minute = now.minute
    current_time_minutes = current_hour * 60 + current_minute
    
    # PSX trading hours: 9:30 AM to 3:00 PM (Pakistan time)
    market_open_minutes = 9 * 60 + 30  # 9:30 AM = 570 minutes
    market_close_minutes = 15 * 60     # 3:00 PM = 900 minutes
    
    is_weekend = now.weekday() >= 5  # Saturday = 5, Sunday = 6
    
    # Debug info for verification
    debug_info = f"Current PKT: {now.strftime('%Y-%m-%d %H:%M:%S %Z')}"
    
    if is_weekend:
        status = "🔴 Closed (Weekend)"
        next_open = "Monday 9:30 AM PKT"
    elif current_time_minutes < market_open_minutes:
        status = "⏰ Pre-Market"
        next_open = "Today 9:30 AM PKT"
    elif market_open_minutes <= current_time_minutes <= market_close_minutes:
        status = "🟢 MARKET OPEN"
        next_open = f"Market closes at 3:00 PM PKT"
    else:
        status = "🔴 Closed (After Hours)"
        if now.weekday() == 4:  # Friday
            next_open = "Monday 9:30 AM PKT"
        else:
            next_open = "Tomorrow 9:30 AM PKT"
    
    return {
        'status': status,
        'next_session': next_open,
        'current_time': now.strftime("%H:%M:%S PKT"),
        'current_date': now.strftime("%A, %B %d, %Y"),
        'debug_info': debug_info,
        'is_market_open': market_open_minutes <= current_time_minutes <= market_close_minutes and not is_weekend
    }
