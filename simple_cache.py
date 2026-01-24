"""
Simple in-memory cache system to replace database functionality
"""
import pandas as pd
from datetime import datetime, timedelta
from typing import Dict, Optional
import streamlit as st

class SimpleCache:
    """Simple in-memory cache for stock data"""
    
    def __init__(self):
        self.cache = {}
        self.cache_timestamps = {}
        self.cache_ttl = 300  # 5 minutes
    
    def is_cache_valid(self, key: str) -> bool:
        """Check if cache entry is still valid"""
        if key not in self.cache_timestamps:
            return False
        
        age = (datetime.now() - self.cache_timestamps[key]).total_seconds()
        return age < self.cache_ttl
    
    def get_stock_data(self, symbol: str, days: int = 30) -> Optional[pd.DataFrame]:
        """Get cached stock data"""
        cache_key = f"{symbol}_{days}"
        
        if cache_key in self.cache and self.is_cache_valid(cache_key):
            return self.cache[cache_key].copy()
        
        return None
    
    def store_stock_data(self, symbol: str, company_name: str, data_df: pd.DataFrame):
        """Store stock data in cache"""
        cache_key = f"{symbol}_30"  # Default to 30 days
        self.cache[cache_key] = data_df.copy()
        self.cache_timestamps[cache_key] = datetime.now()
    
    def clear_cache(self):
        """Clear all cached data"""
        self.cache.clear()
        self.cache_timestamps.clear()
    
    def get_cache_stats(self) -> Dict:
        """Get cache statistics"""
        total_entries = len(self.cache)
        valid_entries = sum(1 for key in self.cache.keys() if self.is_cache_valid(key))
        
        return {
            'total_entries': total_entries,
            'valid_entries': valid_entries,
            'expired_entries': total_entries - valid_entries
        }

def get_cache_manager():
    """Get or create cache manager instance"""
    if 'cache_manager' not in st.session_state:
        st.session_state.cache_manager = SimpleCache()
    return st.session_state.cache_manager