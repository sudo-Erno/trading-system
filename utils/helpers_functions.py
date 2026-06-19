import os
from logs import get_core_logger
from dotenv import load_dotenv, find_dotenv

load_dotenv(find_dotenv())

logger = get_core_logger("HelpersFunctions")

def save_market_data_to_csv(df, symbol, timeframe, save_dir):
    """Save a market data DataFrame to a CSV file in the requested directory."""
    os.makedirs(save_dir, exist_ok=True)
    safe_symbol = symbol.replace('/', '_')
    filename = f"{safe_symbol}_{timeframe}.csv"
    filepath = os.path.join(save_dir, filename)
    df.to_csv(filepath)
    logger.info(f"Data successfully saved to {filepath}")
    return filepath