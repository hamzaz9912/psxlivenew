"""
Test script to verify XAUSD file upload functionality
"""

import pandas as pd
from simple_file_reader import read_any_file, analyze_dataframe
from universal_predictor_new import UniversalPredictor

def test_xausd_format():
    """Test the XAUSD CSV format handling"""
    
    # Create sample XAUSD data in the same format as user's file
    sample_data = '''﻿"Date","Price","Open","High","Low","Vol.","Change %"
"07/09/2025","3,312.14","3,302.73","3,314.64","3,282.90","","0.30%"
"07/08/2025","3,302.35","3,335.99","3,345.94","3,287.17","","-1.00%"
"07/07/2025","3,335.61","3,335.95","3,343.29","3,296.41","","0.20%"
"07/06/2025","3,328.98","3,341.40","3,341.89","3,326.37","","-0.23%"
"07/04/2025","3,336.64","3,326.44","3,345.15","3,323.59","","0.30%"'''
    
    # Save to temporary file
    with open('test_xausd.csv', 'w', encoding='utf-8-sig') as f:
        f.write(sample_data)
    
    print("Testing XAUSD file format...")
    
    # Test 1: Read the file
    class MockFile:
        def __init__(self, filename):
            self.name = filename
            with open(filename, 'rb') as f:
                self.content = f.read()
            self.pos = 0
        
        def seek(self, pos):
            self.pos = pos
        
        def read(self):
            return self.content[self.pos:]
    
    mock_file = MockFile('test_xausd.csv')
    
    # Test reading
    df, error = read_any_file(mock_file)
    
    if error:
        print(f"❌ Error reading file: {error}")
        return False
    
    print("✅ File read successfully!")
    print(f"Shape: {df.shape}")
    print(f"Columns: {list(df.columns)}")
    print("\nFirst few rows:")
    print(df.head())
    
    # Test analysis
    analysis = analyze_dataframe(df, "XAUSD")
    
    if 'error' in analysis:
        print(f"❌ Error analyzing file: {analysis['error']}")
        return False
    
    print("\n✅ File analysis successful!")
    print(f"Price column detected: {analysis.get('price_column')}")
    print(f"Date column detected: {analysis.get('date_column')}")
    print(f"Data types: {analysis.get('data_types')}")
    
    # Test prediction generation
    predictor = UniversalPredictor()
    
    try:
        predictions = predictor.generate_predictions(df, "XAUSD", analysis['price_column'], analysis.get('date_column'))
        
        if 'error' in predictions:
            print(f"❌ Error generating predictions: {predictions['error']}")
            return False
        
        print("\n✅ Predictions generated successfully!")
        print(f"Current price: {predictions['current_price']}")
        print(f"Data points: {predictions['data_points']}")
        print(f"Volatility: {predictions['volatility']:.6f}")
        
        return True
        
    except Exception as e:
        print(f"❌ Error in prediction generation: {str(e)}")
        return False

if __name__ == "__main__":
    success = test_xausd_format()
    if success:
        print("\n🎉 All tests passed! XAUSD file upload should work correctly.")
    else:
        print("\n💥 Tests failed. There are still issues to fix.")