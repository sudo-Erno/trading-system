import pandas as pd
import yfinance as yf
import numpy as np
import requests
import os
import time
from io import StringIO
from logs import get_core_logger
from dotenv import load_dotenv, find_dotenv

logger = get_core_logger("EquityScreener")

load_dotenv(find_dotenv())


def get_sp500_tickers() -> list:
    """
    Dynamically fetches the current S&P 500 tickers from Wikipedia.
    This ensures our universe is always up-to-date with index inclusions/exclusions.
    """
    logger.info("Fetching latest S&P 500 constituents from Wikipedia...")
    try:
        # Wikipedia blocks default Python scrapers. We must use a standard browser User-Agent.
        url = 'https://en.wikipedia.org/wiki/List_of_S%26P_500_companies'
        headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'}
        
        response = requests.get(url, headers=headers)
        response.raise_for_status()
        
        # Wrap the raw HTML in StringIO for newer Pandas versions 
        # and explicitly target the 'constituents' table id to avoid parsing junk tables.
        html_buffer = StringIO(response.text)
        table = pd.read_html(html_buffer, attrs={'id': 'constituents'})
        
        df = table[0]
        # YFinance uses '-' instead of '.' for tickers like BRK.B -> BRK-B
        tickers = df['Symbol'].str.replace('.', '-', regex=False).tolist()
        
        logger.info(f"Successfully loaded {len(tickers)} tickers from Wikipedia.")
        return tickers
    except Exception as e:
        logger.error(f"Failed to fetch S&P 500 list: {e}")
        # Fallback to a hardcoded high-liquidity list if Wikipedia fails
        return ['AAPL', 'MSFT', 'NVDA', 'TSLA', 'META', 'AMZN', 'GOOGL']

def screen_equities(limit: int = 5, cache_hours: int = 4) -> list:
    """
    Acts as a programmatic Finviz. Scans the S&P 500 for volume spikes 
    and high volatility, returning the top N tickers for the C++ engine.
    Implements a local cache to avoid spamming the Yahoo Finance API.
    """
    tickers = get_sp500_tickers()
    
    cache_dir = os.getenv("SP500_TICKERS_DATA_DIR")
    cache_file = os.path.join(cache_dir, 'sp500_30d_cache.pkl')
    cache_expiry_seconds = cache_hours * 3600
    
    data = None
    
    # 1. Check if a valid, recent cache exists
    if os.path.exists(cache_file):
        file_age = time.time() - os.path.getmtime(cache_file)
        if file_age < cache_expiry_seconds:
            logger.info(f"Loading S&P 500 data from local cache (Age: {file_age/3600:.2f} hours)...")
            try:
                data = pd.read_pickle(cache_file)
            except Exception as e:
                logger.warning(f"Cache corrupted or unreadable: {e}. Forcing re-download.")
                data = None
        else:
            logger.info("Local cache expired. Fetching fresh data...")
            
    # 2. Download if no cache exists or the cache expired
    if data is None:
        logger.info(f"Downloading 30-day history for {len(tickers)} equities (this takes ~10-20 seconds)...")
        try:
            # We drop any tickers that fail to download to keep the dataset clean
            data = yf.download(tickers, period="1mo", progress=False, group_by='ticker', threads=True)
            
            # Save the heavy DataFrame to a pickle file for instant loading later
            os.makedirs(cache_dir, exist_ok=True)
            data.to_pickle(cache_file)
            logger.info(f"Successfully cached data to {cache_file}")
            
        except Exception as e:
            logger.error(f"Failed to download batch equity data: {e}")
            return []

    results = []

    # 3. Process the data
    for ticker in tickers:
        try:
            # Check if data exists for the ticker
            if ticker not in data or data[ticker].empty:
                continue
                
            df = data[ticker].copy()
            df.dropna(inplace=True)
            
            if len(df) < 20: # Ensure we have enough history
                continue
                
            # Base Liquidity Filter: Ignore penny stocks and low-volume assets
            current_price = df['Close'].iloc[-1]
            avg_volume = df['Volume'].mean()
            if current_price < 10 or avg_volume < 1_000_000:
                continue

            # Volume Spike Calculation (Current Volume / 30-Day Moving Average)
            current_volume = df['Volume'].iloc[-1]
            volume_ratio = current_volume / avg_volume

            # Volatility Calculation (Standard Deviation of daily returns)
            returns = df['Close'].pct_change().dropna()
            volatility = returns.std()

            # Store the metrics
            results.append({
                'ticker': ticker,
                'price': float(current_price),
                'volume_ratio': float(volume_ratio),
                'volatility': float(volatility)
            })
            
        except Exception:
            # Silently skip tickers that have formatting issues
            continue

    if not results:
        logger.warning("No equities passed the screening filters.")
        return []

    results_df = pd.DataFrame(results)
    
    # 4. The Quant Ranking Logic
    results_df['rank_score'] = (results_df['volume_ratio'] * 0.7) + (results_df['volatility'] * 100 * 0.3)
    
    # Sort by the highest score
    top_equities = results_df.sort_values(by='rank_score', ascending=False).head(limit)
    
    logger.info(f"\n--- Top {limit} Equities Selected for C++ Processing ---")
    for _, row in top_equities.iterrows():
        logger.info(f"{row['ticker']}: Score {row['rank_score']:.2f} | Vol Ratio {row['volume_ratio']:.2f}x | Volatility {row['volatility']:.4f}")
        
    return top_equities['ticker'].tolist()

if __name__ == "__main__":
    # Test the screener natively
    print("Initializing Quantitative Equity Screener...")
    top_tickers = screen_equities(limit=5)
    print(f"\nFinal Ticker List to pass to C++ engine: {top_tickers}")