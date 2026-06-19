import pandas as pd
import numpy as np
import json
from logs import get_core_logger

# Initialize our centralized logger
logger = get_core_logger("FeatureEngineering")

def calculate_atr(df, period=14):
    """Calculates the Average True Range (ATR) for volatility-adjusted barriers."""
    high_low = df['high'] - df['low']
    high_close = np.abs(df['high'] - df['close'].shift())
    low_close = np.abs(df['low'] - df['close'].shift())
    
    ranges = pd.concat([high_low, high_close, low_close], axis=1)
    true_range = np.max(ranges, axis=1)
    
    # ATR is the rolling mean of the True Range
    return true_range.rolling(period).mean()

def compute_hurst(ts):
    """
    Core math to calculate the Hurst Exponent.
    H < 0.5: Mean Reverting Market (Fade the extremes)
    H = 0.5: Geometric Brownian Motion (Random Walk / Noise)
    H > 0.5: Trending Market (Momentum Breakout)
    """
    # Require enough data points for a valid log-log regression
    if len(ts) < 20:
        return np.nan
        
    lags = range(2, 20)
    # Calculate the standard deviation of the differenced series
    try:
        tau = [np.std(np.subtract(ts[lag:], ts[:-lag])) for lag in lags]
        # Calculate the slope of the log-log plot
        poly = np.polyfit(np.log(lags), np.log(tau), 1)
        return poly[0]
    except Exception:
        return np.nan

def engineer_features(df, rolling_window=100):
    """
    Takes the raw OHLCV DataFrame and attaches institutional quant metrics.
    """
    logger.info("Starting feature engineering pipeline...")
    df = df.copy()

    # 1. Price Returns (Momentum)
    df['returns'] = df['close'].pct_change()
    
    # 2. Average True Range (Volatility)
    df['atr_14'] = calculate_atr(df, period=14)

    # 3. Rolling Z-Scores (Anomaly Detection)
    # Normalizing volume and returns so the LLM/Neural Net isn't blinded by absolute values
    logger.info("Calculating Rolling Z-Scores...")
    df['volume_zscore'] = (df['volume'] - df['volume'].rolling(rolling_window).mean()) / (df['volume'].rolling(rolling_window).std() + 1e-8)
    df['returns_zscore'] = (df['returns'] - df['returns'].rolling(rolling_window).mean()) / (df['returns'].rolling(rolling_window).std() + 1e-8)

    # 4. Autocorrelation (Market Memory)
    # Does the current 4H candle follow the trend of the previous candle?
    logger.info("Calculating Autocorrelation...")
    df['autocorr_lag1'] = df['returns'].rolling(rolling_window).corr(df['returns'].shift(1))
    df['autocorr_lag4'] = df['returns'].rolling(rolling_window).corr(df['returns'].shift(4))

    # 5. Hurst Exponent (Market Regime)
    # Warning: Using .rolling().apply() with a custom function is computationally heavy.
    # On an H4 timeframe (6 candles a day), this is perfectly fast. 
    logger.info("Calculating Hurst Exponent (This may take a moment)...")
    # We apply it to the log prices, looking back over the last 100 periods
    log_prices = np.log(df['close'])
    df['hurst_exponent'] = log_prices.rolling(window=rolling_window).apply(compute_hurst, raw=True)

    # Drop all the NaNs created by our rolling lookback windows
    df.dropna(inplace=True)
    
    logger.info("Feature engineering complete.")
    return df

def generate_llm_payload(df, ticker="BTC/USDT", timeframe="4h"):
    """
    Extracts the most recent state of the market and formats it into 
    a clean dictionary, ready to be injected into Claude's prompt.
    """
    latest = df.iloc[-1]
    
    payload = {
        "metadata": {
            "ticker": ticker,
            "timeframe": timeframe,
            "timestamp_utc": str(latest.name)
        },
        "price_action": {
            "current_close": float(latest['close']),
            "returns_pct": float(latest['returns']),
            "returns_zscore": float(latest['returns_zscore']),
            "volume_zscore": float(latest['volume_zscore'])
        },
        "market_regime": {
            "atr_14": float(latest['atr_14']),
            "hurst_exponent": float(latest['hurst_exponent']),
            "autocorrelation_lag1": float(latest['autocorr_lag1']),
            "autocorrelation_lag4": float(latest['autocorr_lag4'])
        }
    }
    
    return json.dumps(payload, indent=2)

if __name__ == "__main__":
    # Mocking a small DataFrame to test the logic
    # In production, you import fetch_market_data from data_fetcher.py here
    logger.info("Generating mock data for testing...")
    dates = pd.date_range(end=pd.Timestamp.utcnow(), periods=500, freq='4h')
    mock_data = {
        'open': np.random.uniform(60000, 65000, 500),
        'high': np.random.uniform(65000, 66000, 500),
        'low': np.random.uniform(59000, 60000, 500),
        'close': np.random.uniform(60000, 65000, 500),
        'volume': np.random.uniform(100, 1000, 500)
    }
    raw_df = pd.DataFrame(mock_data, index=dates)

    # 1. Run the engineering pipeline
    featured_df = engineer_features(raw_df, rolling_window=100)

    # 2. Generate the LLM Payload
    llm_json_string = generate_llm_payload(featured_df)
    
    logger.info("\n--- LLM Context Payload generated successfully! ---")
    
    # This string is what you will wrap in <market_data> tags and send to Claude
    print(f"<market_data>\n{llm_json_string}\n</market_data>")