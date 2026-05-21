#!/usr/bin/env python3
"""
DailyMarketCheck - Financial News Pipeline
Fetches articles from financial RSS feeds, summarizes with Claude AI,
and generates a static site (index.html).
"""

import feedparser
import requests
import json
import re
import os
from datetime import datetime, timezone
from anthropic import Anthropic

# ── CONFIG ────────────────────────────────────────────────────────────────────

SITE_TITLE = "DailyMarketCheck"
SITE_TAGLINE = "Markets · IPOs · Dividends · Bonds · Stocks"
OUTPUT_FILE = "index.html"
MAX_ARTICLES_PER_FEED = 6

# ── FINNHUB CONFIG ────────────────────────────────────────────────────────────
# Live market data: quotes for ticker tape + sidebar + IPO calendar.
# API key from environment (GitHub Actions secret FINNHUB_API_KEY).
# Free tier: 60 calls/minute. We use ~23 per run.

FINNHUB_API_KEY = os.environ.get("FINNHUB_API_KEY", "")
FINNHUB_BASE = "https://finnhub.io/api/v1"

# Ticker tape symbols (scrolling bar at top). Finnhub format.
# Crypto uses BINANCE:BTCUSDT format; ETF/stock use plain ticker.
TICKER_SYMBOLS = [
    ("SPY", "SPY"), ("QQQ", "QQQ"), ("DIA", "DIA"), ("IWM", "IWM"),
    ("AAPL", "AAPL"), ("NVDA", "NVDA"), ("MSFT", "MSFT"), ("AMZN", "AMZN"),
    ("TSLA", "TSLA"), ("GOOGL", "GOOGL"), ("META", "META"),
    ("BTC", "BINANCE:BTCUSDT"), ("ETH", "BINANCE:ETHUSDT"),
    ("GLD", "GLD"),  # Gold ETF as proxy for gold
]

# Sidebar market snapshot — display name + Finnhub symbol + format style.
# style: 'pct' (percent change), 'price' (raw price), 'yield' (treasury yield)
SIDEBAR_INDICES = [
    ("S&P 500",     "SPY",  "price"),   # Using SPY ETF as proxy for S&P 500
    ("Nasdaq",      "QQQ",  "price"),   # QQQ as proxy for Nasdaq-100
    ("Dow Jones",   "DIA",  "price"),   # DIA as proxy for Dow
    ("Russell 2000","IWM",  "price"),   # IWM as proxy for Russell 2000
    ("10-Yr Yield", "TLT",  "price"),   # TLT as bond proxy (not perfect but works on free tier)
    ("Gold",        "GLD",  "price"),   # GLD as gold proxy
    ("WTI Oil",     "USO",  "price"),   # USO as oil proxy
    ("Bitcoin",     "BINANCE:BTCUSDT", "price"),
]


# Financial RSS feeds by category
FEEDS = {
    "Market News": [
        "https://feeds.finance.yahoo.com/rss/2.0/headline?s=^GSPC&region=US&lang=en-US",
        "https://www.marketwatch.com/rss/topstories",
        "https://feeds.a.dj.com/rss/RSSMarketsMain.xml",
        "https://www.cnbc.com/id/100003114/device/rss/rss.html",
        "https://www.investors.com/feed/",
        "https://www.thestreet.com/rss/",
        "https://www.barrons.com/xml/rss/3_7551.xml",
        "https://www.kiplinger.com/rss/",
        "https://feeds.businessinsider.com/custom/all",
        "https://www.forbes.com/investing/feed/",
        "https://morningstar.com/feeds/us/all-feeds.rss",
    ],
    "Stocks": [
        "https://feeds.finance.yahoo.com/rss/2.0/headline?s=AAPL,MSFT,NVDA,AMZN&region=US&lang=en-US",
        "https://www.investing.com/rss/news_25.rss",
        "https://seekingalpha.com/feed.xml",
        "https://www.cnbc.com/id/15839135/device/rss/rss.html",
        "https://www.zacks.com/rss/stockresearch.xml",
        "https://www.fool.com/feeds/index.aspx",
        "https://finance.yahoo.com/rss/topfinstories",
        "https://www.forbes.com/money/feed/",
        "https://www.kiplinger.com/investing/stocks/rss",
        "https://www.thestreet.com/rss/stocks",
        "https://feeds.businessinsider.com/custom/markets",
    ],
    "IPOs": [
        "https://feeds.finance.yahoo.com/rss/2.0/headline?s=ipo&region=US&lang=en-US",
        "https://www.renaissancecapital.com/review/ipoweekly.rss",
        "https://www.iposcoop.com/rss/",
        "https://www.cnbc.com/id/10000664/device/rss/rss.html",
        "https://www.forbes.com/ipo/feed/",
        "https://www.thestreet.com/rss/ipo",
        "https://www.investing.com/rss/news_577.rss",
    ],
    "Dividends": [
        "https://feeds.finance.yahoo.com/rss/2.0/headline?s=dividend&region=US&lang=en-US",
        "https://www.dividend.com/rss/news/",
        "https://dividendgrowthinvestor.com/feed/",
        "https://seekingalpha.com/tag/dividends.xml",
        "https://www.fool.com/feeds/index.aspx?id=dividends",
        "https://simplysafedividends.com/feed",
        "https://www.kiplinger.com/investing/dividends/rss",
        "https://www.thestreet.com/rss/dividends",
        "https://www.forbes.com/dividends/feed/",
    ],
    "Bonds & Fixed Income": [
        "https://feeds.a.dj.com/rss/RSSBonds.xml",
        "https://www.treasurydirect.gov/rss/news.xml",
        "https://feeds.finance.yahoo.com/rss/2.0/headline?s=^TNX&region=US&lang=en-US",
        "https://www.cnbc.com/id/20910258/device/rss/rss.html",
        "https://www.investing.com/rss/news_285.rss",
        "https://www.kiplinger.com/investing/bonds/rss",
        "https://www.thestreet.com/rss/fixed-income",
    ],
    "ETFs": [
        "https://etfdb.com/rss.xml",
        "https://feeds.finance.yahoo.com/rss/2.0/headline?s=SPY,QQQ,IWM&region=US&lang=en-US",
        "https://www.etf.com/rss.xml",
        "https://seekingalpha.com/tag/etf-portfolio-strategy.xml",
        "https://www.cnbc.com/id/100727362/device/rss/rss.html",
        "https://www.kiplinger.com/investing/etfs/rss",
        "https://www.thestreet.com/rss/etfs",
        "https://www.forbes.com/etfs/feed/",
    ],
    "Crypto": [
        "https://cointelegraph.com/rss",
        "https://www.coindesk.com/arc/outboundfeeds/rss/",
        "https://feeds.finance.yahoo.com/rss/2.0/headline?s=BTC-USD,ETH-USD&region=US&lang=en-US",
        "https://decrypt.co/feed",
        "https://www.cnbc.com/id/100762479/device/rss/rss.html",
        "https://bitcoinmagazine.com/.rss/full/",
        "https://www.forbes.com/crypto-blockchain/feed/",
        "https://cryptoslate.com/feed/",
        "https://ambcrypto.com/feed/",
        "https://www.theblock.co/rss.xml",
    ],
    "Economy & Fed": [
        "https://feeds.a.dj.com/rss/RSSEconomy.xml",
        "https://feeds.finance.yahoo.com/rss/2.0/headline?s=economy+fed+rates&region=US&lang=en-US",
        "https://www.federalreserve.gov/feeds/press_all.xml",
        "https://home.treasury.gov/news/press-releases/feed",
        "https://www.cnbc.com/id/20910258/device/rss/rss.html",
        "https://www.investing.com/rss/news_14.rss",
        "https://www.kiplinger.com/economy/rss",
        "https://www.forbes.com/economy/feed/",
        "https://feeds.businessinsider.com/custom/economy",
    ],
    "Earnings": [
        "https://feeds.finance.yahoo.com/rss/2.0/headline?s=earnings&region=US&lang=en-US",
        "https://www.cnbc.com/id/15839135/device/rss/rss.html",
        "https://seekingalpha.com/tag/earnings.xml",
        "https://www.zacks.com/rss/earnings.xml",
        "https://www.thestreet.com/rss/earnings",
        "https://www.fool.com/feeds/index.aspx?id=earnings",
        "https://www.investing.com/rss/news_25.rss",
    ],
    "Real Estate & REITs": [
        "https://feeds.finance.yahoo.com/rss/2.0/headline?s=reit&region=US&lang=en-US",
        "https://www.investing.com/rss/news_15.rss",
        "https://seekingalpha.com/tag/reits.xml",
        "https://www.thestreet.com/rss/real-estate",
        "https://www.kiplinger.com/real-estate/rss",
        "https://www.forbes.com/real-estate/feed/",
        "https://feeds.businessinsider.com/custom/real-estate",
        "https://www.fool.com/feeds/index.aspx?id=real-estate",
    ],
    "Global Markets": [
        "https://feeds.a.dj.com/rss/RSSWorldNews.xml",
        "https://www.cnbc.com/id/100727362/device/rss/rss.html",
        "https://feeds.finance.yahoo.com/rss/2.0/headline?s=^FTSE,^N225,^HSI&region=US&lang=en-US",
        "https://www.investing.com/rss/news_285.rss",
        "https://www.forbes.com/global-markets/feed/",
        "https://feeds.businessinsider.com/custom/international",
        "https://www.thestreet.com/rss/global",
        "https://www.ft.com/global-economy?format=rss",
    ],
    "Personal Finance": [
        "https://www.kiplinger.com/personal-finance/rss",
        "https://www.forbes.com/personal-finance/feed/",
        "https://feeds.businessinsider.com/custom/personal-finance",
        "https://www.fool.com/feeds/index.aspx?id=personal-finance",
        "https://www.cnbc.com/id/10000664/device/rss/rss.html",
        "https://www.thestreet.com/rss/personal-finance",
        "https://www.investopedia.com/feedbuilder/feed/getFeed?feedName=rss_personal-finance",
    ],
}

# IPO calendar data (static/curated — update weekly)
IPO_CALENDAR = [
    {"company": "Check pipeline for latest IPO calendar", "ticker": "—", "date": "Updated weekly", "exchange": "NYSE/NASDAQ", "expected_price": "—", "sector": "—"},
]

# Top dividend stocks (static/curated — update monthly)
TOP_DIVIDEND_STOCKS = [
    {"ticker": "T",   "company": "AT&T",         "yield": "6.8%", "sector": "Telecom"},
    {"ticker": "MO",  "company": "Altria Group",  "yield": "8.2%", "sector": "Consumer"},
    {"ticker": "VZ",  "company": "Verizon",       "yield": "6.5%", "sector": "Telecom"},
    {"ticker": "PFE", "company": "Pfizer",        "yield": "5.9%", "sector": "Healthcare"},
    {"ticker": "KMI", "company": "Kinder Morgan", "yield": "6.1%", "sector": "Energy"},
    {"ticker": "ABBV","company": "AbbVie",        "yield": "3.8%", "sector": "Healthcare"},
    {"ticker": "CVX", "company": "Chevron",       "yield": "4.2%", "sector": "Energy"},
    {"ticker": "IBM", "company": "IBM",           "yield": "3.3%", "sector": "Technology"},
]

# ── HELPERS ───────────────────────────────────────────────────────────────────

client = Anthropic()

def clean_html(text):
    """Strip HTML tags from text."""
    return re.sub(r'<[^>]+>', '', text or '').strip()

def fetch_feed(url):
    """Fetch and parse an RSS feed."""
    try:
        feed = feedparser.parse(url)
        return feed.entries[:MAX_ARTICLES_PER_FEED]
    except Exception as e:
        print(f"  ⚠ Feed error {url}: {e}")
        return []

def summarize(title, description):
    """Use Claude to write a concise financial news summary."""
    prompt = f"""You are a financial news editor. Write a 2-sentence summary of this article for a professional audience. Be factual, concise, and highlight market impact. No fluff.

Title: {title}
Content: {description[:800]}

Return only the 2-sentence summary. No preamble."""
    try:
        resp = client.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=120,
            messages=[{"role": "user", "content": prompt}]
        )
        return resp.content[0].text.strip()
    except Exception as e:
        print(f"  ⚠ AI error: {e}")
        return clean_html(description)[:200] + "..."

def _parse_pub_date(entry):
    """Best-effort parse of a feed entry's publish date for sorting. Newer = higher."""
    # feedparser usually populates published_parsed or updated_parsed as time.struct_time
    for key in ("published_parsed", "updated_parsed"):
        val = entry.get(key)
        if val:
            try:
                return datetime(*val[:6])
            except Exception:
                pass
    return datetime.min  # undated entries sort last

def _finnhub_quote(symbol):
    """Fetch a single quote from Finnhub. Returns dict with c,d,dp,pc or None on failure."""
    if not FINNHUB_API_KEY:
        return None
    try:
        url = f"{FINNHUB_BASE}/quote"
        resp = requests.get(url, params={"symbol": symbol, "token": FINNHUB_API_KEY}, timeout=8)
        if resp.status_code != 200:
            print(f"  ⚠ Finnhub {symbol}: HTTP {resp.status_code}")
            return None
        data = resp.json()
        # Finnhub returns {c: 0} for invalid symbols; treat as failure
        if data.get("c", 0) == 0:
            return None
        return data
    except Exception as e:
        print(f"  ⚠ Finnhub {symbol} error: {e}")
        return None

def _finnhub_ipo_calendar():
    """Fetch upcoming IPOs from Finnhub for the next 30 days."""
    if not FINNHUB_API_KEY:
        return []
    try:
        from datetime import timedelta
        today = datetime.now().date()
        to_date = today + timedelta(days=30)
        url = f"{FINNHUB_BASE}/calendar/ipo"
        resp = requests.get(
            url,
            params={
                "from": today.isoformat(),
                "to": to_date.isoformat(),
                "token": FINNHUB_API_KEY,
            },
            timeout=8,
        )
        if resp.status_code != 200:
            print(f"  ⚠ Finnhub IPO calendar: HTTP {resp.status_code}")
            return []
        data = resp.json()
        return data.get("ipoCalendar", []) or []
    except Exception as e:
        print(f"  ⚠ Finnhub IPO error: {e}")
        return []

def fetch_market_data():
    """Fetch live market data from Finnhub for ticker tape, sidebar, IPO calendar.

    Returns dict with keys: ticker_items, sidebar_items, ipo_rows.
    Each list contains pre-formatted dicts ready to render. Falls back to
    hardcoded defaults if Finnhub is unavailable so the site never breaks.
    """
    print("\n💹 Fetching live market data from Finnhub...")

    if not FINNHUB_API_KEY:
        print("  ⚠ FINNHUB_API_KEY not set — using hardcoded fallback values")
        return _market_data_fallback()

    # 1. Ticker tape quotes
    ticker_items = []
    for display, symbol in TICKER_SYMBOLS:
        q = _finnhub_quote(symbol)
        if q is None:
            continue
        price = q.get("c", 0)
        dp = q.get("dp", 0)  # daily percent change
        direction = "up" if dp >= 0 else "dn"
        arrow = "▲" if dp >= 0 else "▼"
        ticker_items.append({
            "sym": display,
            "val": f"{arrow} {abs(dp):.2f}%",
            "dir": direction,
        })
        print(f"  ✓ {display}: ${price:.2f} ({dp:+.2f}%)")

    # If we got nothing useful, fall back entirely
    if not ticker_items:
        print("  ⚠ No ticker data — falling back to hardcoded values")
        return _market_data_fallback()

    # 2. Sidebar index quotes
    sidebar_items = []
    for display, symbol, style in SIDEBAR_INDICES:
        q = _finnhub_quote(symbol)
        if q is None:
            # Keep a placeholder entry rather than dropping the row
            sidebar_items.append({"name": display, "val": "—", "dir": ""})
            continue
        price = q.get("c", 0)
        dp = q.get("dp", 0)
        direction = "up" if dp >= 0 else "dn"
        arrow = "▲" if dp >= 0 else "▼"
        # Format price differently for crypto (large numbers) vs ETFs (smaller)
        if price >= 10000:
            formatted = f"{arrow} ${price:,.0f}"
        elif price >= 100:
            formatted = f"{arrow} {price:,.2f}"
        else:
            formatted = f"{arrow} ${price:.2f}"
        sidebar_items.append({"name": display, "val": formatted, "dir": direction})

    # 3. IPO calendar
    ipos = _finnhub_ipo_calendar()
    ipo_rows = []
    for ipo in ipos[:15]:  # cap at 15 to keep table manageable
        symbol = ipo.get("symbol") or "—"
        name = ipo.get("name", "—")
        date = ipo.get("date", "—")
        exchange = ipo.get("exchange", "—")
        price_range = ipo.get("price", "—") or "—"
        # Finnhub doesn't return sector directly; leave blank
        ipo_rows.append({
            "ticker": symbol,
            "company": name,
            "date": date,
            "exchange": exchange,
            "expected_price": f"${price_range}" if price_range != "—" else "—",
            "sector": "—",
        })
    print(f"  ✓ IPO calendar: {len(ipo_rows)} upcoming IPOs")

    return {
        "ticker_items": ticker_items,
        "sidebar_items": sidebar_items,
        "ipo_rows": ipo_rows,
    }

def _market_data_fallback():
    """Hardcoded fallback values if Finnhub is unavailable. Keeps site from breaking."""
    return {
        "ticker_items": [
            {"sym": "SPY", "val": "▲ 0.38%", "dir": "up"},
            {"sym": "QQQ", "val": "▲ 0.62%", "dir": "up"},
            {"sym": "DIA", "val": "▼ 0.11%", "dir": "dn"},
            {"sym": "IWM", "val": "▲ 0.24%", "dir": "up"},
            {"sym": "AAPL", "val": "▲ 1.20%", "dir": "up"},
            {"sym": "NVDA", "val": "▲ 2.40%", "dir": "up"},
            {"sym": "MSFT", "val": "▼ 0.30%", "dir": "dn"},
            {"sym": "AMZN", "val": "▲ 0.90%", "dir": "up"},
            {"sym": "TSLA", "val": "▼ 1.10%", "dir": "dn"},
            {"sym": "BTC", "val": "▲ 3.10%", "dir": "up"},
            {"sym": "GLD", "val": "▲ 0.50%", "dir": "up"},
        ],
        "sidebar_items": [
            {"name": "S&P 500",      "val": "▲ 531.24", "dir": "up"},
            {"name": "Nasdaq",       "val": "▲ 467.13", "dir": "up"},
            {"name": "Dow Jones",    "val": "▼ 391.18", "dir": "dn"},
            {"name": "Russell 2000", "val": "▲ 204.13", "dir": "up"},
            {"name": "10-Yr Yield",  "val": "4.42%",    "dir": ""},
            {"name": "Gold",         "val": "▲ $2,418", "dir": "up"},
            {"name": "WTI Oil",      "val": "▼ $78.12", "dir": "dn"},
            {"name": "Bitcoin",      "val": "▲ $68,420","dir": "up"},
        ],
        "ipo_rows": [],
    }

def fetch_all_articles():
    """Fetch articles from all feeds, categorized.

    Strategy: round-robin across feeds within each category for source diversity.
    Pre-fetch every feed, sort each by publish date (newest first), then take one
    article per feed in rotation until the category cap is reached. This ensures
    every curated feed gets a chance to contribute before any single feed dominates.
    """
    CATEGORY_CAP = 8  # max articles displayed per category
    all_data = {}

    for category, urls in FEEDS.items():
        print(f"\n📡 Fetching: {category}")

        # Pre-fetch + sort every feed in this category
        feed_queues = []  # list of (source_label, [sorted entries])
        for url in urls:
            entries = fetch_feed(url)
            if not entries:
                continue
            try:
                entries = sorted(entries, key=_parse_pub_date, reverse=True)
            except Exception:
                pass  # if sort fails, fall back to original order
            source_label = url.split("/")[2].replace("www.", "").replace("feeds.", "")
            feed_queues.append((source_label, list(entries)))

        # Round-robin: cycle through feeds taking one article each pass
        articles = []
        seen_titles = set()
        while len(articles) < CATEGORY_CAP and any(q for _, q in feed_queues):
            for source_label, queue in feed_queues:
                if len(articles) >= CATEGORY_CAP:
                    break
                if not queue:
                    continue
                entry = queue.pop(0)
                title = clean_html(entry.get("title", ""))
                if not title or title in seen_titles:
                    continue
                seen_titles.add(title)
                link = entry.get("link", "#")
                description = clean_html(entry.get("summary", entry.get("description", "")))
                pub = entry.get("published", entry.get("updated", ""))
                print(f"  ✓ [{source_label}] {title[:55]}...")
                summary = summarize(title, description)
                articles.append({
                    "title": title,
                    "link": link,
                    "summary": summary,
                    "pub": pub,
                    "source": source_label,
                })

        all_data[category] = articles
        unique_sources = len({a["source"] for a in articles})
        print(f"  → {len(articles)} articles from {unique_sources} sources")

    return all_data

# ── HTML GENERATION ───────────────────────────────────────────────────────────

def build_html(articles_by_category, market_data=None):
    now = datetime.now(timezone.utc).strftime("%B %d, %Y · %H:%M UTC")

    # Fallback to defaults if market_data not provided
    if market_data is None:
        market_data = _market_data_fallback()

    # Build ticker tape HTML from live data — duplicated for seamless scroll loop
    ticker_items_html = ""
    for _ in range(2):  # duplicate the loop so the scroll animation feels seamless
        for item in market_data["ticker_items"]:
            ticker_items_html += (
                f'<span class="ticker-item">'
                f'<span class="sym">{item["sym"]}</span> '
                f'<span class="{item["dir"]}">{item["val"]}</span>'
                f'</span>\n    '
            )

    # Build sidebar market snapshot HTML from live data
    sidebar_items_html = ""
    for item in market_data["sidebar_items"]:
        dir_class = item["dir"]
        # Escape ampersand for HTML safety (matches original markup style)
        safe_name = item["name"].replace("&", "&amp;")
        sidebar_items_html += (
            f'<div class="market-item">'
            f'<span class="market-name">{safe_name}</span>'
            f'<span class="market-val {dir_class}">{item["val"]}</span>'
            f'</div>\n          '
        )

    # IPO rows: use live data if available, else fall back to static IPO_CALENDAR
    live_ipo_rows = market_data.get("ipo_rows") or []
    ipo_source = live_ipo_rows if live_ipo_rows else IPO_CALENDAR

    # Build article cards per category
    category_sections = ""
    category_nav_items = ""
    all_categories = list(articles_by_category.keys())

    for i, category in enumerate(all_categories):
        articles = articles_by_category[category]
        cat_id = category.lower().replace(" ", "-").replace("&", "and")
        active = "active" if i == 0 else ""
        category_nav_items += f'<button class="cat-btn {active}" onclick="showCat(\'{cat_id}\')" id="catbtn-{cat_id}">{category}</button>\n'

        cards = ""
        for art in articles:
            cards += f"""
            <a class="article-card" href="{art['link']}" target="_blank" rel="noopener">
              <div class="card-source">{art['source']}</div>
              <div class="card-title">{art['title']}</div>
              <div class="card-summary">{art['summary']}</div>
              <div class="card-footer">
                <span class="card-date">{art['pub'][:16] if art['pub'] else ''}</span>
                <span class="card-read">Read →</span>
              </div>
            </a>"""

        display = "block" if i == 0 else "none"
        category_sections += f"""
        <div class="cat-section" id="cat-{cat_id}" style="display:{display}">
          <div class="cat-header"><h2>{category}</h2></div>
          <div class="articles-grid">{cards}</div>
        </div>"""

    # Dividend table rows
    dividend_rows = ""
    for s in TOP_DIVIDEND_STOCKS:
        dividend_rows += f"""
        <tr>
          <td class="ticker">{s['ticker']}</td>
          <td>{s['company']}</td>
          <td class="yield-val">{s['yield']}</td>
          <td><span class="sector-badge">{s['sector']}</span></td>
        </tr>"""

    # IPO calendar rows
    ipo_rows = ""
    for ipo in ipo_source:
        ipo_rows += f"""
        <tr>
          <td class="ticker">{ipo['ticker']}</td>
          <td>{ipo['company']}</td>
          <td>{ipo['date']}</td>
          <td>{ipo['exchange']}</td>
          <td class="ipo-price">{ipo['expected_price']}</td>
          <td><span class="sector-badge">{ipo['sector']}</span></td>
        </tr>"""

    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8"/>
<meta name="viewport" content="width=device-width,initial-scale=1.0"/>
<title>DailyMarketCheck</title>
<link rel="preconnect" href="https://fonts.googleapis.com"/>
<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=IBM+Plex+Serif:ital,wght@0,400;0,600;1,400&family=IBM+Plex+Mono:wght@400;600&family=IBM+Plex+Sans:wght@300;400;500;600&display=swap"/>
<style>
  :root {{
    --black: #0a0a0a;
    --ink: #1a1a1a;
    --dark: #111111;
    --panel: #f5f4f0;
    --border: #d4cfc4;
    --accent: #ff6600;
    --accent2: #0033cc;
    --green: #007a3d;
    --red: #c0392b;
    --gold: #b8860b;
    --text: #1a1a1a;
    --muted: #6b6560;
    --serif: 'IBM Plex Serif', Georgia, serif;
    --sans: 'IBM Plex Sans', Helvetica, sans-serif;
    --mono: 'IBM Plex Mono', monospace;
  }}

  *, *::before, *::after {{ box-sizing: border-box; margin: 0; padding: 0; }}
  html {{ scroll-behavior: smooth; }}

  body {{
    background: #faf9f5;
    color: var(--text);
    font-family: var(--sans);
    font-size: 14px;
    line-height: 1.5;
  }}

  /* ── TOP BAR ── */
  .top-bar {{
    background: var(--black);
    color: #ccc;
    font-family: var(--mono);
    font-size: 11px;
    padding: 4px 20px;
    display: flex;
    justify-content: space-between;
    align-items: center;
    border-bottom: 1px solid #333;
    white-space: nowrap;
    overflow: hidden;
  }}
  .top-bar-left {{ color: #888; }}
  .top-bar-right {{ color: var(--accent); letter-spacing: 0.5px; }}

  /* ── TICKER TAPE ── */
  .ticker-wrap {{
    background: var(--ink);
    overflow: hidden;
    border-bottom: 2px solid var(--accent);
    padding: 6px 0;
  }}
  .ticker-inner {{
    display: flex;
    gap: 40px;
    animation: ticker 60s linear infinite;
    width: max-content;
  }}
  .ticker-item {{
    font-family: var(--mono);
    font-size: 12px;
    color: #ddd;
    white-space: nowrap;
    display: flex;
    gap: 6px;
    align-items: center;
  }}
  .ticker-item .sym {{ color: #fff; font-weight: 600; }}
  .ticker-item .up {{ color: #00c853; }}
  .ticker-item .dn {{ color: #ff3d3d; }}
  @keyframes ticker {{ 0% {{ transform: translateX(0); }} 100% {{ transform: translateX(-50%); }} }}

  /* ── MASTHEAD ── */
  .masthead {{
    background: var(--black);
    color: white;
    text-align: center;
    padding: 28px 20px 20px;
    border-bottom: 4px solid var(--accent);
    position: relative;
  }}
  .masthead-name {{
    font-family: var(--serif);
    font-size: clamp(36px, 6vw, 72px);
    font-weight: 600;
    letter-spacing: -1px;
    line-height: 1;
    color: #fff;
  }}
  .masthead-name span {{ color: var(--accent); }}
  .masthead-tagline {{
    font-family: var(--mono);
    font-size: 11px;
    color: #888;
    letter-spacing: 3px;
    text-transform: uppercase;
    margin-top: 8px;
  }}
  .masthead-date {{
    font-family: var(--mono);
    font-size: 11px;
    color: #666;
    margin-top: 6px;
    border-top: 1px solid #333;
    padding-top: 8px;
  }}

  /* ── NAV ── */
  .main-nav {{
    background: var(--ink);
    border-bottom: 1px solid #333;
    padding: 0 20px;
    display: flex;
    gap: 0;
    overflow-x: auto;
  }}
  .nav-tab {{
    font-family: var(--sans);
    font-size: 12px;
    font-weight: 500;
    color: #aaa;
    padding: 11px 16px;
    cursor: pointer;
    border: none;
    background: none;
    text-transform: uppercase;
    letter-spacing: 0.8px;
    border-bottom: 3px solid transparent;
    white-space: nowrap;
    transition: color 0.15s, border-color 0.15s;
  }}
  .nav-tab:hover {{ color: #fff; }}
  .nav-tab.active {{ color: #fff; border-bottom-color: var(--accent); }}

  /* ── LAYOUT ── */
  .site-wrap {{ max-width: 1400px; margin: 0 auto; padding: 0; }}

  /* ── PAGE ── */
  .page {{ display: none; }}
  .page.active {{ display: block; }}

  /* ── NEWS PAGE ── */
  .news-layout {{
    display: grid;
    grid-template-columns: 1fr 280px;
    gap: 0;
    min-height: 80vh;
  }}
  .news-main {{ border-right: 1px solid var(--border); }}
  .news-sidebar {{ background: var(--panel); }}

  /* Category filter bar */
  .cat-filter {{
    background: var(--panel);
    border-bottom: 1px solid var(--border);
    padding: 8px 20px;
    display: flex;
    gap: 6px;
    overflow-x: auto;
    flex-wrap: nowrap;
  }}
  .cat-btn {{
    font-family: var(--sans);
    font-size: 11px;
    font-weight: 500;
    color: var(--muted);
    background: white;
    border: 1px solid var(--border);
    padding: 4px 10px;
    cursor: pointer;
    border-radius: 2px;
    white-space: nowrap;
    text-transform: uppercase;
    letter-spacing: 0.5px;
    transition: all 0.15s;
  }}
  .cat-btn:hover {{ background: var(--ink); color: white; border-color: var(--ink); }}
  .cat-btn.active {{ background: var(--accent); color: white; border-color: var(--accent); }}

  /* Article grid */
  .articles-grid {{
    display: grid;
    grid-template-columns: repeat(auto-fill, minmax(300px, 1fr));
    gap: 1px;
    background: var(--border);
    border-bottom: 1px solid var(--border);
  }}
  .article-card {{
    background: white;
    padding: 18px 20px;
    text-decoration: none;
    color: var(--text);
    display: flex;
    flex-direction: column;
    gap: 8px;
    transition: background 0.12s;
    border-left: 3px solid transparent;
  }}
  .article-card:hover {{
    background: #fffbf5;
    border-left-color: var(--accent);
  }}
  .card-source {{
    font-family: var(--mono);
    font-size: 10px;
    color: var(--muted);
    text-transform: uppercase;
    letter-spacing: 0.8px;
  }}
  .card-title {{
    font-family: var(--serif);
    font-size: 15px;
    font-weight: 600;
    line-height: 1.35;
    color: var(--ink);
  }}
  .article-card:hover .card-title {{ color: var(--accent2); }}
  .card-summary {{
    font-size: 13px;
    color: #4a4540;
    line-height: 1.5;
    flex: 1;
  }}
  .card-footer {{
    display: flex;
    justify-content: space-between;
    align-items: center;
    border-top: 1px solid #eee;
    padding-top: 8px;
    margin-top: 4px;
  }}
  .card-date {{ font-family: var(--mono); font-size: 10px; color: var(--muted); }}
  .card-read {{ font-family: var(--mono); font-size: 10px; color: var(--accent); }}

  .cat-header {{
    padding: 16px 20px 4px;
    border-bottom: 1px solid var(--border);
    margin-bottom: 0;
  }}
  .cat-header h2 {{
    font-family: var(--serif);
    font-size: 20px;
    font-weight: 600;
    color: var(--ink);
  }}

  /* ── SIDEBAR ── */
  .sidebar-section {{
    border-bottom: 1px solid var(--border);
    padding: 16px;
  }}
  .sidebar-title {{
    font-family: var(--mono);
    font-size: 10px;
    font-weight: 600;
    text-transform: uppercase;
    letter-spacing: 1.5px;
    color: var(--muted);
    margin-bottom: 12px;
    padding-bottom: 6px;
    border-bottom: 2px solid var(--accent);
    display: inline-block;
  }}

  /* Mini dividend table */
  .div-table {{ width: 100%; border-collapse: collapse; font-size: 12px; }}
  .div-table tr {{ border-bottom: 1px solid #e8e4dc; }}
  .div-table td {{ padding: 5px 3px; }}
  .div-table .sym {{ font-family: var(--mono); font-weight: 600; color: var(--accent2); }}
  .div-table .yld {{ font-family: var(--mono); font-weight: 600; color: var(--green); text-align: right; }}

  /* Market snapshot */
  .market-item {{
    display: flex;
    justify-content: space-between;
    padding: 6px 0;
    border-bottom: 1px solid #e8e4dc;
    font-size: 12px;
  }}
  .market-item:last-child {{ border-bottom: none; }}
  .market-name {{ font-weight: 500; color: var(--ink); }}
  .market-val {{ font-family: var(--mono); }}
  .market-val.up {{ color: var(--green); }}
  .market-val.dn {{ color: var(--red); }}

  /* ── DIVIDENDS PAGE ── */
  .data-page {{ padding: 30px 24px; }}
  .data-page h1 {{
    font-family: var(--serif);
    font-size: 28px;
    margin-bottom: 6px;
    color: var(--ink);
  }}
  .data-page .subtitle {{
    font-family: var(--mono);
    font-size: 11px;
    color: var(--muted);
    margin-bottom: 24px;
    text-transform: uppercase;
    letter-spacing: 1px;
  }}
  .data-table {{
    width: 100%;
    border-collapse: collapse;
    font-size: 13px;
    background: white;
    border: 1px solid var(--border);
  }}
  .data-table th {{
    background: var(--ink);
    color: white;
    font-family: var(--mono);
    font-size: 10px;
    font-weight: 600;
    text-transform: uppercase;
    letter-spacing: 1px;
    padding: 10px 14px;
    text-align: left;
  }}
  .data-table td {{
    padding: 10px 14px;
    border-bottom: 1px solid #eee;
    vertical-align: middle;
  }}
  .data-table tr:hover td {{ background: #fffbf5; }}
  .ticker {{
    font-family: var(--mono);
    font-weight: 600;
    color: var(--accent2);
    font-size: 13px;
  }}
  .yield-val {{
    font-family: var(--mono);
    font-weight: 600;
    color: var(--green);
    font-size: 14px;
  }}
  .ipo-price {{
    font-family: var(--mono);
    color: var(--ink);
  }}
  .sector-badge {{
    background: var(--panel);
    border: 1px solid var(--border);
    padding: 2px 7px;
    border-radius: 2px;
    font-size: 11px;
    color: var(--muted);
    font-family: var(--mono);
  }}

  /* ── ABOUT PAGE ── */
  .about-wrap {{ max-width: 700px; margin: 40px auto; padding: 0 24px 60px; }}
  .about-wrap h1 {{
    font-family: var(--serif);
    font-size: 32px;
    margin-bottom: 8px;
    color: var(--ink);
  }}
  .about-wrap p {{
    font-size: 14px;
    line-height: 1.7;
    color: #4a4540;
    margin-bottom: 14px;
  }}
  .disclaimer {{
    background: #fff8e1;
    border-left: 4px solid var(--gold);
    padding: 14px 18px;
    font-size: 12px;
    color: #5a4a00;
    line-height: 1.6;
    margin-top: 24px;
    border-radius: 0 4px 4px 0;
  }}

  /* ── FOOTER ── */
  .site-footer {{
    background: var(--black);
    color: #666;
    font-family: var(--mono);
    font-size: 11px;
    text-align: center;
    padding: 20px;
    border-top: 2px solid #222;
    line-height: 1.8;
  }}
  .site-footer span {{ color: #444; }}
  .disclaimer-footer {{
    margin-top: 8px;
    color: #444;
    font-size: 10px;
    max-width: 700px;
    margin: 8px auto 0;
  }}

  /* ── RESPONSIVE ── */
  @media (max-width: 768px) {{
    .news-layout {{ grid-template-columns: 1fr; }}
    .news-sidebar {{ display: none; }}
    .articles-grid {{ grid-template-columns: 1fr; }}
  }}
</style>
</head>
<body>

<!-- Top bar -->
<div class="top-bar">
  <span class="top-bar-left">DAILYMARKETCHECK.COM</span>
  <span class="top-bar-right">Updated: {now}</span>
</div>

<!-- Ticker tape -->
<div class="ticker-wrap">
  <div class="ticker-inner" id="ticker">
    {ticker_items_html}
  </div>
</div>

<!-- Masthead -->
<div class="masthead">
  <div class="masthead-name">Daily<span>Market</span>Check</div>
  <div class="masthead-tagline">{SITE_TAGLINE}</div>
  <div class="masthead-date">{now}</div>
</div>

<!-- Main Nav -->
<nav style="background:#0a0a0a;border-bottom:1px solid #222;">
  <div class="site-wrap">
    <div style="display:flex;overflow-x:auto;">
      <button class="nav-tab active" onclick="showPage('news',this)">News</button>
      <button class="nav-tab" onclick="showPage('dividends',this)">Top Dividends</button>
      <button class="nav-tab" onclick="showPage('ipos',this)">IPO Calendar</button>
      <button class="nav-tab" onclick="showPage('about',this)">About</button>
    </div>
  </div>
</nav>

<div class="site-wrap">

  <!-- ── NEWS PAGE ── -->
  <div class="page active" id="page-news">
    <div class="cat-filter">
      {category_nav_items}
    </div>
    <div class="news-layout">
      <div class="news-main">
        {category_sections}
      </div>
      <aside class="news-sidebar">
        <div class="sidebar-section">
          <div class="sidebar-title">Market Status</div>
          <div style="font-size: 13px; line-height: 1.6; color: #666;">
            <p style="margin-bottom: 10px;"><strong>US Markets:</strong></p>
            <p style="margin-bottom: 12px;">📍 <strong>Open:</strong> Mon–Fri, 9:30 AM – 4:00 PM ET<br/>
            <strong>Closed:</strong> Weekends & US Holidays</p>
            <p style="margin-bottom: 12px; font-size: 12px; color: #888;">For live prices and real-time quotes, visit:</p>
            <p style="margin-bottom: 0;">
              <a href="https://finance.yahoo.com" target="_blank" style="color: #0033cc; text-decoration: none;">Yahoo Finance</a> • 
              <a href="https://www.bloomberg.com" target="_blank" style="color: #0033cc; text-decoration: none;">Bloomberg</a> • 
              <a href="https://www.marketwatch.com" target="_blank" style="color: #0033cc; text-decoration: none;">MarketWatch</a>
            </p>
          </div>
        </div>
        <div class="sidebar-section">
          <div class="sidebar-title">Top Dividends</div>
          <table class="div-table">
            {''.join(f"<tr><td class='sym'>{s['ticker']}</td><td style='font-size:11px;color:#666'>{s['company']}</td><td class='yld'>{s['yield']}</td></tr>" for s in TOP_DIVIDEND_STOCKS[:5])}
          </table>
        </div>
        <div class="sidebar-section">
          <div class="sidebar-title">Disclaimer</div>
          <p style="font-size:11px;color:#888;line-height:1.6;">DailyMarketCheck is for informational purposes only. Nothing on this site constitutes financial advice. Always consult a licensed financial advisor before making investment decisions.</p>
        </div>
      </aside>
    </div>
  </div>

  <!-- ── DIVIDENDS PAGE ── -->
  <div class="page" id="page-dividends">
    <div class="data-page">
      <h1>Highest Dividend Stocks</h1>
      <div class="subtitle">Updated monthly · Sorted by yield · Not financial advice</div>
      <table class="data-table">
        <thead>
          <tr>
            <th>Ticker</th><th>Company</th><th>Dividend Yield</th><th>Sector</th>
          </tr>
        </thead>
        <tbody>{dividend_rows}</tbody>
      </table>
      <div class="disclaimer" style="margin-top:20px;">
        ⚠ Dividend yields are estimates and change with stock price and dividend announcements. Always verify with your broker before investing. Past performance does not guarantee future dividends.
      </div>
    </div>
  </div>

  <!-- ── IPO CALENDAR PAGE ── -->
  <div class="page" id="page-ipos">
    <div class="data-page">
      <h1>IPO Calendar</h1>
      <div class="subtitle">Upcoming &amp; recent IPOs · Updated weekly</div>
      <table class="data-table">
        <thead>
          <tr>
            <th>Ticker</th><th>Company</th><th>Date</th><th>Exchange</th><th>Expected Price</th><th>Sector</th>
          </tr>
        </thead>
        <tbody>{ipo_rows}</tbody>
      </table>
      <div class="disclaimer" style="margin-top:20px;">
        ⚠ IPO dates and price ranges are estimates and subject to change. This is not a solicitation to buy any security. Always read the S-1 prospectus before investing in any IPO.
      </div>
    </div>
  </div>

  <!-- ── ABOUT PAGE ── -->
  <div class="page" id="page-about">
    <div class="about-wrap">
      <h1>About DailyMarketCheck</h1>
      <p>DailyMarketCheck is an independent financial news aggregator that pulls articles from major financial publications and uses AI to generate concise summaries — so you can stay informed without information overload.</p>
      <p>Coverage includes stocks, bonds, IPOs, dividend investing, ETFs, cryptocurrency, and macroeconomic news. The site updates daily via an automated pipeline powered by Claude AI.</p>
      <p>Featured sources include MarketWatch, The Wall Street Journal, Yahoo Finance, Seeking Alpha, CoinDesk, and more.</p>
      <div class="disclaimer">
        <strong>⚠ Financial Disclaimer</strong><br/>
        DailyMarketCheck is an informational service only. Nothing published here constitutes financial, investment, tax, or legal advice. All data, prices, and news summaries are for general informational purposes and may not be accurate or up to date. Past market performance is not indicative of future results. Always consult a qualified financial advisor, accountant, or attorney before making any investment or financial decision.
      </div>
    </div>
  </div>

</div><!-- /site-wrap -->

<!-- Footer -->
<footer class="site-footer">
  <div>© {datetime.now().year} DailyMarketCheck &nbsp;·&nbsp; Powered by Claude AI &nbsp;·&nbsp; Updated daily at 6:30 AM ET</div>
  <div class="disclaimer-footer">For informational purposes only. Not financial advice. Always consult a licensed financial advisor before investing.</div>
</footer>

<script>
function showPage(name, btn) {{
  document.querySelectorAll('.page').forEach(p => p.classList.remove('active'));
  document.querySelectorAll('.nav-tab').forEach(b => b.classList.remove('active'));
  document.getElementById('page-' + name).classList.add('active');
  if (btn) btn.classList.add('active');
  window.scrollTo(0, 0);
}}

function showCat(catId) {{
  document.querySelectorAll('.cat-section').forEach(s => s.style.display = 'none');
  document.querySelectorAll('.cat-btn').forEach(b => b.classList.remove('active'));
  var el = document.getElementById('cat-' + catId);
  if (el) el.style.display = 'block';
  var btn = document.getElementById('catbtn-' + catId);
  if (btn) btn.classList.add('active');
}}
</script>
</body>
</html>"""
    return html

# ── MAIN ──────────────────────────────────────────────────────────────────────

def main():
    print("=" * 60)
    print("  DailyMarketCheck Pipeline")
    print("=" * 60)
    print(f"  Started: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

    articles = fetch_all_articles()

    total = sum(len(v) for v in articles.values())
    print(f"\n✅ Total articles fetched: {total}")

    market_data = fetch_market_data()

    print("🏗  Building HTML...")

    html = build_html(articles, market_data)

    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        f.write(html)

    print(f"✅ Site saved to: {OUTPUT_FILE}")
    print("=" * 60)

if __name__ == "__main__":
    main()
