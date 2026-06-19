from services.binance import connect_to_binance
from services.binance import fetch_market_data

active_exchange = connect_to_binance()
df_btc = fetch_market_data(
    active_exchange,
    "BTC/USDT",
    "1h",
    "data/binance"
)

print(f"Dataframe: \n{df_btc}")


