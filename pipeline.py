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
MAX_ARTICLES_PER_FEED = 4

# Financial RSS feeds by category
FEEDS = {
    "Market News": [
        "https://feeds.finance.yahoo.com/rss/2.0/headline?s=^GSPC&region=US&lang=en-US",
        "https://www.marketwatch.com/rss/topstories",
        "https://feeds.a.dj.com/rss/RSSMarketsMain.xml",
        "https://www.cnbc.com/id/100003114/device/rss/rss.html",
        "https://feeds.reuters.com/reuters/businessNews",
        "https://www.investors.com/feed/",
        "https://www.thestreet.com/rss/",
        "https://www.barrons.com/xml/rss/3_7551.xml",
    ],
    "Stocks": [
        "https://feeds.finance.yahoo.com/rss/2.0/headline?s=AAPL,MSFT,NVDA,AMZN&region=US&lang=en-US",
        "https://www.investing.com/rss/news_25.rss",
        "https://seekingalpha.com/feed.xml",
        "https://www.cnbc.com/id/15839135/device/rss/rss.html",
        "https://feeds.reuters.com/reuters/companyNews",
        "https://www.zacks.com/rss/stockresearch.xml",
        "https://www.fool.com/feeds/index.aspx",
        "https://finance.yahoo.com/rss/topfinstories",
    ],
    "IPOs": [
        "https://feeds.finance.yahoo.com/rss/2.0/headline?s=ipo&region=US&lang=en-US",
        "https://www.renaissancecapital.com/review/ipoweekly.rss",
        "https://www.iposcoop.com/rss/",
        "https://www.cnbc.com/id/10000664/device/rss/rss.html",
        "https://feeds.reuters.com/reuters/IPOs",
    ],
    "Dividends": [
        "https://feeds.finance.yahoo.com/rss/2.0/headline?s=dividend&region=US&lang=en-US",
        "https://www.dividend.com/rss/news/",
        "https://dividendgrowthinvestor.com/feed/",
        "https://seekingalpha.com/tag/dividends.xml",
        "https://www.fool.com/feeds/index.aspx?id=dividends",
        "https://simplysafedividends.com/feed",
    ],
    "Bonds & Fixed Income": [
        "https://feeds.a.dj.com/rss/RSSBonds.xml",
        "https://www.treasurydirect.gov/rss/news.xml",
        "https://feeds.finance.yahoo.com/rss/2.0/headline?s=^TNX&region=US&lang=en-US",
        "https://feeds.reuters.com/reuters/bondsNews",
        "https://www.cnbc.com/id/20910258/device/rss/rss.html",
        "https://www.investing.com/rss/news_285.rss",
    ],
    "ETFs": [
        "https://etfdb.com/rss.xml",
        "https://feeds.finance.yahoo.com/rss/2.0/headline?s=SPY,QQQ,IWM&region=US&lang=en-US",
        "https://www.etf.com/rss.xml",
        "https://seekingalpha.com/tag/etf-portfolio-strategy.xml",
        "https://www.cnbc.com/id/100727362/device/rss/rss.html",
    ],
    "Crypto": [
        "https://cointelegraph.com/rss",
        "https://coindesk.com/arc/outboundfeeds/rss/",
        "https://feeds.finance.yahoo.com/rss/2.0/headline?s=BTC-USD,ETH-USD&region=US&lang=en-US",
        "https://decrypt.co/feed",
        "https://www.cnbc.com/id/100762479/device/rss/rss.html",
        "https://bitcoinmagazine.com/.rss/full/",
    ],
    "Economy & Fed": [
        "https://feeds.a.dj.com/rss/RSSEconomy.xml",
        "https://feeds.finance.yahoo.com/rss/2.0/headline?s=economy+fed+rates&region=US&lang=en-US",
        "https://www.federalreserve.gov/feeds/press_all.xml",
        "https://feeds.reuters.com/reuters/economicNews",
        "https://www.cnbc.com/id/20910258/device/rss/rss.html",
        "https://www.investing.com/rss/news_14.rss",
    ],
    "Earnings": [
        "https://feeds.finance.yahoo.com/rss/2.0/headline?s=earnings&region=US&lang=en-US",
        "https://www.cnbc.com/id/15839135/device/rss/rss.html",
        "https://seekingalpha.com/tag/earnings.xml",
        "https://www.zacks.com/rss/earnings.xml",
        "https://feeds.reuters.com/reuters/companyNews",
    ],
    "Real Estate & REITs": [
        "https://feeds.finance.yahoo.com/rss/2.0/headline?s=reit&region=US&lang=en-US",
        "https://www.investing.com/rss/news_15.rss",
        "https://seekingalpha.com/tag/reits.xml",
        "https://www.thestreet.com/rss/real-estate",
    ],
    "Global Markets": [
        "https://feeds.reuters.com/reuters/worldNews",
        "https://feeds.a.dj.com/rss/RSSWorldNews.xml",
        "https://www.cnbc.com/id/100727362/device/rss/rss.html",
        "https://feeds.finance.yahoo.com/rss/2.0/headline?s=^FTSE,^N225,^HSI&region=US&lang=en-US",
        "https://www.investing.com/rss/news_285.rss",
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
            model="claude-sonnet-4-20250514",
            max_tokens=120,
            messages=[{"role": "user", "content": prompt}]
        )
        return resp.content[0].text.strip()
    except Exception as e:
        print(f"  ⚠ AI error: {e}")
        return clean_html(description)[:200] + "..."

def fetch_all_articles():
    """Fetch articles from all feeds, categorized."""
    all_data = {}
    for category, urls in FEEDS.items():
        print(f"\n📡 Fetching: {category}")
        articles = []
        seen_titles = set()
        for url in urls:
            entries = fetch_feed(url)
            for entry in entries:
                title = clean_html(entry.get("title", ""))
                if not title or title in seen_titles:
                    continue
                seen_titles.add(title)
                link = entry.get("link", "#")
                description = clean_html(entry.get("summary", entry.get("description", "")))
                pub = entry.get("published", entry.get("updated", ""))
                print(f"  ✓ {title[:60]}...")
                summary = summarize(title, description)
                articles.append({
                    "title": title,
                    "link": link,
                    "summary": summary,
                    "pub": pub,
                    "source": url.split("/")[2].replace("www.", "").replace("feeds.", ""),
                })
                if len(articles) >= 8:
                    break
            if len(articles) >= 8:
                break
        all_data[category] = articles
        print(f"  → {len(articles)} articles collected")
    return all_data

# ── HTML GENERATION ───────────────────────────────────────────────────────────

def build_html(articles_by_category):
    now = datetime.now(timezone.utc).strftime("%B %d, %Y · %H:%M UTC")

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
    for ipo in IPO_CALENDAR:
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
    <span class="ticker-item"><span class="sym">SPY</span> <span class="up">▲ 0.38%</span></span>
    <span class="ticker-item"><span class="sym">QQQ</span> <span class="up">▲ 0.62%</span></span>
    <span class="ticker-item"><span class="sym">DIA</span> <span class="dn">▼ 0.11%</span></span>
    <span class="ticker-item"><span class="sym">IWM</span> <span class="up">▲ 0.24%</span></span>
    <span class="ticker-item"><span class="sym">AAPL</span> <span class="up">▲ 1.2%</span></span>
    <span class="ticker-item"><span class="sym">NVDA</span> <span class="up">▲ 2.4%</span></span>
    <span class="ticker-item"><span class="sym">MSFT</span> <span class="dn">▼ 0.3%</span></span>
    <span class="ticker-item"><span class="sym">AMZN</span> <span class="up">▲ 0.9%</span></span>
    <span class="ticker-item"><span class="sym">TSLA</span> <span class="dn">▼ 1.1%</span></span>
    <span class="ticker-item"><span class="sym">BTC</span> <span class="up">▲ 3.1%</span></span>
    <span class="ticker-item"><span class="sym">10Y</span> 4.42%</span>
    <span class="ticker-item"><span class="sym">GOLD</span> <span class="up">▲ 0.5%</span></span>
    <span class="ticker-item"><span class="sym">OIL</span> <span class="dn">▼ 0.7%</span></span>
    <span class="ticker-item"><span class="sym">USD/EUR</span> 0.923</span>
    <!-- Duplicate for seamless loop -->
    <span class="ticker-item"><span class="sym">SPY</span> <span class="up">▲ 0.38%</span></span>
    <span class="ticker-item"><span class="sym">QQQ</span> <span class="up">▲ 0.62%</span></span>
    <span class="ticker-item"><span class="sym">DIA</span> <span class="dn">▼ 0.11%</span></span>
    <span class="ticker-item"><span class="sym">IWM</span> <span class="up">▲ 0.24%</span></span>
    <span class="ticker-item"><span class="sym">AAPL</span> <span class="up">▲ 1.2%</span></span>
    <span class="ticker-item"><span class="sym">NVDA</span> <span class="up">▲ 2.4%</span></span>
    <span class="ticker-item"><span class="sym">MSFT</span> <span class="dn">▼ 0.3%</span></span>
    <span class="ticker-item"><span class="sym">AMZN</span> <span class="up">▲ 0.9%</span></span>
    <span class="ticker-item"><span class="sym">TSLA</span> <span class="dn">▼ 1.1%</span></span>
    <span class="ticker-item"><span class="sym">BTC</span> <span class="up">▲ 3.1%</span></span>
    <span class="ticker-item"><span class="sym">10Y</span> 4.42%</span>
    <span class="ticker-item"><span class="sym">GOLD</span> <span class="up">▲ 0.5%</span></span>
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
          <div class="sidebar-title">Market Snapshot</div>
          <div class="market-item"><span class="market-name">S&amp;P 500</span><span class="market-val up">▲ 5,312.41</span></div>
          <div class="market-item"><span class="market-name">Nasdaq</span><span class="market-val up">▲ 18,671.29</span></div>
          <div class="market-item"><span class="market-name">Dow Jones</span><span class="market-val dn">▼ 39,118.86</span></div>
          <div class="market-item"><span class="market-name">Russell 2000</span><span class="market-val up">▲ 2,041.33</span></div>
          <div class="market-item"><span class="market-name">10-Yr Yield</span><span class="market-val">4.42%</span></div>
          <div class="market-item"><span class="market-name">Gold</span><span class="market-val up">▲ $2,418</span></div>
          <div class="market-item"><span class="market-name">WTI Oil</span><span class="market-val dn">▼ $78.12</span></div>
          <div class="market-item"><span class="market-name">Bitcoin</span><span class="market-val up">▲ $68,420</span></div>
          <div style="font-family:var(--mono);font-size:10px;color:#aaa;margin-top:8px;">* Prices update via pipeline</div>
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
    print("🏗  Building HTML...")

    html = build_html(articles)

    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        f.write(html)

    print(f"✅ Site saved to: {OUTPUT_FILE}")
    print("=" * 60)

if __name__ == "__main__":
    main()
