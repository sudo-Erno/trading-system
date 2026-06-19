from services.binance import connect_to_binance
from services.binance import fetch_market_data
from features import engineer_features
from utils import save_market_data_to_csv

import os
from dotenv import load_dotenv, find_dotenv
load_dotenv(find_dotenv())


active_exchange = connect_to_binance()
df_btc = fetch_market_data(
    active_exchange,
    "BTC/USDT",
    "1h",
    os.getenv("BIANCE_RAW_SAVE_DIR")
)

df_feature_btc = engineer_features(df_btc, 25)
save_market_data_to_csv(df_feature_btc, "BTC/USDT", "1h", os.getenv("BINANCE_FEATURE_SAVE_DIR"))

print(f"Features: \n{df_feature_btc}")


