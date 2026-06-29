import pandas as pd
import requests
from io import StringIO
from logs import get_core_logger

logger = get_core_logger("InsiderTrading")

def check_insider_buying(ticker: str, min_buy_value: int = 250000) -> dict:
    """
    Scrapes aggregated SEC Form 4 filings to detect recent Insider Buying.
    Filters out stock grants/sales and only looks for open-market BUYS.
    
    Returns a dictionary with a boolean flag for the C++ engine and 
    a text context string for the LLM.
    """
    logger.info(f"Scanning SEC Form 4 insider transactions for {ticker}...")
    
    # We use Finviz as our SEC Form 4 aggregator because it renders a clean HTML table
    url = f"https://finviz.com/quote.ashx?t={ticker}"
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
    }
    
    try:
        response = requests.get(url, headers=headers, timeout=10)
        response.raise_for_status()
        
        # Parse the HTML to extract all tables
        html_buffer = StringIO(response.text)
        tables = pd.read_html(html_buffer)
        
        insider_df = None
        
        # Hunt for the specific Insider Trading table 
        # (It typically has 9 columns and starts with the header 'Insider Trading')
        for df in tables:
            if len(df.columns) == 9 and df.iloc[0, 0] == 'Insider Trading':
                # Promote the first row to be the actual column headers
                df.columns = df.iloc[0]
                insider_df = df[1:].copy()
                break
                
        if insider_df is None or insider_df.empty:
            logger.info(f"No insider trading data found for {ticker}.")
            return {"insider_buy_spike": False, "context": "No recent insider transactions."}
            
        # 1. Filter out options exercises and sales. We ONLY want 'Buy' transactions.
        buys = insider_df[insider_df['Transaction'] == 'Buy'].copy()
        
        if buys.empty:
            logger.info(f"No insider BUYS detected for {ticker} recently.")
            return {"insider_buy_spike": False, "context": "Only sales or no transactions detected."}
            
        # 2. Clean the 'Value ($)' column (remove commas and convert to float for math)
        buys['Value ($)'] = buys['Value ($)'].astype(str).str.replace(',', '').astype(float)
        
        # 3. Calculate total capital deployed by insiders recently
        total_buy_value = buys['Value ($)'].sum()
        logger.info(f"{ticker}: Detected ${total_buy_value:,.2f} in recent insider buying.")
        
        # 4. Determine if this crosses our institutional threshold
        if total_buy_value >= min_buy_value:
            # Extract who bought it (e.g., 'Chief Executive Officer', 'Director')
            roles = buys['Relationship'].unique().tolist()
            roles_str = ", ".join(roles)
            
            context = f"BULLISH CATALYST: Massive Insider Buying Detected! Total Value: ${total_buy_value:,.2f}. Buyers include: {roles_str}."
            logger.info(f"Alpha Signal Generated: {context}")
            
            return {"insider_buy_spike": True, "context": context}
        else:
            return {"insider_buy_spike": False, "context": f"Minor insider buying (${total_buy_value:,.2f}), below threshold."}
            
    except Exception as e:
        logger.error(f"Error fetching insider data for {ticker}: {e}")
        return {"insider_buy_spike": False, "context": "Failed to fetch SEC Form 4 data."}

if __name__ == "__main__":
    # Test the module natively. 
    # (Note: Insider buying is rare. Most stocks will return False on any given day).
    test_ticker = "TSLA" 
    print(f"\n--- Testing Insider Trading Alpha for {test_ticker} ---")
    
    result = check_insider_buying(test_ticker, min_buy_value=100_000)
    
    print("\n--- Payload for the LLM ---")
    print(result)