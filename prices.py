#!/usr/bin/env python3
"""
DailyMarketCheck Prices Update
Runs every minute during market hours (9 AM - 5 PM ET weekdays).
Fetches live prices from Finnhub and updates ticker + sidebar only.
Does NOT regenerate news articles or other content.
"""
import os, re, requests
from datetime import datetime, timezone

FINNHUB_API_KEY = os.environ.get("FINNHUB_API_KEY", "")
FINNHUB_BASE = "https://finnhub.io/api/v1"
OUTPUT_FILE = "index.html"

# Symbols for ticker tape
TICKER_SYMBOLS = [
    ("SPY", "SPY"), ("QQQ", "QQQ"), ("DIA", "DIA"), ("IWM", "IWM"),
    ("AAPL", "AAPL"), ("NVDA", "NVDA"), ("MSFT", "MSFT"), ("AMZN", "AMZN"),
    ("TSLA", "TSLA"), ("GOOGL", "GOOGL"), ("META", "META"),
    ("BTC", "BINANCE:BTCUSDT"), ("ETH", "BINANCE:ETHUSDT"), ("GLD", "GLD"),
]

# Symbols for sidebar Market Snapshot
SIDEBAR_INDICES = [
    ("S&P 500", "SPY"), ("Nasdaq", "QQQ"), ("Dow Jones", "DIA"), 
    ("Russell 2000", "IWM"), ("10-Yr Yield", "TLT"), ("Gold", "GLD"), 
    ("WTI Oil", "USO"), ("Bitcoin", "BINANCE:BTCUSDT"),
]

def get_quote(symbol):
    """Fetch price data from Finnhub."""
    if not FINNHUB_API_KEY:
        return None
    try:
        r = requests.get(f"{FINNHUB_BASE}/quote", 
                        params={"symbol": symbol, "token": FINNHUB_API_KEY}, timeout=5)
        if r.status_code == 200:
            data = r.json()
            return data if data.get("c", 0) != 0 else None
    except:
        pass
    return None

def update_html():
    """Read index.html, update prices, write back."""
    if not os.path.exists(OUTPUT_FILE):
        print(f"Error: {OUTPUT_FILE} not found")
        return False
    
    if not FINNHUB_API_KEY:
        print("Error: FINNHUB_API_KEY not set")
        return False
    
    print("Fetching prices...")
    
    # Build ticker HTML
    ticker_html = ""
    for display, symbol in TICKER_SYMBOLS:
        q = get_quote(symbol)
        if not q:
            continue
        dp = q.get("dp", 0)
        arrow = "▲" if dp >= 0 else "▼"
        color = "up" if dp >= 0 else "dn"
        ticker_html += f'<span class="ticker-item"><span class="sym">{display}</span> <span class="{color}">{arrow} {abs(dp):.2f}%</span></span>\n    '
    
    # Build sidebar HTML
    sidebar_html = ""
    for display, symbol in SIDEBAR_INDICES:
        q = get_quote(symbol)
        if not q:
            sidebar_html += f'<div class="market-item"><span class="market-name">{display}</span><span class="market-val">—</span></div>\n          '
            continue
        dp = q.get("dp", 0)
        arrow = "▲" if dp >= 0 else "▼"
        color = "up" if dp >= 0 else "dn"
        fmt = f"{arrow} {abs(dp):.2f}%"
        sidebar_html += f'<div class="market-item"><span class="market-name">{display}</span><span class="market-val {color}">{fmt}</span></div>\n          '
    
    if not ticker_html or not sidebar_html:
        print("No price data fetched")
        return False
    
    # Read and update HTML
    try:
        with open(OUTPUT_FILE, "r", encoding="utf-8") as f:
            content = f.read()
        
        # Replace ticker
        ticker_pat = re.compile(r'(<div class="ticker-inner" id="ticker">\s*\n).*?(\s*</div>\s*\n</div>\s*\n\s*\n<!-- Masthead)', re.DOTALL)
        content = ticker_pat.sub(r'\1    ' + ticker_html + r'\2', content)
        
        # Replace sidebar
        sidebar_pat = re.compile(r'(<div class="sidebar-title">Market Snapshot</div>\s*\n\s*).*?(<div style="font-family:var\(--mono\);[^>]*>.*?\* Live data via Finnhub</div>)', re.DOTALL)
        content = sidebar_pat.sub(r'\1          ' + sidebar_html + r'\2', content)
        
        # Update timestamp
        now = datetime.now(timezone.utc).strftime("%B %d, %Y · %H:%M UTC")
        ts_pat = re.compile(r'(Updated: )[^<]+')
        content = ts_pat.sub(r'\1' + now, content, count=1)
        
        with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
            f.write(content)
        
        print(f"✓ Updated {OUTPUT_FILE}")
        return True
    except Exception as e:
        print(f"Error: {e}")
        return False

if __name__ == "__main__":
    success = update_html()
    exit(0 if success else 1)
