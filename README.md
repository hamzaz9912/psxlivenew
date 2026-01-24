# PSX Stock Forecasting Dashboard

A comprehensive real-time stock market forecasting dashboard for the Pakistan Stock Exchange (PSX) KSE-100 index and its constituent companies.

## Features

- **Real-time Data**: Live stock prices from Pakistani financial sources
- **Advanced Forecasting**: Machine learning predictions using Facebook Prophet
- **5-Minute Intervals**: Detailed intraday forecasting with 5-minute precision
- **Time Range Selection**: Custom date and time range analysis
- **File Upload**: Upload and analyze any stock data files
- **Interactive Charts**: Dynamic visualizations with Plotly
- **Auto-refresh**: Real-time updates every 5 minutes

## Live Demo

🚀 **Deploy on Streamlit Community Cloud (Free)**

## Quick Start

1. **Clone the repository**
```bash
git clone <your-repo-url>
cd psx-stock-forecasting
```

2. **Install dependencies**
```bash
pip install -r requirements_streamlit.txt
```

3. **Run the application**
```bash
streamlit run app.py
```

## Streamlit Community Cloud Deployment

### Prerequisites
- GitHub account
- Streamlit Community Cloud account (free at [share.streamlit.io](https://share.streamlit.io))

### Deployment Steps

1. **Push to GitHub**
   - Create a new repository on GitHub
   - Upload all project files including `app.py` and the dependencies

2. **Deploy on Streamlit**
   - Go to [share.streamlit.io](https://share.streamlit.io)
   - Click "New app"
   - Connect your GitHub repository
   - Set main file: `app.py`
   - Click "Deploy"

3. **Dependencies**
   The app uses these main packages (automatically installed):
   - streamlit>=1.46.1
   - pandas>=2.3.0
   - numpy>=2.3.1
   - plotly>=6.2.0
   - prophet>=1.1.7
   - requests>=2.32.4
   - beautifulsoup4>=4.13.4
   - streamlit-autorefresh>=1.0.1

## Project Structure

```
psx-stock-forecasting/
├── app.py                    # Main Streamlit application
├── advanced_forecasting.py   # Advanced forecasting features
├── data_fetcher.py          # Live data acquisition
├── forecasting.py           # Machine learning models
├── visualization.py         # Chart generation
├── simple_cache.py          # In-memory caching
├── utils.py                 # Helper functions
├── enhanced_features.py     # Enhanced dashboard features
├── comprehensive_intraday.py # Intraday analysis
└── .streamlit/
    └── config.toml          # Streamlit configuration
```

## Key Features

### 1. Real-time Dashboard
- Live KSE-100 index monitoring
- 75+ Pakistani companies tracking
- Market open/close status

### 2. Advanced Forecasting
- Time range selection (5-minute intervals)
- Custom date forecasting
- Multiple prediction models
- Confidence intervals

### 3. File Upload Analysis
- Support for CSV/Excel files
- Automatic data integration
- Brand-specific analysis

### 4. Interactive Visualizations
- Candlestick charts
- Volume indicators
- Forecast overlays
- Real-time updates

## Data Sources

- Pakistan Stock Exchange (PSX) official data
- Business Recorder financial data
- Dawn Business section
- Multiple Pakistani financial websites

## Technical Details

- **Framework**: Streamlit
- **ML Model**: Facebook Prophet
- **Charts**: Plotly
- **Data**: Real-time web scraping
- **Cache**: In-memory with 5-minute TTL
- **Deployment**: Streamlit Community Cloud ready

## Performance

- **Startup**: ~10-15 seconds
- **Data Refresh**: Every 5 minutes
- **Memory Usage**: ~200MB
- **Response Time**: <2 seconds

## License

This project is open source and available under the MIT License.

## Support

For issues and questions, please create an issue in the GitHub repository.

---

**Ready for Streamlit Community Cloud deployment!** 🚀