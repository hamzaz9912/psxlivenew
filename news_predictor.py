"""
News-based Market Prediction Module
Fetches live news and analyzes sentiment for PSX market predictions
"""

import requests
from bs4 import BeautifulSoup
import re
from datetime import datetime, timedelta
import pandas as pd
import numpy as np

class NewsBasedPredictor:
    """Fetch live news and predict market movements based on sentiment analysis"""
    
    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        })
        self.news_sources = [
            'https://www.dawn.com/business',
            'https://www.businessrecorder.com.pk',
            'https://www.thenews.com.pk/category/business',
            'https://profit.pakistantoday.com.pk',
            'https://www.brecorder.com'
        ]
        
    def fetch_live_market_news(self):
        """Fetch live market news from Pakistani financial sources"""
        all_news = []
        
        for source_url in self.news_sources:
            try:
                response = self.session.get(source_url, timeout=10)
                if response.status_code == 200:
                    soup = BeautifulSoup(response.content, 'html.parser')
                    
                    # Extract news headlines and content
                    headlines = []
                    
                    # Common selectors for news headlines
                    headline_selectors = [
                        'h1', 'h2', 'h3', '.headline', '.title', '.news-title',
                        'a[href*="stock"]', 'a[href*="business"]', 'a[href*="market"]',
                        'a[href*="psx"]', 'a[href*="kse"]'
                    ]
                    
                    for selector in headline_selectors:
                        elements = soup.select(selector)
                        for element in elements:
                            text = element.get_text(strip=True)
                            if len(text) > 20 and any(keyword in text.lower() for keyword in 
                                ['stock', 'market', 'psx', 'kse', 'index', 'shares', 'trading', 'economy']):
                                headlines.append({
                                    'headline': text,
                                    'source': source_url.split('//')[1].split('/')[0],
                                    'timestamp': datetime.now()
                                })
                    
                    all_news.extend(headlines[:10])  # Limit to 10 news per source
                    
            except Exception as e:
                print(f"Error fetching news from {source_url}: {e}")
                continue
        
        return all_news[:50]  # Return top 50 news items
    
    def analyze_news_sentiment(self, news_list):
        """Analyze sentiment of news headlines for market prediction"""
        if not news_list:
            return {'sentiment': 'neutral', 'confidence': 0.5, 'prediction': 'stable'}
        
        # Sentiment keywords
        positive_keywords = [
            'growth', 'profit', 'gain', 'rise', 'increase', 'positive', 'strong',
            'bullish', 'up', 'higher', 'boost', 'improved', 'record', 'success'
        ]
        
        negative_keywords = [
            'decline', 'loss', 'fall', 'decrease', 'negative', 'weak', 'bearish',
            'down', 'lower', 'drop', 'crash', 'crisis', 'concern', 'worry'
        ]
        
        total_score = 0
        scored_items = 0
        
        for news_item in news_list:
            headline = news_item['headline'].lower()
            
            # Calculate sentiment score
            positive_score = sum(1 for keyword in positive_keywords if keyword in headline)
            negative_score = sum(1 for keyword in negative_keywords if keyword in headline)
            
            if positive_score > 0 or negative_score > 0:
                item_score = (positive_score - negative_score) / (positive_score + negative_score + 1)
                total_score += item_score
                scored_items += 1
        
        if scored_items == 0:
            return {'sentiment': 'neutral', 'confidence': 0.5, 'prediction': 'stable'}
        
        average_sentiment = total_score / scored_items
        
        # Determine sentiment category
        if average_sentiment > 0.1:
            sentiment = 'positive'
            prediction = 'bullish'
            confidence = min(0.8, 0.5 + abs(average_sentiment))
        elif average_sentiment < -0.1:
            sentiment = 'negative'
            prediction = 'bearish'
            confidence = min(0.8, 0.5 + abs(average_sentiment))
        else:
            sentiment = 'neutral'
            prediction = 'stable'
            confidence = 0.5
        
        return {
            'sentiment': sentiment,
            'confidence': confidence,
            'prediction': prediction,
            'score': average_sentiment,
            'news_count': len(news_list)
        }
    
    def generate_news_based_prediction(self, current_price, symbol="KSE-100"):
        """Generate price prediction based on news sentiment"""
        try:
            # Fetch live news
            news_data = self.fetch_live_market_news()
            
            if not news_data:
                return None
            
            # Analyze sentiment
            sentiment_analysis = self.analyze_news_sentiment(news_data)
            
            # Generate price prediction based on sentiment
            base_price = current_price
            
            if sentiment_analysis['prediction'] == 'bullish':
                # Positive sentiment - expect price increase
                price_change = np.random.uniform(0.5, 3.0) * sentiment_analysis['confidence']
                predicted_price = base_price * (1 + price_change / 100)
                trend = 'upward'
            elif sentiment_analysis['prediction'] == 'bearish':
                # Negative sentiment - expect price decrease
                price_change = np.random.uniform(0.5, 3.0) * sentiment_analysis['confidence']
                predicted_price = base_price * (1 - price_change / 100)
                trend = 'downward'
            else:
                # Neutral sentiment - stable price
                price_change = np.random.uniform(-0.5, 0.5)
                predicted_price = base_price * (1 + price_change / 100)
                trend = 'stable'
            
            return {
                'current_price': current_price,
                'predicted_price': predicted_price,
                'price_change': predicted_price - current_price,
                'change_percent': ((predicted_price - current_price) / current_price) * 100,
                'trend': trend,
                'sentiment': sentiment_analysis,
                'news_count': len(news_data),
                'prediction_time': datetime.now(),
                'confidence': sentiment_analysis['confidence']
            }
            
        except Exception as e:
            print(f"Error generating news-based prediction: {e}")
            return None

def get_news_predictor():
    """Get news predictor instance"""
    return NewsBasedPredictor()