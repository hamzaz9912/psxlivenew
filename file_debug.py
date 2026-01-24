"""
Comprehensive file debugging utility for universal file upload
"""
import pandas as pd
import io
# import chardet

def analyze_uploaded_file(uploaded_file):
    """Comprehensive analysis of uploaded file"""
    analysis = {}
    
    try:
        # Basic file info
        analysis['file_name'] = uploaded_file.name
        analysis['file_size'] = uploaded_file.size
        analysis['file_type'] = uploaded_file.type
        
        # Read raw bytes
        uploaded_file.seek(0)
        raw_bytes = uploaded_file.read()
        analysis['raw_size'] = len(raw_bytes)
        
        # Detect encoding (fallback without chardet)
        analysis['detected_encoding'] = {'encoding': 'utf-8', 'confidence': 0.8}
        
        # Try to decode with detected encoding
        try:
            if analysis['detected_encoding']['encoding']:
                content = raw_bytes.decode(analysis['detected_encoding']['encoding'])
                analysis['decode_success'] = True
                analysis['content_length'] = len(content)
                
                # Analyze content structure
                lines = content.split('\n')
                analysis['total_lines'] = len(lines)
                analysis['non_empty_lines'] = len([line for line in lines if line.strip()])
                
                if lines:
                    first_line = lines[0]
                    analysis['first_line'] = first_line
                    analysis['first_line_length'] = len(first_line)
                    
                    # Check for common delimiters
                    delimiters = {
                        'comma': first_line.count(','),
                        'semicolon': first_line.count(';'),
                        'tab': first_line.count('\t'),
                        'pipe': first_line.count('|'),
                        'space': first_line.count(' ')
                    }
                    analysis['delimiter_counts'] = delimiters
                    
                    # Find best delimiter
                    best_delimiter = max(delimiters, key=delimiters.get)
                    analysis['suggested_delimiter'] = best_delimiter
                    analysis['suggested_delimiter_count'] = delimiters[best_delimiter]
                    
                    # Try to parse with suggested delimiter
                    if delimiters[best_delimiter] > 0:
                        delimiter_char = {'comma': ',', 'semicolon': ';', 'tab': '\t', 'pipe': '|', 'space': ' '}[best_delimiter]
                        headers = first_line.split(delimiter_char)
                        analysis['potential_headers'] = headers
                        analysis['potential_columns'] = len(headers)
                        
                        # Check data consistency
                        consistent_rows = 0
                        for line in lines[1:]:
                            if line.strip():
                                row = line.split(delimiter_char)
                                if len(row) == len(headers):
                                    consistent_rows += 1
                        
                        analysis['consistent_data_rows'] = consistent_rows
                        analysis['data_consistency'] = consistent_rows > 0
                
                # Show first few lines
                analysis['first_5_lines'] = lines[:5]
                
            else:
                analysis['decode_success'] = False
                analysis['decode_error'] = "No encoding detected"
                
        except Exception as decode_error:
            analysis['decode_success'] = False
            analysis['decode_error'] = str(decode_error)
        
        # Try pandas read with different methods
        pandas_results = []
        
        # Method 1: Standard read_csv
        try:
            uploaded_file.seek(0)
            df = pd.read_csv(uploaded_file)
            pandas_results.append({
                'method': 'standard_csv',
                'success': True,
                'rows': len(df),
                'columns': len(df.columns),
                'column_names': list(df.columns)
            })
        except Exception as e:
            pandas_results.append({
                'method': 'standard_csv',
                'success': False,
                'error': str(e)
            })
        
        # Method 2: Try common delimiters
        for delim_name, delim_char in [('comma', ','), ('semicolon', ';'), ('tab', '\t'), ('pipe', '|')]:
            try:
                uploaded_file.seek(0)
                df = pd.read_csv(uploaded_file, delimiter=delim_char)
                pandas_results.append({
                    'method': f'delimiter_{delim_name}',
                    'success': True,
                    'rows': len(df),
                    'columns': len(df.columns),
                    'column_names': list(df.columns)
                })
            except Exception as e:
                pandas_results.append({
                    'method': f'delimiter_{delim_name}',
                    'success': False,
                    'error': str(e)
                })
        
        # Method 3: Try different encodings
        for encoding in ['utf-8', 'latin-1', 'iso-8859-1', 'cp1252']:
            try:
                uploaded_file.seek(0)
                df = pd.read_csv(uploaded_file, encoding=encoding)
                pandas_results.append({
                    'method': f'encoding_{encoding}',
                    'success': True,
                    'rows': len(df),
                    'columns': len(df.columns),
                    'column_names': list(df.columns)
                })
            except Exception as e:
                pandas_results.append({
                    'method': f'encoding_{encoding}',
                    'success': False,
                    'error': str(e)
                })
        
        analysis['pandas_attempts'] = pandas_results
        
        # Check if any pandas method succeeded
        successful_methods = [result for result in pandas_results if result['success']]
        analysis['successful_pandas_methods'] = len(successful_methods)
        
        if successful_methods:
            analysis['recommended_method'] = successful_methods[0]
        
        return analysis
        
    except Exception as e:
        analysis['error'] = str(e)
        return analysis

def create_manual_dataframe(raw_content, delimiter, headers_row=0, encoding='utf-8'):
    """Create dataframe manually from raw content"""
    try:
        lines = raw_content.split('\n')
        
        if len(lines) <= headers_row:
            return None, "Not enough lines for headers"
        
        headers = lines[headers_row].split(delimiter)
        headers = [h.strip() for h in headers]
        
        data = []
        for line in lines[headers_row + 1:]:
            if line.strip():
                row = line.split(delimiter)
                row = [r.strip() for r in row]
                if len(row) == len(headers):
                    data.append(row)
        
        if not data:
            return None, "No valid data rows found"
        
        df = pd.DataFrame(data, columns=headers)
        return df, "Success"
        
    except Exception as e:
        return None, str(e)