from services.screen import screen_equities



print("Initializing Quantitative Equity Screener...")
top_tickers = screen_equities(limit=5)
print(f"\nFinal Ticker List to pass to C++ engine: {top_tickers}")