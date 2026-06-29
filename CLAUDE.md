# Quantitative Trading System — Project Rules

## Vision

**AI-powered Bloomberg Terminal.**

A real-time financial intelligence platform that ingests market data, runs quantitative analysis, and uses AI models (and future AI agents with specialized financial skills) to surface investment suggestions to the human operator. Not a black-box autonomous bot — a co-pilot.

Two layers:
1. **Terminal/Dashboard** — live data display, charts, alerts (Bloomberg-style UI)
2. **AI Intelligence** — LLM analysis + quantitative signals → investment recommendations

Future: Multi-agent system where specialized agents handle distinct tasks (news analyst agent, technicals agent, fundamentals agent, risk officer agent) and a coordinator synthesizes their outputs.

## Current Phase

Building the data pipeline and quantitative engine that will feed the terminal.
Goal of trading strategies: beat options writing yields (1-3%/mo) — accepts 25-35% max drawdown.

## Architecture

```
[Python Orchestration Layer]
       ↓ (normalized CSV)
[C++ Engine: feature calc + backtesting]
       ↓ (features.json)
[Local LLM via Ollama: signal generation]
       ↓
[Python Execution: paper/live orders via CCXT]
```

### Python Layer — Orchestration & Data
- `services/binance/binance_connector.py` — authenticated CCXT connection
- `services/binance/binance_data_fetcher.py` — OHLCV spot data, paginated
- `services/binance/binance_futures_fetcher.py` — Open Interest + Funding Rates (Binance Futures)
- `services/yahoo_finance/yf_macro_regime_fetcher.py` — DXY + US10Y at 4H (ffill weekends)
- `services/news/news_fetcher.py` — CryptoPanic (crypto) + Alpaca/Benzinga (TradFi)
- `services/screen/equity_screen.py` — programmatic Finviz: S&P 500 screener by volume spike + volatility
- `features/feature_engineer.py` — ATR(14), volume/returns Z-scores, autocorr lag-1/4, Hurst exponent, LLM payload builder
- `logs/logger.py` — centralized logger; all modules call `get_core_logger("ModuleName")`
- `master_pipeline.py` — async state machine (STUB — not implemented)
- `main.py` — simple BTC/USDT 1H test pipeline

### C++ Layer — Heavy Math (NOT YET BUILT)
Event-driven backtester classes:
- `DataFeeder` — reads normalized CSV, ticks forward one candle at a time
- `BrokerSimulator` — fees (0.04% maker/taker), slippage (0.1% fill penalty), margin manager
- `StrategyBase` — pluggable strategy logic listening to DataFeeder events
- `PerformanceMetrics` — Sharpe, Sortino, MaxDD, Win/Loss → `backtest_results.json`

C++ indicators (offloaded for speed):
- VWAP (institutional price benchmark)
- CVD — Cumulative Volume Delta (buy vs sell aggression)
- Keltner Channels (volatility squeeze detection)
- Skewness + Kurtosis (fat-tail regime)

## Tech Stack
- **Language:** Python 3.12
- **Data:** CCXT (Binance), yfinance (macro), CryptoPanic API, Alpaca News API
- **ML/Features:** Pandas, NumPy
- **Local LLM:** Ollama (`deepseek-r1` or `qwen3` recommended) on `localhost:11434`
- **Backtesting engine:** C++ (to be written)
- **Env management:** python-dotenv with `find_dotenv()`

## Hard Rules

### No Look-Ahead Bias
When labeling data or merging DataFrames, data at timestamp `t` must only contain info available at or before `t`. Never use future rows to compute past features.

### Normalization Protocol
All data must be on the same 4H grid before the C++ engine or LLM sees it:
- Time align: `resample('4h').ffill()` — crypto 24/7, macro 24/5 (ffill weekends)
- Price → log returns or pct_change (never feed absolute prices like $65,000)
- Volume / OI / ATR → rolling Z-score (100-period lookback)
- Bounded oscillators (RSI, Social Dominance %) → MinMax scaled to [-1, 1]
- Rolling Z-score fitted on training set only; apply to val/test — no leakage

### Target Variable: Triple-Barrier Classification
Predict outcomes (-1, 0, 1), NOT continuous price. Use dynamic ATR-based barriers:
- Class 1 (Long): price hits TP = close + (2 × ATR) first
- Class -1 (Short): price hits SL = close - (1 × ATR) first
- Class 0 (Hold): time expiry (12 candles) without hitting either barrier

### Code Style
- Vectorized Pandas/NumPy — avoid Python loops over DataFrames except where unavoidable (triple-barrier look-ahead)
- Type hints on all functions
- Modules stay isolated: fetchers, features, backtest, execution
- All print statements replaced with `get_core_logger("Name")` calls
- Env vars via `load_dotenv(find_dotenv())`

## Strategies (C++ Engine)

**Strategy A — Volatility Breakout** (Crypto + Equities)
- Entry: Hurst > 0.55 AND Keltner squeeze (width in bottom 10th %) AND Volume Z-score > 2.0
- Direction: Long if close > VWAP; Short if close < VWAP
- Exit: TP = 2×ATR, SL = 1×ATR, time expiry = 12 candles

**Strategy B — Funding Rate Squeeze** (Crypto mean-reversion)
- Entry: Hurst < 0.45 AND 3 consecutive green candles AND Funding Rate > 0.05% AND autocorr lag-1 negative
- Direction: SHORT (bet on retail long liquidation cascade)
- Exit: when Funding Rate returns to baseline

**Strategy C — LLM Sentiment Divergence** (Hybrid)
- Trigger: C++ flags price drop + CVD deeply negative
- LLM check: if news classified "highly_bullish" despite price drop → buy the manipulation dip
- Direction: LONG

**Strategy D — Value-Insider Squeeze** (TradFi equities only)
- Entry: Macro stable (DXY flat, US10Y not spiking) AND stock >20% undervalued (AlphaSpread logic) AND insider buying (SEC Form 4) in last 7 days AND Volume Z-score > 2.0
- Direction: LONG

## Risk Management
- **Kelly Criterion leverage**: 3x–5x when LLM confidence > 90% AND strategy win-rate > 60%
- **Circuit breaker**: portfolio drops 15% from peak → kill all positions, revoke API keys, enter SLEEP state
- **Target**: beat options writing (1-3%/mo) — accepts 25-35% max drawdown

## LLM Integration

Claude API is used as the **Executive Risk Officer** via context injection:
```xml
<technical_data>{ "hurst": 0.62, "volume_zscore": 2.5, "returns_zscore": 1.2 }</technical_data>
<fundamental_catalysts>
- [2026-06-24] Bitcoin ETF record $500M outflow.
</fundamental_catalysts>
```

Claude outputs strict JSON matching this schema:
```json
{
  "signal": -1,
  "confidence_score": 0.87,
  "barriers": { "take_profit_price": 67500.0, "stop_loss_price": 63800.0, "expiration_candles": 12 },
  "thesis_summary": "CVD divergence + bearish news overrides technical oversold."
}
```

> **NOTE:** The Gemini chat described `client.beta.skills.create` with `betas=["skills-2025-10-02"]` — this is a Gemini hallucination. No such Claude API exists. Use system prompts + context injection instead (which is what's implemented above).

Local Ollama is the **primary** inference engine for the async pipeline (no API cost, full privacy).
Claude API is used for high-stakes confirmation and research.

## TradFi Data Sources (Planned)
- **Dynamic screener**: `services/screen/equity_screen.py` (built — S&P 500 via Wikipedia + yfinance)
- **Insider trading**: SEC Form 4 filings (DataRoma logic) — NOT YET BUILT
- **Valuation gap**: AlphaSpread intrinsic value formula — NOT YET BUILT

## Build Status

| Component | Status |
|---|---|
| Binance OHLCV fetcher | Done |
| Binance Futures (OI + Funding) | Done |
| Yahoo Finance macro (DXY, US10Y) | Done |
| Feature engineering (ATR, Hurst, Z-scores, autocorr) | Done |
| News fetcher (CryptoPanic + Alpaca) | Done |
| Equity screener (Finviz logic) | Done |
| Data normalization pipeline | Not built |
| Insider trading (SEC Form 4) | Not built |
| Valuation gap (AlphaSpread) | Not built |
| Async master pipeline | Stub only |
| C++ backtesting engine | Not built |
| Ollama integration | Not built |

## Immediate Next Steps (as agreed with user)
1. DataRoma insider trading logic (SEC Form 4 fetcher)
2. Data normalization pipeline (aligns all sources to 4H grid)
3. C++ engine scaffold (DataFeeder + BrokerSimulator)
4. Ollama async integration in master_pipeline.py