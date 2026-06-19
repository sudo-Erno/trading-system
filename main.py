from services.binance import connect_to_binance
from services.binance import fetch_market_data
from services.binance import fetch_derivatives_data
from features import engineer_features
from utils import save_market_data_to_csv, save_dataframe_to_csv

import threading

import os
from dotenv import load_dotenv, find_dotenv
load_dotenv(find_dotenv())


SYMBOL = "BTC/USDT"

active_exchange = connect_to_binance()
df_raw_btc = fetch_market_data(
    active_exchange,
    SYMBOL,
    "1h",
    os.getenv("BIANCE_RAW_SAVE_DIR")
)

df_futures_io_btc = fetch_derivatives_data(SYMBOL)
save_dataframe_to_csv(df_futures_io_btc, os.path.join(os.getenv("BINANCE_FUTURE_IO_SAVE_DIR"), "BTC_USDT_FEATURE_IO.csv"))

df_btc = df_raw_btc.join(df_futures_io_btc)
save_dataframe_to_csv(df_btc, os.path.join(os.getenv("BIANCE_SAVE_DIR"), "BTC_USDT.csv"))


df_feature_btc = engineer_features(df_btc, 25)
save_market_data_to_csv(df_feature_btc, SYMBOL, "1h", os.getenv("BINANCE_FEATURE_SAVE_DIR"))

# thread_save_df = threading.Thread(target=save_dataframe_to_csv, args=(df_futures_io_btc, os.getenv("BINANCE_FUTURE_IO_SAVE_DIR")))

# thread_save_df.start()