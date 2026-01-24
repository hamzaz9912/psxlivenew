import sys
import os
sys.path.append(os.path.dirname(__file__))

from enhanced_psx_fetcher import EnhancedPSXFetcher

# List of symbols to fetch
symbols = [
    'HBL', 'UBL', 'NBP', 'ABL', 'JSBL', 'APL', 'BWCL', 'ACPL', 'JSCL', 'ASC',
    'IBLHL', 'BBFL', 'SPEL', 'SLGL', 'AGSML', 'PKGP', 'SGPL', 'KTML', 'BFAGRO',
    'ZAL', 'CEPB', 'PSX', 'HMB', 'DHPL', 'FNEL', 'IBFL', 'DCR', 'HGFA', 'LCI',
    'PABC', 'TGL', 'BNWM', 'SCBPL', 'PSEL'
]

# Create fetcher instance
fetcher = EnhancedPSXFetcher()

# Modified fetch_live_prices_batch without streamlit
def fetch_live_prices_batch_no_st(fetcher, symbols_list):
    batch_data = {}

    print(f"Fetching live prices for {len(symbols_list)} companies in batch mode...")

    # Get comprehensive market data first
    market_data = fetcher._fetch_psx_market_summary()
    alt_data = fetcher._fetch_alternative_sources()

    # Combine all data sources
    all_market_data = {}
    all_market_data.update(market_data)
    all_market_data.update(alt_data)

    successful_fetches = 0

    for i, symbol in enumerate(symbols_list):
        print(f"Processing {symbol}... ({i+1}/{len(symbols_list)})")

        # Try to find in market data first
        live_price = None
        data_source = 'unavailable'

        # Search in all market data
        for market_symbol, market_info in all_market_data.items():
            if symbol.upper() == market_symbol.upper():
                live_price = market_info.get('current', market_info.get('price', 0))
                data_source = market_info.get('source', 'psx_batch')
                break

        # If not found in batch data, try individual fetch
        if not live_price:
            individual_data = fetcher._fetch_individual_company_price(symbol)
            if individual_data:
                live_price = individual_data['price']
                data_source = individual_data['source']

        # If still no live price, use estimate
        if not live_price:
            live_price = fetcher._get_sector_based_estimate(symbol)
            data_source = 'sector_estimate_batch'

        batch_data[symbol] = {
            'symbol': symbol,
            'company_name': fetcher.kse100_companies.get(symbol, 'Unknown'),
            'current_price': live_price,
            'timestamp': fetcher.get_pakistan_time(),
            'source': data_source
        }

        if data_source != 'sector_estimate_batch':
            successful_fetches += 1

    print(f"Batch fetch complete: {successful_fetches}/{len(symbols_list)} live prices")
    return batch_data

# Fetch prices
prices = fetch_live_prices_batch_no_st(fetcher, symbols)

# Print results
print("\nLive Prices for Requested Symbols:")
print("=" * 50)
for symbol, data in prices.items():
    price = data['current_price']
    source = data['source']
    timestamp = data['timestamp']
    print(f"{symbol}: PKR {price:.2f} (Source: {source}, Time: {timestamp})")

print("\nFetch complete.")