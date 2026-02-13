"""
Intraday Trading Session Scheduler for PSX KSE-100
Focused scheduler for intraday trading sessions with detailed session management

Schedule:
- 9:00 AM  - Full Day & Next Day Charts Reset + Activate Next Day
- 9:45 AM  - Morning Session Prediction Generate
- 10:30 AM - Full Day Prediction Generate
- 11:00 AM - Afternoon Session Prediction Generate
- 3:00 PM  - Next Day Prediction Generate (PENDING)
- 3:30 PM  - Morning & Afternoon Sessions Hidden in intraday trading session

Version: 1.0.0 - 2026-02-12
"""

import streamlit as st
import pandas as pd
import numpy as np
import pytz
from datetime import datetime, timedelta
from typing import Dict, Optional, Callable, List
from enum import Enum
import plotly.graph_objects as go


class IntradaySession(Enum):
    """Intraday trading session states"""
    PRE_MARKET = "pre_market"
    CHARTS_RESET = "charts_reset"
    MORNING_SESSION = "morning_session"
    FULL_DAY = "full_day"
    AFTERNOON_SESSION = "afternoon_session"
    TRADING_HOURS = "trading_hours"
    NEXT_DAY_PENDING = "next_day_pending"
    SESSIONS_HIDDEN = "sessions_hidden"
    POST_MARKET = "post_market"


class IntradayScheduler:
    """Intraday Trading Session Scheduler"""
    
    TRADING_SCHEDULE = {
        (9, 0): {"action": "charts_reset", "session": IntradaySession.CHARTS_RESET, "description": "Charts Reset + Activate Next Day"},
        (9, 45): {"action": "morning_session_generate", "session": IntradaySession.MORNING_SESSION, "description": "Morning Session Prediction"},
        (10, 30): {"action": "full_day_generate", "session": IntradaySession.FULL_DAY, "description": "Full Day Prediction"},
        (11, 0): {"action": "afternoon_session_generate", "session": IntradaySession.AFTERNOON_SESSION, "description": "Afternoon Session Prediction"},
        (15, 0): {"action": "next_day_generate_pending", "session": IntradaySession.NEXT_DAY_PENDING, "description": "Next Day Pending"},
        (15, 30): {"action": "sessions_hide", "session": IntradaySession.SESSIONS_HIDDEN, "description": "Sessions Hide"}
    }
    
    def __init__(self):
        self.pakistan_tz = pytz.timezone('Asia/Karachi')
        self.current_session = IntradaySession.PRE_MARKET
        self.last_action_time = None
        self._init_session_state()
    
    def _init_session_state(self):
        if 'intraday_scheduler_initialized' not in st.session_state:
            st.session_state.intraday_scheduler_initialized = True
            st.session_state.current_intraday_session = IntradaySession.PRE_MARKET.value
            st.session_state.charts_reset_done = False
            st.session_state.morning_session_generated = False
            st.session_state.full_day_generated = False
            st.session_state.afternoon_session_generated = False
            st.session_state.next_day_pending = False
            st.session_state.sessions_hidden = False
            st.session_state.intraday_predictions = {'morning_session': None, 'full_day': None, 'afternoon_session': None, 'next_day': None}
            st.session_state.last_reset_time = None
            st.session_state.session_start_time = None
            st.session_state.market_open = False
            st.session_state.market_close = False
    
    def get_pakistan_time(self) -> datetime:
        return datetime.now(self.pakistan_tz)
    
    def get_current_hour_minute(self) -> tuple:
        now = self.get_pakistan_time()
        return (now.hour, now.minute)
    
    def get_current_session(self) -> IntradaySession:
        hour, minute = self.get_current_hour_minute()
        if (hour, minute) in self.TRADING_SCHEDULE:
            return self.TRADING_SCHEDULE[(hour, minute)]["session"]
        if hour < 9:
            return IntradaySession.PRE_MARKET
        elif hour == 9 and minute < 45:
            return IntradaySession.PRE_MARKET
        elif hour == 9 and minute >= 45:
            return IntradaySession.MORNING_SESSION
        elif hour == 10 and minute < 30:
            return IntradaySession.MORNING_SESSION
        elif hour == 10 and minute >= 30:
            return IntradaySession.FULL_DAY
        elif hour == 11 and minute < 30:
            return IntradaySession.FULL_DAY
        elif hour == 11 and minute >= 30:
            return IntradaySession.AFTERNOON_SESSION
        elif hour < 15:
            return IntradaySession.TRADING_HOURS
        elif hour == 15 and minute < 30:
            return IntradaySession.NEXT_DAY_PENDING
        elif hour >= 15 and minute >= 30:
            return IntradaySession.SESSIONS_HIDDEN
        else:
            return IntradaySession.POST_MARKET
    
    def should_execute_action(self, hour: int, minute: int) -> bool:
        current_hour, current_minute = self.get_current_hour_minute()
        if current_hour == hour and current_minute == minute:
            if self.last_action_time:
                if self.last_action_time.date() == self.get_pakistan_time().date():
                    if self.last_action_time.hour == hour and self.last_action_time.minute == minute:
                        return False
            return True
        return False
    
    def get_scheduled_actions_for_now(self) -> list:
        hour, minute = self.get_current_hour_minute()
        actions = []
        action_key = (hour, minute)
        if action_key in self.TRADING_SCHEDULE:
            action_info = self.TRADING_SCHEDULE[action_key]
            actions.append({'hour': hour, 'minute': minute, 'action': action_info['action'], 'description': action_info['description'], 'session': action_info['session']})
        return actions
    
    def execute_scheduled_actions(self, forecaster=None, current_price=None) -> dict:
        executed = {}
        actions = self.get_scheduled_actions_for_now()
        for action_info in actions:
            action = action_info['action']
            hour = action_info['hour']
            minute = action_info['minute']
            if self.should_execute_action(hour, minute):
                try:
                    result = self._execute_action(action, forecaster, current_price)
                    executed[action] = {'success': True, 'result': result, 'time': f"{hour:02d}:{minute:02d}", 'description': action_info['description']}
                    self.last_action_time = self.get_pakistan_time()
                    self.current_session = action_info['session']
                    st.session_state.current_intraday_session = action_info['session'].value
                except Exception as e:
                    executed[action] = {'success': False, 'error': str(e), 'time': f"{hour:02d}:{minute:02d}", 'description': action_info['description']}
        return executed
    
    def _execute_action(self, action: str, forecaster=None, current_price=None) -> dict:
        now = self.get_pakistan_time()
        if action == "charts_reset":
            st.session_state.charts_reset_done = True
            st.session_state.morning_session_generated = False
            st.session_state.full_day_generated = False
            st.session_state.afternoon_session_generated = False
            st.session_state.next_day_pending = False
            st.session_state.sessions_hidden = False
            st.session_state.last_reset_time = now
            st.session_state.intraday_predictions = {'morning_session': None, 'full_day': None, 'afternoon_session': None, 'next_day': None}
            return {'status': 'success', 'message': 'Charts reset at 9:00 AM'}
        elif action == "morning_session_generate":
            if forecaster and current_price:
                try:
                    morning_df = forecaster.generate_morning_session_forecast_daily(current_price, "KSE-100")
                    st.session_state.intraday_predictions['morning_session'] = morning_df
                    st.session_state.morning_session_generated = True
                    return {'status': 'success', 'message': 'Morning session prediction generated at 9:45 AM', 'predictions_count': len(morning_df) if morning_df is not None else 0}
                except Exception as e:
                    return {'status': 'error', 'message': str(e)}
            return {'status': 'skipped', 'message': 'Forecaster not available'}
        elif action == "full_day_generate":
            if forecaster and current_price:
                try:
                    full_day_df = forecaster.generate_full_day_forecast_daily(current_price, "KSE-100")
                    st.session_state.intraday_predictions['full_day'] = full_day_df
                    st.session_state.full_day_generated = True
                    return {'status': 'success', 'message': 'Full day prediction generated at 10:30 AM', 'predictions_count': len(full_day_df) if full_day_df is not None else 0}
                except Exception as e:
                    return {'status': 'error', 'message': str(e)}
            return {'status': 'skipped', 'message': 'Forecaster not available'}
        elif action == "afternoon_session_generate":
            if forecaster and current_price:
                try:
                    afternoon_df = forecaster.generate_afternoon_session_forecast_daily(current_price, "KSE-100")
                    st.session_state.intraday_predictions['afternoon_session'] = afternoon_df
                    st.session_state.afternoon_session_generated = True
                    return {'status': 'success', 'message': 'Afternoon session prediction generated at 11:00 AM', 'predictions_count': len(afternoon_df) if afternoon_df is not None else 0}
                except Exception as e:
                    return {'status': 'error', 'message': str(e)}
            return {'status': 'skipped', 'message': 'Forecaster not available'}
        elif action == "next_day_generate_pending":
            st.session_state.next_day_pending = True
            return {'status': 'success', 'message': 'Next day pending at 3:00 PM'}
        elif action == "sessions_hide":
            st.session_state.sessions_hidden = True
            return {'status': 'success', 'message': 'Sessions hidden at 3:30 PM'}
        return {'status': 'unknown', 'message': f'Unknown action: {action}'}
    
    def get_session_status(self) -> dict:
        # Ensure session state is initialized
        self._init_session_state()
        
        now = self.get_pakistan_time()
        current_time = now.strftime('%H:%M:%S')
        current_session = self.get_current_session()
        
        # Safely access session state with fallback values
        predictions = st.session_state.get('intraday_predictions', {'morning_session': None, 'full_day': None, 'afternoon_session': None, 'next_day': None})
        
        return {
            'current_time': current_time,
            'current_session': current_session.value,
            'session_display': current_session.name.replace('_', ' ').title(),
            'timezone': 'Asia/Karachi (UTC+5)',
            'predictions': predictions,
            'actions_status': {
                'charts_reset': st.session_state.get('charts_reset_done', False),
                'morning_session': st.session_state.get('morning_session_generated', False),
                'full_day': st.session_state.get('full_day_generated', False),
                'afternoon_session': st.session_state.get('afternoon_session_generated', False),
                'next_day_pending': st.session_state.get('next_day_pending', False),
                'sessions_hidden': st.session_state.get('sessions_hidden', False)
            }
        }
    
    def should_show_morning_session(self) -> bool:
        self._init_session_state()
        return st.session_state.get('morning_session_generated', False) and not st.session_state.get('sessions_hidden', False)
    
    def should_show_full_day(self) -> bool:
        self._init_session_state()
        return st.session_state.get('full_day_generated', False)
    
    def should_show_afternoon_session(self) -> bool:
        self._init_session_state()
        return st.session_state.get('afternoon_session_generated', False) and not st.session_state.get('sessions_hidden', False)
    
    def should_show_next_day(self) -> bool:
        self._init_session_state()
        return st.session_state.get('sessions_hidden', False)
    
    def get_prediction(self, prediction_type: str) -> Optional[pd.DataFrame]:
        self._init_session_state()
        predictions = st.session_state.get('intraday_predictions', {'morning_session': None, 'full_day': None, 'afternoon_session': None, 'next_day': None})
        return predictions.get(prediction_type)
    
    def display_session_status(self):
        status = self.get_session_status()
        session_colors = {IntradaySession.PRE_MARKET: '#2196f3', IntradaySession.CHARTS_RESET: '#9c27b0', IntradaySession.MORNING_SESSION: '#4caf50', IntradaySession.FULL_DAY: '#ff9800', IntradaySession.AFTERNOON_SESSION: '#e91e63', IntradaySession.TRADING_HOURS: '#00bcd4', IntradaySession.NEXT_DAY_PENDING: '#f44336', IntradaySession.SESSIONS_HIDDEN: '#673ab7', IntradaySession.POST_MARKET: '#607d8b'}
        color = session_colors.get(self.get_current_session(), '#607d8b')
        st.markdown(f"""<div style='background: linear-gradient(135deg, {color} 0%, #333 100%); padding: 20px; border-radius: 10px; margin: 10px 0;'><h2 style='color: white; margin: 0;'>Intraday Trading Scheduler</h2><p style='color: #e8eaf6; margin: 10px 0 0 0;'>Current Session: {status['session_display']}<br>Current Time: {status['current_time']} PKT</p></div>""", unsafe_allow_html=True)


_intraday_scheduler_instance = None

def get_intraday_scheduler() -> IntradayScheduler:
    global _intraday_scheduler_instance
    if _intraday_scheduler_instance is None:
        _intraday_scheduler_instance = IntradayScheduler()
    return _intraday_scheduler_instance

def check_intraday_scheduled_actions(forecaster=None, current_price=None) -> dict:
    scheduler = get_intraday_scheduler()
    return scheduler.execute_scheduled_actions(forecaster, current_price)

def display_intraday_session_status():
    scheduler = get_intraday_scheduler()
    scheduler.display_session_status()

def get_intraday_session_info() -> dict:
    scheduler = get_intraday_scheduler()
    return scheduler.get_session_status()

def show_intraday_predictions():
    st.header("Intraday Trading Session Predictions")
    scheduler = get_intraday_scheduler()
    status = scheduler.get_session_status()
    scheduler.display_session_status()
    predictions = status.get('predictions', {'morning_session': None, 'full_day': None, 'afternoon_session': None, 'next_day': None})
    
    if scheduler.should_show_morning_session() and predictions['morning_session'] is not None:
        st.subheader("Morning Session Prediction (9:45 AM)")
        st.dataframe(predictions['morning_session'])
        morning_df = predictions['morning_session']
        fig = go.Figure()
        fig.add_trace(go.Scatter(x=morning_df['time'], y=morning_df['predicted_price'], mode='lines+markers', name='Morning', line=dict(color='green', width=3)))
        fig.update_layout(title="Morning Session Prediction", height=400)
        st.plotly_chart(fig, use_container_width=True)
    
    if scheduler.should_show_full_day() and predictions['full_day'] is not None:
        st.subheader("Full Day Prediction (10:30 AM)")
        st.dataframe(predictions['full_day'])
        full_day_df = predictions['full_day']
        fig = go.Figure()
        fig.add_trace(go.Scatter(x=full_day_df['time'], y=full_day_df['predicted_price'], mode='lines+markers', name='Full Day', line=dict(color='blue', width=3)))
        fig.update_layout(title="Full Day Prediction", height=400)
        st.plotly_chart(fig, use_container_width=True)
    
    if scheduler.should_show_afternoon_session() and predictions['afternoon_session'] is not None:
        st.subheader("Afternoon Session Prediction (11:00 AM)")
        st.dataframe(predictions['afternoon_session'])
        afternoon_df = predictions['afternoon_session']
        fig = go.Figure()
        fig.add_trace(go.Scatter(x=afternoon_df['time'], y=afternoon_df['predicted_price'], mode='lines+markers', name='Afternoon', line=dict(color='orange', width=3)))
        fig.update_layout(title="Afternoon Session Prediction", height=400)
        st.plotly_chart(fig, use_container_width=True)
    
    if scheduler.should_show_next_day():
        st.subheader("Next Day Prediction")
        st.success("Next day prediction is now available!")
    
    st.markdown("---")
    with st.expander("Manual Controls (Testing)", expanded=False):
        col1, col2 = st.columns(2)
        with col1:
            if st.button("Reset Charts (9:00 AM)"):
                scheduler._execute_action("charts_reset")
                st.rerun()
            if st.button("Morning Session (9:45 AM)"):
                scheduler._execute_action("morning_session_generate", None, 10000)
                st.rerun()
            if st.button("Full Day (10:30 AM)"):
                scheduler._execute_action("full_day_generate", None, 10000)
                st.rerun()
        with col2:
            if st.button("Afternoon (11:00 AM)"):
                scheduler._execute_action("afternoon_session_generate", None, 10000)
                st.rerun()
            if st.button("Next Day Pending (3:00 PM)"):
                scheduler._execute_action("next_day_generate_pending")
                st.rerun()
            if st.button("Hide Sessions (3:30 PM)"):
                scheduler._execute_action("sessions_hide")
                st.rerun()
