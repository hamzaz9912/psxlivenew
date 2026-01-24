"""
Disable yfinance module to prevent console noise
"""
import sys

# Replace yfinance module with a dummy that doesn't make API calls
class DummyYfinance:
    class Ticker:
        def __init__(self, symbol):
            pass
        
        def history(self, period="1d", interval="5m"):
            # Return empty DataFrame to simulate no data
            import pandas as pd
            return pd.DataFrame()

# Override yfinance imports
sys.modules['yfinance'] = DummyYfinance()