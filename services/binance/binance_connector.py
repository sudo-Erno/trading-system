import ccxt
import os
from dotenv import load_dotenv, find_dotenv
from pprint import pprint

from logs import get_core_logger

# Initialize the logger for this specific file
logger = get_core_logger("BinanceConnector")



def connect_to_binance():
    """
    Establishes an authenticated connection to the Binance API using CCXT.
    Requires BINANCE_API_KEY and BINANCE_SECRET_KEY to be set in the environment.
    """
    # 1. Retrieve keys from environment variables
    load_dotenv(find_dotenv())
    
    api_key = os.getenv('BINANCE_API_KEY')
    api_secret = os.getenv('BINANCE_SECRET_KEY')

    if not api_key or not api_secret:
        raise ValueError("CRITICAL: Binance API keys not found in environment variables.")

    logger.info("Initializing Binance connection...")

    # 2. Initialize the Exchange Instance
    try:
        exchange = ccxt.binance({
            'apiKey': api_key,
            'secret': api_secret,
            # CRITICAL: Always enable the rate limiter to prevent IP bans
            'enableRateLimit': True,
            # Optional: Set to True if you want to use the Binance Testnet (Paper Trading)
            # 'urls': {
            #     'api': {
            #         'public': 'https://testnet.binance.vision/api/v3',
            #         'private': 'https://testnet.binance.vision/api/v3',
            #     }
            # }
        })

        # 3. Test the connection by fetching account balances
        logger.info("Authenticating and fetching account balance...")
        
        # We use fetch_balance() to ensure private API access is working
        balance = exchange.fetch_balance()
        
        # Parse the balance to only show assets where you hold a non-zero amount
        non_zero_balances = {
            asset: amounts 
            for asset, amounts in balance['total'].items() 
            if amounts > 0
        }
        
        logger.info("--- Connection Successful! ---")
        logger.info(f"Current Active Balances: {non_zero_balances}")
        # pprint(non_zero_balances)
        
        return exchange

    except ccxt.AuthenticationError as e:
        logger.error(f"FAILED: Invalid API Key or Secret. Details: {e}")
    except ccxt.NetworkError as e:
        logger.error(f"FAILED: Network issue or Binance is down. Details: {e}")
    except Exception as e:
        logger.error(f"FAILED: An unexpected error occurred. Details: {e}", exc_info=True)
        
    return None

if __name__ == "__main__":
    # To run this, you must first export your keys in your terminal:
    # export BINANCE_API_KEY="your_api_key_here"
    # export BINANCE_SECRET_KEY="your_secret_key_here"
    
    active_exchange = connect_to_binance()
    
    # If successful, you can now use 'active_exchange' to fetch data or place orders
    # Example: active_exchange.fetch_ticker('BTC/USDT')