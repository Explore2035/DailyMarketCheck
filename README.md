# 📈 DailyMarketCheck

**Financial news aggregator with AI-powered summaries.**  
Covers stocks, IPOs, bonds, dividends, ETFs, crypto, and macro news.

---

## How It Works

1. `pipeline.py` fetches articles from financial RSS feeds (Yahoo Finance, MarketWatch, WSJ, Seeking Alpha, CoinDesk, etc.)
2. Claude AI writes a 2-sentence summary for each article
3. A static `index.html` is generated with Bloomberg-style design
4. GitHub Actions deploys to GitHub Pages automatically — weekdays at 6:30 AM ET

---

## Setup

### 1. Fork / clone this repo

### 2. Add your Anthropic API key
Go to **Settings → Secrets and variables → Actions**  
Add secret: `ANTHROPIC_API_KEY`

### 3. Enable GitHub Pages
Go to **Settings → Pages → Source: Deploy from branch → main → / (root)**

### 4. Run manually first
Go to **Actions → DailyMarketCheck → Run workflow**

---

## Customization

### Add / remove feeds
Edit the `FEEDS` dictionary in `pipeline.py`. Each category can have multiple RSS URLs.

### Update dividend stocks
Edit `TOP_DIVIDEND_STOCKS` list in `pipeline.py` (update monthly or as needed).

### Update IPO calendar
Edit `IPO_CALENDAR` list in `pipeline.py` (update weekly — check Renaissance Capital or IPO Scoop).

### Update ticker tape prices
For live prices, integrate a free API like **Finnhub** or **Alpha Vantage** into the pipeline — replace the static ticker values in `build_html()`.

---

## Site Features

| Feature | Details |
|---|---|
| 📡 News | 8 categories, AI-summarized, sourced from top financial RSS feeds |
| 📊 Market Snapshot | S&P 500, Nasdaq, Dow, yields, gold, oil, BTC |
| 💰 Top Dividends | Curated table of highest-yield stocks |
| 🚀 IPO Calendar | Upcoming IPOs with exchange, price range, sector |
| 📜 Disclaimer | Standard financial disclaimer on every page |
| 🎨 Design | Bloomberg-style: dark header, serif/mono typography, orange accent |

---

## ⚠️ Disclaimer

DailyMarketCheck is for **informational purposes only**.  
Nothing on this site constitutes financial, investment, tax, or legal advice.  
Always consult a licensed financial advisor before making investment decisions.

---

*Powered by Claude AI · Built with Python + GitHub Pages*
