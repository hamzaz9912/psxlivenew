"""
Simple test file to debug upload issues
"""
import streamlit as st
import pandas as pd
import io

def test_file_upload():
    """Simple test function for file upload"""
    st.header("🧪 File Upload Test")
    
    uploaded_file = st.file_uploader("Upload test file", type=['csv', 'xlsx', 'xls'])
    
    if uploaded_file is not None:
        st.write("File uploaded successfully!")
        st.write(f"File name: {uploaded_file.name}")
        st.write(f"File size: {uploaded_file.size}")
        st.write(f"File type: {uploaded_file.type}")
        
        try:
            # Read file content
            uploaded_file.seek(0)
            content = uploaded_file.read()
            st.write(f"Raw content length: {len(content)}")
            
            # Try to decode
            try:
                text_content = content.decode('utf-8')
                st.write("✓ UTF-8 decode successful")
                
                lines = text_content.split('\n')
                st.write(f"Number of lines: {len(lines)}")
                
                if lines:
                    st.write("First few lines:")
                    for i, line in enumerate(lines[:5]):
                        st.code(f"Line {i+1}: {line}")
                
                # Try pandas read
                uploaded_file.seek(0)
                df = pd.read_csv(uploaded_file)
                st.write("✓ Pandas read successful")
                st.write(f"Dataframe shape: {df.shape}")
                st.write(f"Columns: {list(df.columns)}")
                st.dataframe(df.head())
                
            except Exception as decode_error:
                st.error(f"Decode error: {str(decode_error)}")
                
        except Exception as e:
            st.error(f"Error processing file: {str(e)}")
    else:
        st.info("Please upload a file to test")

if __name__ == "__main__":
    test_file_upload()