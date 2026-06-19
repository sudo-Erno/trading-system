import ccxt
import pandas as pd
import os

from datetime import datetime, timedelta
from dotenv import load_dotenv, find_dotenv

from logs import get_core_logger

load_dotenv(find_dotenv())

logger = get_core_logger("MarketDataFetcher")

def fetch_market_data(exchange, symbol, timeframe, save_dir=None, days_back=30):
    """
    Fetches historical OHLCV data from Binance and returns a perfectly 
    formatted Pandas DataFrame. Handles pagination to bypass the 1000-candle limit.
    Optionally saves the DataFrame to a CSV file if save_dir is provided.
    """
    logger.info(f"Fetching {timeframe} data for {symbol} over the last {days_back} days...")

    # Calculate the starting timestamp in milliseconds (CCXT standard)
    start_date = datetime.utcnow() - timedelta(days=days_back)
    since_timestamp = int(start_date.timestamp() * 1000)
    
    all_ohlcv = []
    
    # Binance limits us to 1000 candles per request.
    # We use a loop to fetch data until we reach the current date.
    while True:
        try:
            # fetch_ohlcv returns: [timestamp, open, high, low, close, volume]
            ohlcv = exchange.fetch_ohlcv(
                symbol=symbol, 
                timeframe=timeframe, 
                since=since_timestamp, 
                limit=1000
            )
            
            if not ohlcv:
                break # No more data available
                
            all_ohlcv.extend(ohlcv)
            
            # Update the 'since' timestamp to the last fetched candle's timestamp + 1 millisecond
            # to avoid fetching the same candle twice in the next loop iteration
            last_timestamp = ohlcv[-1][0]
            since_timestamp = last_timestamp + 1
            
            # Safe exit if we've fetched up to the current moment
            if since_timestamp >= int(datetime.utcnow().timestamp() * 1000):
                break
                
        except Exception as e:
            logger.error(f"Error fetching data: {e}", exc_info=True)
            # print(f"Error fetching data: {e}")
            break

    if not all_ohlcv:
        logger.warning("No data was fetched.")
        return pd.DataFrame()

    # Convert the raw array into a Pandas DataFrame
    df = pd.DataFrame(all_ohlcv, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
    
    # Convert timestamps from milliseconds to UTC datetime objects
    df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')
    
    # Set the timestamp as the index (crucial for time-series and ML analysis)
    df.set_index('timestamp', inplace=True)
    
    # Ensure all data is numeric (prevents string errors in ML models)
    df = df.apply(pd.to_numeric)
    
    print(f"Success! Retrieved {len(df)} candles.")

    # Save to CSV if a directory was specified
    if save_dir:
        os.makedirs(save_dir, exist_ok=True)
        # Create a safe filename (e.g., BTC_USDT_4h.csv)
        safe_symbol = symbol.replace('/', '_')
        filename = f"{safe_symbol}_{timeframe}.csv"
        filepath = os.path.join(save_dir, filename)
        
        df.to_csv(filepath)
        print(f"Data successfully saved to {filepath}")
        
    return df


if __name__ == "__main__":
    from binance_connector import connect_to_binance
    
    # 1. Connect to Binance using our existing connector
    # Note: connect_to_binance() has enableRateLimit=True, which automatically 
    # pauses our while loop slightly so we don't get banned by Binance!
    active_exchange = connect_to_binance()
    
    if active_exchange:
        # 2. Define our parameters (e.g., Bitcoin H4 chart for the last 60 days)
        target_symbol = 'BTC/USDT'
        target_timeframe = '4h'
        history_days = 60
        
        # 3. Fetch the data
        historical_df = fetch_market_data(
            exchange=active_exchange, 
            symbol=target_symbol, 
            timeframe=target_timeframe, 
            days_back=history_days
        )
        
        # 4. Inspect our professional, ML-ready DataFrame
        if not historical_df.empty:
            print("\n--- DataFrame Head ---")
            print(historical_df.head())
            print("\n--- DataFrame Tail ---")
            print(historical_df.tail())
            print("\n--- DataFrame Info ---")
            print(historical_df.info())