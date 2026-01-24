"""
Universal File Upload Predictor Module
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

class UniversalPredictor:
    """Universal predictor for any uploaded financial data"""
    
    def __init__(self):
        self.supported_formats = ['.csv', '.xlsx', '.xls']
        self.common_price_columns = [
            'close', 'Close', 'CLOSE', 'price', 'Price', 'PRICE',
            'last', 'Last', 'LAST', 'value', 'Value', 'VALUE'
        ]
        self.common_date_columns = [
            'date', 'Date', 'DATE', 'time', 'Time', 'TIME',
            'datetime', 'DateTime', 'DATETIME', 'timestamp', 'Timestamp'
        ]
        
    def process_uploaded_file(self, uploaded_file, brand_name="Unknown"):
        """Process uploaded file and extract financial data"""
        try:
            file_extension = uploaded_file.name.split('.')[-1].lower()
            
            # Reset file pointer to beginning
            uploaded_file.seek(0)
            
            if file_extension == 'csv':
                # Try different CSV reading approaches
                error_messages = []
                df = None
                
                # Method 1: Default CSV reading
                try:
                    uploaded_file.seek(0)
                    df = pd.read_csv(uploaded_file)
                    if df.empty or len(df.columns) == 0:
                        raise ValueError("Empty dataframe or no columns")
                except Exception as e1:
                    error_messages.append(f"Default CSV read: {str(e1)}")
                
                # Method 2: Try with semicolon delimiter
                if df is None:
                    try:
                        uploaded_file.seek(0)
                        df = pd.read_csv(uploaded_file, delimiter=';')
                        if df.empty or len(df.columns) == 0:
                            raise ValueError("Empty dataframe or no columns")
                    except Exception as e2:
                        error_messages.append(f"Semicolon delimiter: {str(e2)}")
                
                # Method 3: Try with tab delimiter
                if df is None:
                    try:
                        uploaded_file.seek(0)
                        df = pd.read_csv(uploaded_file, delimiter='\t')
                        if df.empty or len(df.columns) == 0:
                            raise ValueError("Empty dataframe or no columns")
                    except Exception as e3:
                        error_messages.append(f"Tab delimiter: {str(e3)}")
                
                # Method 4: Try with different encoding
                if df is None:
                    try:
                        uploaded_file.seek(0)
                        df = pd.read_csv(uploaded_file, encoding='latin-1')
                        if df.empty or len(df.columns) == 0:
                            raise ValueError("Empty dataframe or no columns")
                    except Exception as e4:
                        error_messages.append(f"Latin-1 encoding: {str(e4)}")
                
                # Method 5: Try with no header
                if df is None:
                    try:
                        uploaded_file.seek(0)
                        df = pd.read_csv(uploaded_file, header=None)
                        if df.empty or len(df.columns) == 0:
                            raise ValueError("Empty dataframe or no columns")
                        # Add generic column names
                        df.columns = [f'Column_{i+1}' for i in range(len(df.columns))]
                    except Exception as e5:
                        error_messages.append(f"No header: {str(e5)}")
                
                # Method 6: Try to read raw content and detect format
                if df is None:
                    try:
                        uploaded_file.seek(0)
                        content = uploaded_file.read().decode('utf-8')
                        lines = content.strip().split('\n')
                        if len(lines) > 0:
                            # Try to detect delimiter
                            first_line = lines[0]
                            if ',' in first_line:
                                delimiter = ','
                            elif ';' in first_line:
                                delimiter = ';'
                            elif '\t' in first_line:
                                delimiter = '\t'
                            else:
                                delimiter = ','
                            
                            # Create StringIO object
                            from io import StringIO
                            string_data = StringIO(content)
                            df = pd.read_csv(string_data, delimiter=delimiter)
                            
                            if df.empty or len(df.columns) == 0:
                                raise ValueError("Empty dataframe or no columns")
                    except Exception as e6:
                        error_messages.append(f"Raw content parsing: {str(e6)}")
                
                if df is None:
                    # Final attempt with comprehensive debugging
                    try:
                        uploaded_file.seek(0)
                        raw_bytes = uploaded_file.read()
                        
                        # Try multiple encodings
                        for encoding in ['utf-8', 'latin-1', 'iso-8859-1', 'cp1252', 'ascii']:
                            try:
                                content = raw_bytes.decode(encoding)
                                
                                # Check if content has any data
                                if not content.strip():
                                    continue
                                
                                # Try to create a dataframe manually
                                lines = content.strip().split('\n')
                                if len(lines) < 2:
                                    continue
                                
                                # Detect delimiter
                                first_line = lines[0]
                                delimiters = [',', ';', '\t', '|', ' ']
                                best_delimiter = ','
                                max_splits = 0
                                
                                for delim in delimiters:
                                    splits = len(first_line.split(delim))
                                    if splits > max_splits:
                                        max_splits = splits
                                        best_delimiter = delim
                                
                                # Create dataframe manually
                                data = []
                                headers = lines[0].split(best_delimiter)
                                
                                for line in lines[1:]:
                                    if line.strip():
                                        row = line.split(best_delimiter)
                                        if len(row) == len(headers):
                                            data.append(row)
                                
                                if data:
                                    df = pd.DataFrame(data, columns=headers)
                                    break
                                    
                            except Exception:
                                continue
                        
                        # If df is found, we can continue processing
                            
                    except Exception as final_e:
                        error_messages.append(f"Final manual parsing: {str(final_e)}")
                
                if df is None:
                    return {
                        'error': f'Unable to read CSV file. Tried multiple methods:\n' + '\n'.join(error_messages),
                        'debug_info': {
                            'file_size': uploaded_file.size,
                            'attempted_methods': len(error_messages),
                            'methods_tried': error_messages
                        }
                    }
                            
            elif file_extension in ['xlsx', 'xls']:
                # Read Excel file
                try:
                    df = pd.read_excel(uploaded_file)
                    if df.empty or len(df.columns) == 0:
                        return {'error': 'Excel file is empty or has no columns'}
                except Exception as e:
                    return {'error': f'Unable to read Excel file: {str(e)}'}
            else:
                return {'error': f'Unsupported file format: {file_extension}. Please upload CSV or Excel files.'}
            
            # Check if dataframe is empty
            if df.empty:
                return {'error': 'The uploaded file appears to be empty or has no readable data.'}
            
            # Check if dataframe has any columns
            if len(df.columns) == 0:
                return {'error': 'The uploaded file has no columns. Please check the file format.'}
            
            # Remove completely empty rows and columns
            df = df.dropna(how='all').dropna(axis=1, how='all')
            
            if df.empty:
                return {'error': 'After removing empty rows/columns, no data remains. Please check your file.'}
            
            # Analyze the data structure
            analysis = self._analyze_data_structure(df, brand_name)
            
            return analysis
            
        except Exception as e:
            return {'error': f'Error processing file: {str(e)}. Please ensure the file is not corrupted and contains valid data.'}
    
    def _analyze_data_structure(self, df, brand_name):
        """Analyze the structure of uploaded data"""
        try:
            # Clean column names - remove extra spaces and special characters
            df.columns = df.columns.str.strip()
            
            # Basic info
            analysis = {
                'brand_name': brand_name,
                'total_rows': len(df),
                'total_columns': len(df.columns),
                'columns': list(df.columns),
                'data_types': {str(k): str(v) for k, v in df.dtypes.to_dict().items()},
                'has_price_data': False,
                'has_date_data': False,
                'price_column': None,
                'date_column': None,
                'data_range': None,
                'sample_data': []
            }
            
            # Get sample data safely
            try:
                sample_df = df.head(3)
                # Convert to safe format for display
                analysis['sample_data'] = []
                for idx, row in sample_df.iterrows():
                    row_dict = {}
                    for col in df.columns:
                        try:
                            val = row[col]
                            if pd.isna(val):
                                row_dict[col] = "N/A"
                            else:
                                row_dict[col] = str(val)
                        except:
                            row_dict[col] = "Error"
                    analysis['sample_data'].append(row_dict)
            except Exception as e:
                analysis['sample_data'] = [{'Error': f'Cannot display sample data: {str(e)}'}]
            
            # Identify price column with more flexible matching
            for col in df.columns:
                col_lower = str(col).lower()
                if any(price_col.lower() in col_lower for price_col in self.common_price_columns):
                    analysis['price_column'] = col
                    analysis['has_price_data'] = True
                    break
            
            # If no price column found, try to find numeric columns
            if not analysis['price_column']:
                numeric_cols = df.select_dtypes(include=[np.number]).columns
                if len(numeric_cols) > 0:
                    # Use the first numeric column as price column
                    analysis['price_column'] = numeric_cols[0]
                    analysis['has_price_data'] = True
            
            # Identify date column with more flexible matching
            for col in df.columns:
                col_lower = str(col).lower()
                if any(date_col.lower() in col_lower for date_col in self.common_date_columns):
                    analysis['date_column'] = col
                    analysis['has_date_data'] = True
                    break
            
            # If no date column found, try to find datetime columns
            if not analysis['date_column']:
                for col in df.columns:
                    try:
                        sample_vals = df[col].dropna().head(5)
                        if len(sample_vals) > 0:
                            # Try to parse as datetime
                            pd.to_datetime(sample_vals, errors='raise')
                            analysis['date_column'] = col
                            analysis['has_date_data'] = True
                            break
                    except:
                        continue
            
            # If price column found, get price statistics
            if analysis['price_column']:
                try:
                    price_data = pd.to_numeric(df[analysis['price_column']], errors='coerce')
                    price_data = price_data.dropna()
                    
                    if len(price_data) > 0:
                        analysis['price_stats'] = {
                            'min': float(price_data.min()),
                            'max': float(price_data.max()),
                            'mean': float(price_data.mean()),
                            'current': float(price_data.iloc[-1]),
                            'previous': float(price_data.iloc[-2]) if len(price_data) > 1 else None,
                            'change': float(price_data.iloc[-1] - price_data.iloc[-2]) if len(price_data) > 1 else 0
                        }
                except Exception as e:
                    analysis['price_stats'] = {'error': f'Cannot analyze price data: {str(e)}'}
            
            # If date column found, get date range
            if analysis['date_column']:
                try:
                    date_data = pd.to_datetime(df[analysis['date_column']], errors='coerce')
                    date_data = date_data.dropna()
                    
                    if len(date_data) > 0:
                        analysis['data_range'] = {
                            'start': date_data.min().strftime('%Y-%m-%d'),
                            'end': date_data.max().strftime('%Y-%m-%d'),
                            'total_days': (date_data.max() - date_data.min()).days
                        }
                except Exception as e:
                    analysis['data_range'] = {'error': f'Cannot analyze date data: {str(e)}'}
            
            return analysis
            
        except Exception as e:
            return {'error': f'Error analyzing data: {str(e)}'}
    
    def generate_predictions(self, df, brand_name, price_column, date_column=None):
        """Generate predictions based on uploaded data"""
        try:
            # Prepare data
            price_data = pd.to_numeric(df[price_column], errors='coerce').dropna()
            
            if len(price_data) < 5:
                return {'error': 'Insufficient data for prediction (need at least 5 data points)'}
            
            # Calculate trends and patterns
            returns = price_data.pct_change().dropna()
            volatility = returns.std()
            trend = returns.mean()
            
            current_price = price_data.iloc[-1]
            
            # Generate different types of predictions
            predictions = {
                'brand_name': brand_name,
                'current_price': current_price,
                'data_points': len(price_data),
                'analysis_date': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                'volatility': volatility,
                'trend': trend,
                'predictions': {}
            }
            
            # Short-term prediction (next 1-7 days)
            predictions['predictions']['short_term'] = self._generate_short_term_prediction(
                current_price, trend, volatility, brand_name
            )
            
            # Medium-term prediction (next 1-4 weeks)
            predictions['predictions']['medium_term'] = self._generate_medium_term_prediction(
                current_price, trend, volatility, brand_name
            )
            
            # Long-term prediction (next 1-3 months)
            predictions['predictions']['long_term'] = self._generate_long_term_prediction(
                current_price, trend, volatility, brand_name
            )
            
            # Technical analysis
            predictions['technical_analysis'] = self._perform_technical_analysis(price_data)
            
            return predictions
            
        except Exception as e:
            return {'error': f'Error generating predictions: {str(e)}'}
    
    def _generate_short_term_prediction(self, current_price, trend, volatility, brand_name):
        """Generate short-term predictions (1-7 days)"""
        predictions = []
        
        for day in range(1, 8):
            # Apply trend and volatility
            random_factor = np.random.normal(0, volatility)
            trend_factor = trend * day
            
            predicted_price = current_price * (1 + trend_factor + random_factor)
            
            predictions.append({
                'day': day,
                'date': (datetime.now() + timedelta(days=day)).strftime('%Y-%m-%d'),
                'predicted_price': round(predicted_price, 4),
                'change': round(predicted_price - current_price, 4),
                'change_percent': round(((predicted_price - current_price) / current_price) * 100, 2),
                'confidence': max(0.6, 0.9 - (day * 0.05))  # Decreasing confidence over time
            })
        
        return predictions
    
    def _generate_medium_term_prediction(self, current_price, trend, volatility, brand_name):
        """Generate medium-term predictions (1-4 weeks)"""
        predictions = []
        
        for week in range(1, 5):
            # Medium-term trend adjustment
            trend_adjustment = trend * week * 7 * 0.8  # Slightly damped
            volatility_adjustment = np.random.normal(0, volatility * 0.7)
            
            predicted_price = current_price * (1 + trend_adjustment + volatility_adjustment)
            
            predictions.append({
                'week': week,
                'date': (datetime.now() + timedelta(weeks=week)).strftime('%Y-%m-%d'),
                'predicted_price': round(predicted_price, 4),
                'change': round(predicted_price - current_price, 4),
                'change_percent': round(((predicted_price - current_price) / current_price) * 100, 2),
                'confidence': max(0.4, 0.8 - (week * 0.1))
            })
        
        return predictions
    
    def _generate_long_term_prediction(self, current_price, trend, volatility, brand_name):
        """Generate long-term predictions (1-3 months)"""
        predictions = []
        
        for month in range(1, 4):
            # Long-term trend with mean reversion
            trend_adjustment = trend * month * 30 * 0.6  # More damped
            volatility_adjustment = np.random.normal(0, volatility * 0.5)
            
            predicted_price = current_price * (1 + trend_adjustment + volatility_adjustment)
            
            predictions.append({
                'month': month,
                'date': (datetime.now() + timedelta(days=month*30)).strftime('%Y-%m-%d'),
                'predicted_price': round(predicted_price, 4),
                'change': round(predicted_price - current_price, 4),
                'change_percent': round(((predicted_price - current_price) / current_price) * 100, 2),
                'confidence': max(0.3, 0.7 - (month * 0.15))
            })
        
        return predictions
    
    def _perform_technical_analysis(self, price_data):
        """Perform basic technical analysis"""
        try:
            # Moving averages
            ma_5 = price_data.rolling(window=5).mean().iloc[-1] if len(price_data) >= 5 else None
            ma_10 = price_data.rolling(window=10).mean().iloc[-1] if len(price_data) >= 10 else None
            ma_20 = price_data.rolling(window=20).mean().iloc[-1] if len(price_data) >= 20 else None
            
            # RSI (simplified)
            delta = price_data.diff()
            gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
            loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
            
            rs = gain / loss
            rsi = 100 - (100 / (1 + rs))
            current_rsi = rsi.iloc[-1] if len(rsi) > 0 else 50
            
            # Support and resistance levels
            support = price_data.rolling(window=20).min().iloc[-1] if len(price_data) >= 20 else price_data.min()
            resistance = price_data.rolling(window=20).max().iloc[-1] if len(price_data) >= 20 else price_data.max()
            
            return {
                'moving_averages': {
                    'ma_5': round(ma_5, 4) if ma_5 is not None else None,
                    'ma_10': round(ma_10, 4) if ma_10 is not None else None,
                    'ma_20': round(ma_20, 4) if ma_20 is not None else None
                },
                'rsi': round(current_rsi, 2),
                'support_level': round(support, 4),
                'resistance_level': round(resistance, 4),
                'trend_signal': 'bullish' if current_rsi < 30 else 'bearish' if current_rsi > 70 else 'neutral'
            }
            
        except Exception as e:
            return {'error': f'Technical analysis error: {str(e)}'}
    
    def create_prediction_chart(self, df, predictions, price_column, date_column=None):
        """Create interactive prediction chart"""
        try:
            # Prepare historical data
            price_data = pd.to_numeric(df[price_column], errors='coerce').dropna()
            
            if date_column:
                date_data = pd.to_datetime(df[date_column], errors='coerce')
                dates = date_data.dropna()
            else:
                dates = pd.date_range(start=datetime.now() - timedelta(days=len(price_data)), 
                                     periods=len(price_data), freq='D')
            
            # Create subplot
            fig = make_subplots(
                rows=2, cols=1,
                subplot_titles=('Price History & Predictions', 'Technical Indicators'),
                vertical_spacing=0.1,
                row_heights=[0.7, 0.3]
            )
            
            # Historical price data
            fig.add_trace(
                go.Scatter(
                    x=dates[:len(price_data)],
                    y=price_data,
                    mode='lines',
                    name='Historical Price',
                    line=dict(color='blue', width=2)
                ),
                row=1, col=1
            )
            
            # Short-term predictions
            if 'short_term' in predictions['predictions']:
                pred_dates = [datetime.strptime(pred['date'], '%Y-%m-%d') 
                             for pred in predictions['predictions']['short_term']]
                pred_prices = [pred['predicted_price'] 
                              for pred in predictions['predictions']['short_term']]
                
                fig.add_trace(
                    go.Scatter(
                        x=pred_dates,
                        y=pred_prices,
                        mode='lines+markers',
                        name='Short-term Prediction',
                        line=dict(color='red', width=2, dash='dash'),
                        marker=dict(size=6)
                    ),
                    row=1, col=1
                )
            
            # Add technical indicators
            if 'technical_analysis' in predictions:
                tech = predictions['technical_analysis']
                
                # Support and resistance lines
                fig.add_hline(
                    y=tech['support_level'],
                    line_dash="dot",
                    line_color="green",
                    annotation_text="Support",
                    row=1, col=1
                )
                
                fig.add_hline(
                    y=tech['resistance_level'],
                    line_dash="dot",
                    line_color="red",
                    annotation_text="Resistance",
                    row=1, col=1
                )
                
                # RSI indicator
                fig.add_trace(
                    go.Scatter(
                        x=[dates[-1]],
                        y=[tech['rsi']],
                        mode='markers',
                        name='RSI',
                        marker=dict(size=10, color='purple')
                    ),
                    row=2, col=1
                )
            
            # Update layout
            fig.update_layout(
                title=f"{predictions['brand_name']} - Price Analysis & Predictions",
                xaxis_title="Date",
                yaxis_title="Price",
                height=600,
                showlegend=True,
                hovermode='x unified'
            )
            
            return fig
            
        except Exception as e:
            print(f"Error creating prediction chart: {e}")
            return None

def get_universal_predictor():
    """Get universal predictor instance"""
    return UniversalPredictor()