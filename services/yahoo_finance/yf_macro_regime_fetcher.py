"""
The Macro Regime is the invisible hand that moves the entire crypto market.
While retail traders stare at Bitcoin's chart wondering why it suddenly crashed,
institutional quants are looking at the bond and currency markets because that is
where the crash actually started.

The Theory: The Global Macro Pulse
Crypto is the ultimate "risk-on" asset. It acts like a sponge for global liquidity. When money is cheap and abundant,
it flows into Bitcoin. When money gets tight, it flees Bitcoin instantly.
We track this using two traditional finance (TradFi) indices:

DXY (The U.S. Dollar Index): This measures the strength of the USD against a basket of foreign currencies. Because Bitcoin is priced in dollars (BTC/USD), it has a mathematical and psychological inverse correlation to the DXY.

The Quant Logic: If the DXY is spiking (the dollar is getting stronger), investors are fleeing to cash. We suppress our algorithmic "Buy" signals because a strong dollar acts like gravity on Bitcoin's price.

US10Y (10-Year Treasury Yield): This is the global benchmark for the "risk-free rate." It tells us exactly what the U.S. Government is paying investors to borrow their money.

The Quant Logic: If the US10Y spikes to 5%, why would hedge funds risk billions in volatile crypto when they can get a guaranteed 5% return from the government? When yields rise, capital is sucked out of the crypto ecosystem.
"""

import yfinance as yf
import pandas as pd
from datetime import datetime, timedelta
from logs import get_core_logger

# Initialize our centralized logger
logger = get_core_logger("MacroFetcher")

def fetch_macro_data(days_back=30):
    """
    Fetches DXY and US10Y data from Yahoo Finance, resamples it to a 4-hour 
    timeframe, and forward-fills weekend gaps to align with 24/7 crypto data.
    """
    logger.info(f"Fetching Macro Regime data (DXY, US10Y) for the last {days_back} days...")
    
    # Calculate date strings required by yfinance
    end_date = datetime.utcnow()
    start_date = end_date - timedelta(days=days_back)
    
    start_str = start_date.strftime('%Y-%m-%d')
    end_str = end_date.strftime('%Y-%m-%d')

    try:
        # 1. Fetch DXY (US Dollar Index) and US10Y (10-Year Yield)
        # Note: 'interval="1h"' is available in yfinance for the last 730 days.
        logger.info("Downloading DX-Y.NYB and ^TNX from Yahoo Finance...")
        macro_tickers = yf.download(["DX-Y.NYB", "^TNX"], start=start_str, end=end_str, interval="1h", progress=False)
        
        # 2. Extract just the closing prices
        # yfinance returns a MultiIndex DataFrame if multiple tickers are passed
        if 'Close' in macro_tickers.columns:
            macro_close = macro_tickers['Close']
        else:
            logger.error("Failed to parse closing prices from Yahoo Finance.")
            return pd.DataFrame()
            
        # Rename columns for our ML pipeline
        macro_df = macro_close.rename(columns={"DX-Y.NYB": "dxy_close", "^TNX": "us10y_yield"})
        
        # 3. Clean and Align the Index
        # yfinance returns timezone-aware timestamps (US/Eastern). 
        # We MUST convert them to UTC to match our Binance CCXT data perfectly.
        if macro_df.index.tz is not None:
            macro_df.index = macro_df.index.tz_convert('UTC')
        else:
            macro_df.index = macro_df.index.tz_localize('UTC')
            
        # Remove the timezone object to make it naive UTC (matches CCXT output)
        macro_df.index = macro_df.index.tz_localize(None)

        # 4. Resample to 4-Hour Timeframe and Forward-Fill the Weekends
        logger.info("Resampling macro data to 4H and handling weekend gaps...")
        
        # We resample to 4H taking the last available price in that 4H window
        macro_4h = macro_df.resample('4h').last()
        
        # Forward-fill (ffill) ensures Friday afternoon's closing price populates Saturday and Sunday
        macro_4h_filled = macro_4h.ffill()
        
        # Drop any initial NaNs at the very start of the dataset
        macro_4h_filled.dropna(inplace=True)
        
        logger.info(f"Successfully compiled {len(macro_4h_filled)} rows of Macro data.")
        return macro_4h_filled

    except Exception as e:
        logger.error(f"Failed to fetch macro data: {e}", exc_info=True)
        return pd.DataFrame()

if __name__ == "__main__":
    # Test the fetcher locally
    df_macro = fetch_macro_data(days_back=10)
    
    if not df_macro.empty:
        logger.info(f"\n--- Macro Data Head ---\n{df_macro.head()}")
        logger.info(f"\n--- Macro Data Tail ---\n{df_macro.tail()}")