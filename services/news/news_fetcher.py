import os
import requests
from datetime import datetime
from dotenv import load_dotenv, find_dotenv
from logs import get_core_logger

# Load environment variables
load_dotenv(find_dotenv())
logger = get_core_logger("NewsFetcher")

def fetch_crypto_news(symbol: str, limit: int = 5) -> list:
    """
    Fetches the latest crypto headlines using the CryptoPanic API.
    Requires CRYPTOPANIC_API_KEY in the .env file.
    """
    api_key = os.getenv("CRYPTOPANIC_API_KEY")
    if not api_key:
        logger.warning("CRYPTOPANIC_API_KEY missing. Returning mock crypto news for safety.")
        return [f"[{datetime.utcnow().strftime('%Y-%m-%d')}] Mock News: {symbol} sees institutional inflow."]

    # CryptoPanic uses the base ticker (e.g., 'BTC' instead of 'BTC/USDT')
    base_ticker = symbol.split('/')[0] if '/' in symbol else symbol
    
    url = f"https://cryptopanic.com/api/v1/posts/?auth_token={api_key}&currencies={base_ticker}&filter=hot"
    
    try:
        response = requests.get(url, timeout=10)
        response.raise_for_status()
        data = response.json()
        
        headlines = []
        for post in data.get('results', [])[:limit]:
            # Extract the date and title
            published_at = post.get('published_at', '')[:10] # Get YYYY-MM-DD
            title = post.get('title', 'No Title')
            headlines.append(f"[{published_at}] {title}")
            
        return headlines
    except Exception as e:
        logger.error(f"Failed to fetch CryptoPanic news for {symbol}: {e}")
        return []

def fetch_tradfi_news(symbol: str, limit: int = 5) -> list:
    """
    Fetches the latest equity/TradFi headlines using the Alpaca API (Benzinga feeds).
    Requires ALPACA_API_KEY and ALPACA_API_SECRET in the .env file.
    """
    api_key = os.getenv("ALPACA_API_KEY")
    api_secret = os.getenv("ALPACA_API_SECRET")
    
    if not api_key or not api_secret:
        logger.warning("Alpaca API keys missing. Returning mock TradFi news.")
        return [f"[{datetime.utcnow().strftime('%Y-%m-%d')}] Mock News: {symbol} beats earnings estimates."]

    url = f"https://data.alpaca.markets/v1beta1/news?symbols={symbol}&limit={limit}"
    headers = {
        "APCA-API-KEY-ID": api_key,
        "APCA-API-SECRET-KEY": api_secret
    }
    
    try:
        response = requests.get(url, headers=headers, timeout=10)
        response.raise_for_status()
        data = response.json()
        
        headlines = []
        for article in data.get('news', []):
            published_at = article.get('created_at', '')[:10]
            headline = article.get('headline', 'No Title')
            headlines.append(f"[{published_at}] {headline}")
            
        return headlines
    except Exception as e:
        logger.error(f"Failed to fetch Alpaca news for {symbol}: {e}")
        return []

def get_news_context(symbol: str, asset_class: str = "crypto", limit: int = 5) -> str:
    """
    The main routing function. Determines which API to call based on the asset class,
    and formats the array of headlines into a single clean string for LLM injection.
    """
    logger.info(f"Fetching NLP context for {symbol} ({asset_class})...")
    
    if asset_class.lower() == "crypto":
        headlines = fetch_crypto_news(symbol, limit)
    elif asset_class.lower() in ["tradfi", "equity", "stock"]:
        headlines = fetch_tradfi_news(symbol, limit)
    else:
        logger.error(f"Unknown asset class: {asset_class}")
        return "No news available."
        
    if not headlines:
        return "No significant news catalysts detected."
        
    # Format into a clean bulleted list for the LLM
    formatted_news = "\n".join([f"- {headline}" for headline in headlines])
    logger.info(f"Successfully retrieved {len(headlines)} headlines for {symbol}.")
    
    return formatted_news

if __name__ == "__main__":
    # Test the module directly
    print("--- Testing Crypto News (BTC) ---")
    btc_news = get_news_context("BTC/USDT", asset_class="crypto", limit=3)
    print(btc_news)
    
    print("\n--- Testing TradFi News (AAPL) ---")
    aapl_news = get_news_context("AAPL", asset_class="tradfi", limit=3)
    print(aapl_news)