import asyncio
import os
import json
import aiohttp
import pandas as pd
import yfinance as yf
from enum import Enum, auto
from datetime import datetime

# Import our custom quantitative modules
from services.binance.binance_connector import connect_to_binance
from services.binance.binance_data_fetcher import fetch_market_data
from services.binance.binance_futures_fetcher import fetch_derivatives_data
from services.yahoo_finance.yf_macro_regime_fetcher import fetch_macro_data
from services.screen.equity_screen import screen_equities
from services.dataroma.fetch_dataroma import check_insider_buying
from services.news.news_fetcher import get_news_context
from logs import get_core_logger

logger = get_core_logger("MasterPipeline")

# ---------------------------------------------------------
# 1. Define the States of our Bot
# ---------------------------------------------------------
class BotState(Enum):
    INIT = auto()
    DATA_INGESTION = auto()
    CPP_PROCESSING = auto()
    LLM_REASONING = auto()
    PAPER_EXECUTION = auto()
    SLEEP = auto()
    ERROR = auto()

# ---------------------------------------------------------
# 2. The Asynchronous State Machine
# ---------------------------------------------------------
class TradingStateMachine:
    def __init__(self):
        self.state = BotState.INIT
        self.exchange = connect_to_binance()
        
        # Load configurations from config.json
        self.config = self._load_config()
        
        self.data_dir = self.config['system'].get('data_dir', './data')
        os.makedirs(self.data_dir, exist_ok=True)
        
        # Ollama local server settings dynamically loaded
        self.ollama_url = self.config['llm'].get('ollama_url', "http://localhost:11434/api/generate")
        self.llm_model = self.config['llm'].get('model', "qwen2.5:32b")
        
        # Trading parameters
        self.timeframe = self.config['trading'].get('timeframe', '4h')
        self.days_back = self.config['trading'].get('historical_days_back', 30)
        
        # State memory for the current cycle
        self.active_assets = []      # List of dicts: {'symbol': '...', 'type': '...'}
        self.asset_contexts = {}     # Stores News and Insider signals for the LLM

    def _load_config(self, filepath="./config/master_config.json"):
        """Safely loads the configuration file."""
        try:
            with open(filepath, 'r') as f:
                return json.load(f)
        except FileNotFoundError:
            logger.error(f"Config file {filepath} not found. Using hardcoded safe defaults.")
            # Fallback safe defaults if the file is missing
            return {
                "trading": {"timeframe": "4h", "historical_days_back": 30, "cycle_sleep_seconds": 60},
                "assets": {"crypto": ["BTC/USDT"], "tradfi_dynamic_count": 3},
                "llm": {"ollama_url": "http://localhost:11434/api/generate", "model": "qwen2.5:32b"},
                "system": {"data_dir": "./data"}
            }

    async def run(self):
        """The main infinite loop that drives the state machine."""
        logger.info("Starting Multi-Asset Quantitative State Machine...")
        
        while True:
            try:
                if self.state == BotState.INIT:
                    await self._state_init()
                elif self.state == BotState.DATA_INGESTION:
                    await self._state_ingestion()
                elif self.state == BotState.CPP_PROCESSING:
                    await self._state_cpp_processing()
                elif self.state == BotState.LLM_REASONING:
                    await self._state_llm_reasoning()
                elif self.state == BotState.PAPER_EXECUTION:
                    await self._state_execution()
                elif self.state == BotState.SLEEP:
                    await self._state_sleep()
                elif self.state == BotState.ERROR:
                    logger.error("State Machine hit an unrecoverable error. Shutting down.")
                    break
                    
            except Exception as e:
                logger.error(f"Critical error in state {self.state}: {e}", exc_info=True)
                self.state = BotState.ERROR

    # --- STATE HANDLERS ---

    async def _state_init(self):
        logger.info("[STATE: INIT] System checks passed. Moving to Ingestion.")
        self.state = BotState.DATA_INGESTION

    async def _state_ingestion(self):
        logger.info("[STATE: INGESTION] Aggregating Global Macro & Target Assets...")
        
        # 1. Fetch the Global Macro Regime (DXY, US10Y)
        macro_df = await asyncio.to_thread(fetch_macro_data, self.days_back)
        
        # 2. Dynamic Asset Selection (Finviz Logic)
        dynamic_limit = self.config['assets'].get('tradfi_dynamic_count', 3)
        tradfi_tickers = await asyncio.to_thread(screen_equities, dynamic_limit) 
        
        # 3. Build our target list for this cycle dynamically from config
        self.active_assets = []
        
        # Add Crypto targets from config
        for crypto_ticker in self.config['assets'].get('crypto', []):
            self.active_assets.append({"symbol": crypto_ticker, "type": "crypto"})
            
        # Add TradFi targets from screener
        for ticker in tradfi_tickers:
            self.active_assets.append({"symbol": ticker, "type": "tradfi"})

        self.asset_contexts = {}

        # 4. Ingest data for each specific asset
        for asset in self.active_assets:
            sym = asset['symbol']
            logger.info(f"--- Processing Data for {sym} ---")
            
            if asset['type'] == "crypto":
                # Fetch Spot, Futures, and News
                spot_df = await asyncio.to_thread(fetch_market_data, self.exchange, sym, self.timeframe, self.days_back)
                futures_df = await asyncio.to_thread(fetch_derivatives_data, sym, self.days_back, self.timeframe)
                news = await asyncio.to_thread(get_news_context, sym, "crypto")
                
                # Merge Crypto Data
                master_df = spot_df.join(futures_df, how='left').join(macro_df, how='left').ffill().dropna()
                
                # Store context for LLM
                self.asset_contexts[sym] = {"news": news, "insider_spike": False, "insider_text": ""}
                
            elif asset['type'] == "tradfi":
                # Fetch TradFi Spot (via yfinance), Insider Data, and News
                # Resample daily yfinance data to approximate a comparable DataFrame structure
                yf_data = await asyncio.to_thread(yf.download, sym, period="1mo", interval="1d", progress=False)
                master_df = yf_data.join(macro_df, how='left').ffill().dropna()
                
                insider_data = await asyncio.to_thread(check_insider_buying, sym)
                news = await asyncio.to_thread(get_news_context, sym, "tradfi")
                
                # Store context for LLM
                self.asset_contexts[sym] = {
                    "news": news, 
                    "insider_spike": insider_data['insider_buy_spike'], 
                    "insider_text": insider_data['context']
                }

            # Export normalized data to CSV for the C++ Engine
            safe_sym = sym.replace('/', '_')
            csv_path = os.path.join(self.data_dir, f"{safe_sym}_normalized.csv")
            master_df.to_csv(csv_path)
            logger.info(f"Normalized data saved to {csv_path}")

        self.state = BotState.CPP_PROCESSING

    async def _state_cpp_processing(self):
        logger.info("[STATE: CPP_PROCESSING] Triggering C++ Engine for all assets...")
        
        # In a real environment, we would loop through self.active_assets and 
        # use asyncio.create_subprocess_exec to run the C++ executable on each CSV.
        # For now, we simulate this handoff.
        
        await asyncio.sleep(1) # Simulating C++ calculation time
        logger.info("C++ Feature Engineering & Backtesting completed successfully.")
        
        self.state = BotState.LLM_REASONING

    async def _state_llm_reasoning(self):
        logger.info("[STATE: LLM_REASONING] Consulting Ollama AI for execution signals...")
        
        for asset in self.active_assets:
            sym = asset['symbol']
            context = self.asset_contexts[sym]
            
            # Here we would load the features.json outputted by C++
            cpp_mock_features = '{"hurst": 0.61, "vol_zscore": 2.5, "rsi": 32}'
            
            prompt = f"""You are an institutional quantitative AI. Analyze this asset: {sym}.
            
<technical_and_regime_data>
{cpp_mock_features}
</technical_and_regime_data>

<insider_trading_alpha>
{context['insider_text']}
</insider_trading_alpha>

<fundamental_news>
{context['news']}
</fundamental_news>

Output a strict JSON with "signal" (1, -1, or 0) and "confidence" (0.0 to 1.0).
"""
            # MOCKING LLM CALL for demonstration (to avoid requiring a running Ollama server right now)
            logger.info(f"Sent payload for {sym} to Ollama. Context included: Insider Buying={context['insider_spike']}")
            
        self.state = BotState.PAPER_EXECUTION

    async def _state_execution(self):
        logger.info("[STATE: PAPER_EXECUTION] Simulating Broker Execution...")
        # Evaluate LLM signals and execute paper trades...
        self.state = BotState.SLEEP

    async def _state_sleep(self):
        sleep_time = self.config['trading'].get('cycle_sleep_seconds', 60)
        logger.info(f"[STATE: SLEEP] Cycle complete. Sleeping for {sleep_time} seconds...\n" + "="*50)
        await asyncio.sleep(sleep_time)
        self.state = BotState.DATA_INGESTION

if __name__ == "__main__":
    bot = TradingStateMachine()
    try:
        asyncio.run(bot.run())
    except KeyboardInterrupt:
        logger.info("Bot manually stopped by user.")