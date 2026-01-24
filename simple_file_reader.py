"""
Simple and robust file reader for universal file upload
"""
import pandas as pd
import io
# import chardet

def read_any_file(uploaded_file):
    """
    Read any CSV or Excel file with maximum compatibility
    Returns: (dataframe, error_message)
    """
    try:
        # Reset file pointer
        uploaded_file.seek(0)
        
        # Get file extension
        file_extension = uploaded_file.name.split('.')[-1].lower()
        
        if file_extension in ['xlsx', 'xls']:
            # Excel files
            try:
                df = pd.read_excel(uploaded_file)
                if df.empty:
                    return None, "Excel file is empty"
                return df, None
            except Exception as e:
                return None, f"Excel reading failed: {str(e)}"
        
        elif file_extension == 'csv':
            # CSV files - try multiple approaches
            uploaded_file.seek(0)
            raw_content = uploaded_file.read()
            
            # Detect encoding (fallback without chardet)
            detected_encoding = 'utf-8'  # Default fallback
            
            # Decode content
            try:
                text_content = raw_content.decode(detected_encoding)
            except:
                try:
                    text_content = raw_content.decode('utf-8')
                except:
                    try:
                        text_content = raw_content.decode('latin-1')
                    except:
                        return None, "Cannot decode file with any encoding"
            
            # Remove BOM if present
            if text_content.startswith('\ufeff'):
                text_content = text_content[1:]
            
            # Try different delimiters
            delimiters = [',', ';', '\t', '|']
            
            for delimiter in delimiters:
                try:
                    # Create StringIO from decoded content
                    string_io = io.StringIO(text_content)
                    df = pd.read_csv(string_io, delimiter=delimiter)
                    
                    # Check if dataframe is valid
                    if not df.empty and len(df.columns) > 0:
                        # Check if we have meaningful data (not just one column with everything)
                        if len(df.columns) > 1 or df.iloc[0, 0] != text_content.split('\n')[0]:
                            # Clean up numeric columns by removing commas and quotes
                            for col in df.columns:
                                if df[col].dtype == 'object':
                                    # Try to clean and convert numeric columns
                                    try:
                                        # Remove quotes and commas from potential numeric data
                                        cleaned_series = df[col].astype(str).str.replace('"', '').str.replace(',', '')
                                        # Try to convert to numeric
                                        numeric_series = pd.to_numeric(cleaned_series, errors='coerce')
                                        # If more than 50% are numeric, replace the column
                                        if numeric_series.notna().sum() > len(numeric_series) * 0.5:
                                            df[col] = numeric_series
                                    except:
                                        continue
                            return df, None
                except:
                    continue
            
            # If all delimiters fail, try without headers
            try:
                string_io = io.StringIO(text_content)
                df = pd.read_csv(string_io, header=None)
                
                if not df.empty and len(df.columns) > 0:
                    # Generate column names
                    df.columns = [f'Column_{i+1}' for i in range(len(df.columns))]
                    return df, None
            except:
                pass
            
            return None, f"Cannot parse CSV file with any delimiter or format"
        
        else:
            return None, f"Unsupported file format: {file_extension}"
            
    except Exception as e:
        return None, f"File reading error: {str(e)}"

def analyze_dataframe(df, brand_name="Unknown"):
    """
    Analyze dataframe and identify price/date columns
    """
    try:
        # Basic statistics
        analysis = {
            'brand_name': brand_name,
            'total_rows': len(df),
            'total_columns': len(df.columns),
            'columns': list(df.columns),
            'data_types': {str(k): str(v) for k, v in df.dtypes.to_dict().items()},
            'sample_data': df.head(3).to_dict('records') if len(df) > 0 else [],
            'has_price_data': False,
            'has_date_data': False,
            'price_column': None,
            'date_column': None,
            'data_range': None
        }
        
        # Try to identify price column
        price_candidates = []
        date_candidates = []
        
        for col in df.columns:
            col_lower = str(col).lower()
            
            # Check for price-related columns
            if any(word in col_lower for word in ['price', 'close', 'last', 'value', 'high', 'low', 'open']):
                price_candidates.append(col)
            
            # Check for date-related columns
            if any(word in col_lower for word in ['date', 'time', 'datetime', 'timestamp']):
                date_candidates.append(col)
        
        # If no obvious candidates, check data types and use first numeric column
        if not price_candidates:
            for col in df.columns:
                try:
                    # Try to convert to numeric
                    numeric_data = pd.to_numeric(df[col], errors='coerce')
                    if numeric_data.notna().sum() > len(numeric_data) * 0.5:  # More than 50% numeric
                        price_candidates.append(col)
                except:
                    pass
        
        # If still no candidates, use first column with numeric data
        if not price_candidates:
            for col in df.columns:
                if df[col].dtype in ['float64', 'int64'] or any(isinstance(val, (int, float)) for val in df[col].dropna().iloc[:5]):
                    price_candidates.append(col)
                    break
        
        analysis['price_candidates'] = price_candidates
        analysis['date_candidates'] = date_candidates
        
        if price_candidates:
            analysis['recommended_price_column'] = price_candidates[0]
            analysis['price_column'] = price_candidates[0]
            analysis['has_price_data'] = True
        
        if date_candidates:
            analysis['recommended_date_column'] = date_candidates[0]
            analysis['date_column'] = date_candidates[0]
            analysis['has_date_data'] = True
            
            # Calculate date range if date column exists
            try:
                date_col = date_candidates[0]
                date_data = pd.to_datetime(df[date_col], errors='coerce')
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
        return {'error': f"Analysis failed: {str(e)}"}