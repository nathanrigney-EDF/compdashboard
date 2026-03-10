# 📡 Orbital Intel — Competitor Intelligence Dashboard

A self-hosted, GitHub Pages competitor intelligence dashboard for tracking OSINT and satellite imagery companies that compete in the US defense market. Refreshes automatically every morning via GitHub Actions and sends an email digest of what you missed.

---

## 🗂 What's Tracked

### OSINT / Intelligence Platforms (12 companies)
| Company | Focus |
|---|---|
| Palantir Technologies | AI-powered data fusion & analytics (Gotham, AIP) |
| Babel Street | Real-time multilingual OSINT & persistent monitoring |
| Recorded Future | Threat intelligence dashboards |
| Flashpoint | Dark/deep/open web intelligence (Ignite platform) |
| Dataminr | Real-time AI alerting from public signals |
| Primer AI | NLP document analysis & intelligence automation |
| ShadowDragon | Social media & open-source tracking |
| BigBear.ai | AI-driven analytics for defense/IC |
| Cognyte | OSINT & investigative analytics |
| CACI International | OSINT services ($239M DIA contract) |
| Leidos | Intelligence analysis ($143M DIA contract) |
| Booz Allen Hamilton | Defense analytics & IC consulting |

### Satellite Imagery Providers (13 companies)
| Company | Sensor Type |
|---|---|
| Maxar Intelligence | Optical VHR (30cm) — NGA/NRO anchor |
| Planet Labs | Daily global optical — NRO EOCL |
| BlackSky Technology | Real-time optical + AI analytics |
| Capella Space | SAR (0.5m all-weather) |
| Umbra | Ultra-high-res SAR (0.25m) |
| ICEYE | SAR persistent monitoring |
| Satellogic | Optical + hyperspectral |
| HEO | Space Domain Awareness |
| L3Harris Technologies | Multi-modal EO systems |
| Airbus Defence & Space | Optical + SAR (Pléiades Neo) |
| Spire Global | RF / AIS / weather sensing |
| Muon Space | Multi-sensor smallsats — NRO EOCL |
| Orbital Insight | Geospatial analytics platform |

---

## 🚀 Setup (15 minutes)

### 1. Fork / create this repo
Push this entire folder to a new GitHub repository.

### 2. Enable GitHub Pages
- Go to **Settings → Pages**
- Source: **Deploy from a branch**
- Branch: `main` / `root`
- Your dashboard will be live at `https://yourusername.github.io/your-repo-name`

### 3. Set up Secrets (Settings → Secrets → Actions)

| Secret | Required | Where to get it |
|---|---|---|
| `NEWS_API_KEY` | Recommended | [newsapi.org](https://newsapi.org) — free tier: 100 req/day |
| `SAM_GOV_API_KEY` | Optional | [api.sam.gov](https://api.sam.gov) — free, register with .gov email |
| `SENDGRID_API_KEY` | For email | [sendgrid.com](https://sendgrid.com) — free tier: 100 emails/day |
| `DIGEST_EMAIL_TO` | For email | Your email address |
| `DIGEST_EMAIL_FROM` | For email | Verified sender in SendGrid |

> **Note:** The dashboard works without any API keys using Google News RSS, which is free and requires no registration. API keys add more coverage and enable email digests.

### 4. Run the first fetch
- Go to **Actions → Daily Intelligence Refresh**
- Click **Run workflow** → **Run workflow**
- Wait ~3 minutes for it to complete
- Refresh your GitHub Pages URL

### 5. Automatic daily refresh
The workflow runs automatically at **6:00 AM ET every morning** (10:00 UTC).

---

## 📧 Email Digest Setup

The morning email requires SendGrid (free up to 100 emails/day):

1. Create a free account at [sendgrid.com](https://sendgrid.com)
2. Verify a sender email address (Settings → Sender Authentication)
3. Create an API key (Settings → API Keys → Full Access)
4. Add the four `SENDGRID_*` and `DIGEST_EMAIL_*` secrets to your repo

The email digest includes all articles published in the last 28 hours, grouped by company, with source badges for News / Press Release / Contract.

---

## 📁 File Structure

```
├── index.html              # Dashboard UI (GitHub Pages)
├── data/
│   ├── companies.json      # Company definitions (edit to add/remove)
│   ├── news.json           # Article archive (auto-updated daily)
│   └── digest.json         # Last 28h articles (auto-updated daily)
├── scripts/
│   └── fetch_news.py       # News fetcher (runs in GitHub Actions)
└── .github/
    └── workflows/
        └── daily-refresh.yml   # Cron job: 6am ET daily
```

---

## ✏️ Adding or Removing Companies

Edit `data/companies.json`. Each entry looks like:

```json
{
  "id": "company-slug",
  "name": "Company Name",
  "ticker": "TICK",
  "category": "osint",
  "description": "One line description",
  "website": "https://company.com",
  "newsQuery": "Company Name defense government contract",
  "govClients": ["DoD", "NGA"],
  "founded": 2015,
  "hq": "City, State"
}
```

- `category` must be `"osint"` or `"satellite"`
- `newsQuery` is what gets sent to Google News and NewsAPI — be specific to avoid noise
- After editing, commit the file and re-run the workflow

---

## 🔄 News Sources

| Source | Key Required | What it fetches |
|---|---|---|
| Google News RSS | None | General news articles |
| NewsAPI | `NEWS_API_KEY` | Trade press, deeper coverage |
| SAM.gov | `SAM_GOV_API_KEY` (optional) | US government contract awards |
| Press Release filter | None | Announcements via Google News |

---

## 📊 Dashboard Features

- **Company sidebar** — filter feed by individual company
- **Category tabs** — filter by OSINT, Satellite, or Contract Awards
- **24h "New" filter** — see only what you missed overnight
- **Search** — full-text search across titles, descriptions, sources
- **Ticker** — running count of tracked companies at top
- **Morning digest banner** — highlights new articles when you open the dashboard

---

## 🛠 Customization

**Change refresh time:** Edit the cron in `.github/workflows/daily-refresh.yml`
```yaml
- cron: '0 10 * * *'   # 10:00 UTC = 6:00 AM ET
```

**Keep more/less history:** Edit `DIGEST_LOOKBACK_HOURS` and the 90-day cutoff in `scripts/fetch_news.py`

**Custom news queries:** Update `newsQuery` in `companies.json` for any company to tune signal vs. noise
