import ccxt
import pandas as pd
from datetime import datetime, timedelta
from logs import get_core_logger
from dotenv import load_dotenv, find_dotenv

load_dotenv(find_dotenv())
logger = get_core_logger("FuturesFetcher")

def fetch_derivatives_data(symbol, days_back=30, timeframe='4h'):
    """
    Connects to the Binance Futures market to fetch Open Interest and 
    Funding Rate history, returning a time-aligned Pandas DataFrame.
    """
    logger.info(f"Connecting to Binance Futures for {symbol} leverage data...")
    
    try:
        # Initialize Binance specifically for USDT-margined Perpetual Futures
        exchange = ccxt.binance({
            'enableRateLimit': True,
            'options': {
                'defaultType': 'future', # CRITICAL: Forces CCXT to use the derivatives API
            }
        })
        
        start_date = datetime.utcnow() - timedelta(days=days_back)
        since_timestamp = int(start_date.timestamp() * 1000)
        
        # 1. Fetch Open Interest History
        logger.info("Fetching Open Interest history...")
        oi_data = []
        current_since = since_timestamp
        
        while True:
            # CCXT handles the Binance endpoint for historical OI
            oi_chunk = exchange.fetch_open_interest_history(symbol, timeframe, current_since, limit=500)
            if not oi_chunk:
                break
                
            oi_data.extend(oi_chunk)
            current_since = oi_chunk[-1]['timestamp'] + 1
            
            if current_since >= int(datetime.utcnow().timestamp() * 1000):
                break
                
        # 2. Fetch Funding Rate History
        logger.info("Fetching Funding Rate history...")
        funding_data = []
        current_since = since_timestamp
        
        while True:
            # Funding rates are typically recorded every 8 hours on Binance
            funding_chunk = exchange.fetch_funding_rate_history(symbol, current_since, limit=500)
            if not funding_chunk:
                break
                
            funding_data.extend(funding_chunk)
            current_since = funding_chunk[-1]['timestamp'] + 1
            
            if current_since >= int(datetime.utcnow().timestamp() * 1000):
                break

        # 3. Process Open Interest into a DataFrame
        oi_df = pd.DataFrame(oi_data)
        if not oi_df.empty:
            oi_df['timestamp'] = pd.to_datetime(oi_df['timestamp'], unit='ms')
            oi_df.set_index('timestamp', inplace=True)
            oi_df = oi_df[['openInterestValue']].rename(columns={'openInterestValue': 'open_interest'})

        # 4. Process Funding Rates into a DataFrame
        fund_df = pd.DataFrame(funding_data)
        if not fund_df.empty:
            fund_df['timestamp'] = pd.to_datetime(fund_df['timestamp'], unit='ms')
            fund_df.set_index('timestamp', inplace=True)
            fund_df = fund_df[['fundingRate']].rename(columns={'fundingRate': 'funding_rate'})

        # 5. Merge the Datasets
        # We use an 'outer' join and forward-fill (ffill). 
        # Why? Because funding happens every 8 hours, but our chart is 4 hours. 
        # We want the 4H candles in between funding payouts to carry the most recent funding rate.
        derivatives_df = oi_df.join(fund_df, how='outer')
        derivatives_df['funding_rate'] = derivatives_df['funding_rate'].ffill()
        
        # Drop any remaining NaNs to ensure clean ML tensors
        derivatives_df.dropna(inplace=True)
        
        logger.info(f"Successfully compiled {len(derivatives_df)} rows of derivatives data.")
        return derivatives_df

    except Exception as e:
        logger.error(f"Failed to fetch derivatives data: {e}", exc_info=True)
        return pd.DataFrame()

if __name__ == "__main__":
    # Test the fetcher (Note: CCXT requires the symbol to look slightly different for futures)
    target_symbol = 'BTC/USDT' 
    
    df_derivatives = fetch_derivatives_data(target_symbol, days_back=10, timeframe='4h')
    
    if not df_derivatives.empty:
        logger.info(f"\n--- Derivatives Data Head ---\n{df_derivatives.head()}")
        logger.info(f"\n--- Derivatives Data Tail ---\n{df_derivatives.tail()}")