#!/usr/bin/env python3
"""
OSINT Competitor Intelligence - Daily News Fetcher
Runs via GitHub Actions every morning at 6am ET
Fetches news from multiple sources and writes to data/news.json
"""

import json
import os
import re
import sys
import time
import urllib.parse
import urllib.request
from datetime import datetime, timezone, timedelta

# ─── Config ────────────────────────────────────────────────────────────────────
NEWS_API_KEY = os.environ.get("NEWS_API_KEY", "")
SENDGRID_API_KEY = os.environ.get("SENDGRID_API_KEY", "")
DIGEST_EMAIL_TO = os.environ.get("DIGEST_EMAIL_TO", "")
DIGEST_EMAIL_FROM = os.environ.get("DIGEST_EMAIL_FROM", "noreply@yourdomain.com")

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
COMPANIES_FILE = os.path.join(BASE_DIR, "data", "companies.json")
NEWS_FILE = os.path.join(BASE_DIR, "data", "news.json")
DIGEST_FILE = os.path.join(BASE_DIR, "data", "digest.json")

# SAM.gov API (free, no key required for basic search)
SAM_GOV_API = "https://api.sam.gov/opportunities/v2/search"
SAM_GOV_KEY = os.environ.get("SAM_GOV_API_KEY", "")  # Register free at api.sam.gov

# How many days back to look for "new" articles in digest
DIGEST_LOOKBACK_HOURS = 28  # slightly more than 24h to avoid missing anything


# ─── Helpers ───────────────────────────────────────────────────────────────────

def load_companies():
    with open(COMPANIES_FILE) as f:
        return json.load(f)


def load_existing_news():
    if os.path.exists(NEWS_FILE):
        with open(NEWS_FILE) as f:
            return json.load(f)
    return {"articles": [], "lastUpdated": None}


def http_get(url, headers=None, timeout=15):
    """Simple HTTP GET with error handling."""
    req = urllib.request.Request(url, headers=headers or {})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except Exception as e:
        print(f"  [WARN] HTTP error for {url[:80]}: {e}", file=sys.stderr)
        return None


def slugify(text):
    return re.sub(r"[^a-z0-9-]", "-", text.lower()).strip("-")


# ─── News API (newsapi.org) ─────────────────────────────────────────────────────

def fetch_newsapi(company, from_date):
    """Fetch articles from NewsAPI for a company."""
    if not NEWS_API_KEY:
        return []

    query = urllib.parse.quote(company["newsQuery"])
    url = (
        f"https://newsapi.org/v2/everything"
        f"?q={query}"
        f"&from={from_date}"
        f"&sortBy=publishedAt"
        f"&language=en"
        f"&pageSize=10"
        f"&apiKey={NEWS_API_KEY}"
    )

    data = http_get(url)
    if not data or data.get("status") != "ok":
        return []

    articles = []
    for a in data.get("articles", []):
        articles.append({
            "id": slugify(company["id"] + "-" + (a.get("title") or "")[:50]),
            "companyId": company["id"],
            "companyName": company["name"],
            "category": company["category"],
            "source": "news",
            "sourceName": a.get("source", {}).get("name", "Unknown"),
            "title": a.get("title", ""),
            "description": a.get("description", ""),
            "url": a.get("url", ""),
            "publishedAt": a.get("publishedAt", ""),
            "fetchedAt": datetime.now(timezone.utc).isoformat(),
        })
    return articles


# ─── Google News RSS (free, no key) ────────────────────────────────────────────

def fetch_google_news_rss(company):
    """Fetch from Google News RSS — free, no API key needed."""
    import xml.etree.ElementTree as ET

    query = urllib.parse.quote(company["newsQuery"])
    url = f"https://news.google.com/rss/search?q={query}&hl=en-US&gl=US&ceid=US:en"

    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            content = resp.read().decode("utf-8")
    except Exception as e:
        print(f"  [WARN] RSS error for {company['name']}: {e}", file=sys.stderr)
        return []

    articles = []
    try:
        root = ET.fromstring(content)
        items = root.findall(".//item")[:8]
        for item in items:
            title = item.findtext("title", "").strip()
            link = item.findtext("link", "").strip()
            pub_date = item.findtext("pubDate", "").strip()
            description = item.findtext("description", "").strip()
            # Clean HTML from description
            description = re.sub(r"<[^>]+>", "", description)[:300]

            # Parse date
            try:
                from email.utils import parsedate_to_datetime
                dt = parsedate_to_datetime(pub_date)
                iso_date = dt.isoformat()
            except Exception:
                iso_date = datetime.now(timezone.utc).isoformat()

            articles.append({
                "id": slugify(company["id"] + "-rss-" + title[:50]),
                "companyId": company["id"],
                "companyName": company["name"],
                "category": company["category"],
                "source": "news",
                "sourceName": "Google News",
                "title": title,
                "description": description,
                "url": link,
                "publishedAt": iso_date,
                "fetchedAt": datetime.now(timezone.utc).isoformat(),
            })
    except ET.ParseError as e:
        print(f"  [WARN] RSS parse error for {company['name']}: {e}", file=sys.stderr)

    return articles


# ─── SAM.gov Contract Awards ────────────────────────────────────────────────────

def fetch_sam_contracts(company, from_date):
    """Fetch contract awards from SAM.gov API."""
    if not SAM_GOV_KEY:
        # Try unauthenticated (limited)
        keyword = urllib.parse.quote(company["name"])
        url = (
            f"https://api.sam.gov/opportunities/v2/search"
            f"?keywords={keyword}"
            f"&postedFrom={from_date}"
            f"&limit=5"
            f"&index=opp"
            f"&q={keyword}"
        )
    else:
        keyword = urllib.parse.quote(company["name"])
        url = (
            f"https://api.sam.gov/opportunities/v2/search"
            f"?api_key={SAM_GOV_KEY}"
            f"&keywords={keyword}"
            f"&postedFrom={from_date}"
            f"&limit=5"
        )

    data = http_get(url)
    if not data:
        return []

    awards = []
    opportunities = data.get("opportunitiesData", []) or data.get("_embedded", {}).get("results", [])
    for opp in opportunities[:5]:
        title = opp.get("title", "")
        notice_id = opp.get("noticeId", "")
        posted_date = opp.get("postedDate", "")
        dept = opp.get("departmentName", opp.get("department", ""))
        award_amt = opp.get("award", {}).get("amount", "") if isinstance(opp.get("award"), dict) else ""

        awards.append({
            "id": slugify(company["id"] + "-sam-" + (notice_id or title[:40])),
            "companyId": company["id"],
            "companyName": company["name"],
            "category": company["category"],
            "source": "contract",
            "sourceName": "SAM.gov",
            "title": f"Contract: {title}",
            "description": f"Agency: {dept}" + (f" | Award: ${award_amt:,}" if award_amt else ""),
            "url": f"https://sam.gov/opp/{notice_id}/view" if notice_id else "https://sam.gov",
            "publishedAt": posted_date or datetime.now(timezone.utc).isoformat(),
            "fetchedAt": datetime.now(timezone.utc).isoformat(),
        })
    return awards


# ─── Press Release RSS (company IR pages via GNews) ────────────────────────────

def fetch_press_releases(company):
    """Fetch press releases by searching for 'site:company.com' style queries."""
    import xml.etree.ElementTree as ET

    domain = urllib.parse.urlparse(company["website"]).netloc
    query = urllib.parse.quote(f'"{company["name"]}" press release OR announcement')
    url = f"https://news.google.com/rss/search?q={query}&hl=en-US&gl=US&ceid=US:en"

    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            content = resp.read().decode("utf-8")
    except Exception as e:
        return []

    articles = []
    try:
        root = ET.fromstring(content)
        items = root.findall(".//item")[:5]
        for item in items:
            title = item.findtext("title", "").strip()
            link = item.findtext("link", "").strip()
            pub_date = item.findtext("pubDate", "").strip()

            # Only include if it looks like a press release
            if not any(kw in title.lower() for kw in ["announce", "award", "contract", "partner", "launch", "release", "win", "select"]):
                continue

            try:
                from email.utils import parsedate_to_datetime
                dt = parsedate_to_datetime(pub_date)
                iso_date = dt.isoformat()
            except Exception:
                iso_date = datetime.now(timezone.utc).isoformat()

            articles.append({
                "id": slugify(company["id"] + "-pr-" + title[:50]),
                "companyId": company["id"],
                "companyName": company["name"],
                "category": company["category"],
                "source": "press_release",
                "sourceName": "Press Release",
                "title": title,
                "description": f"Press release / announcement from {company['name']}",
                "url": link,
                "publishedAt": iso_date,
                "fetchedAt": datetime.now(timezone.utc).isoformat(),
            })
    except Exception:
        pass

    return articles


# ─── Dedup & Merge ─────────────────────────────────────────────────────────────

def dedup_articles(articles):
    """Remove duplicates by ID, keeping the most recent fetchedAt."""
    seen = {}
    for a in articles:
        aid = a["id"]
        if aid not in seen:
            seen[aid] = a
        else:
            # Keep newer fetch
            if a["fetchedAt"] > seen[aid]["fetchedAt"]:
                seen[aid] = a
    return list(seen.values())


def is_recent(article, hours=DIGEST_LOOKBACK_HOURS):
    """Check if article was published within the last N hours."""
    try:
        pub = datetime.fromisoformat(article["publishedAt"].replace("Z", "+00:00"))
        cutoff = datetime.now(timezone.utc) - timedelta(hours=hours)
        return pub >= cutoff
    except Exception:
        return False


# ─── Email Digest via SendGrid ─────────────────────────────────────────────────

def send_email_digest(new_articles, all_companies):
    """Send morning digest email via SendGrid."""
    if not SENDGRID_API_KEY or not DIGEST_EMAIL_TO:
        print("[INFO] Skipping email — SENDGRID_API_KEY or DIGEST_EMAIL_TO not set")
        return

    today = datetime.now(timezone.utc).strftime("%B %d, %Y")
    company_map = {c["id"]: c for c in all_companies}

    # Group by company
    by_company = {}
    for a in new_articles:
        cid = a["companyId"]
        by_company.setdefault(cid, []).append(a)

    if not by_company:
        print("[INFO] No new articles — skipping email digest")
        return

    # Build HTML email
    source_icons = {
        "news": "📰",
        "press_release": "📣",
        "contract": "📋",
    }

    sections = ""
    for cid, articles in sorted(by_company.items()):
        company = company_map.get(cid, {"name": cid, "category": "unknown"})
        cat_label = "OSINT" if company["category"] == "osint" else "SAT IMAGERY"
        sections += f"""
        <div style="margin-bottom:28px; border-left:3px solid {'#00d4ff' if company['category'] == 'osint' else '#ff6b35'}; padding-left:16px;">
          <div style="font-size:11px;letter-spacing:2px;text-transform:uppercase;color:#888;margin-bottom:4px;">{cat_label}</div>
          <div style="font-size:18px;font-weight:700;color:#e8e8e8;margin-bottom:12px;">{company['name']}</div>
        """
        for a in articles[:4]:
            icon = source_icons.get(a["source"], "🔗")
            try:
                pub_dt = datetime.fromisoformat(a["publishedAt"].replace("Z", "+00:00"))
                pub_str = pub_dt.strftime("%b %d, %I:%M %p UTC")
            except Exception:
                pub_str = a["publishedAt"][:10]

            sections += f"""
          <div style="margin-bottom:10px;padding:10px 14px;background:#1a1f2e;border-radius:6px;">
            <div style="font-size:10px;color:#666;margin-bottom:3px;">{icon} {a['sourceName'].upper()} · {pub_str}</div>
            <a href="{a['url']}" style="color:#00d4ff;text-decoration:none;font-size:14px;font-weight:600;">{a['title']}</a>
            <div style="color:#999;font-size:12px;margin-top:3px;">{a.get('description','')[:120]}</div>
          </div>
            """
        sections += "</div>"

    total = len(new_articles)
    companies_active = len(by_company)

    html_body = f"""
<!DOCTYPE html>
<html>
<head><meta charset="UTF-8"></head>
<body style="background:#0d1117;margin:0;padding:0;font-family:'Helvetica Neue',Helvetica,sans-serif;">
  <div style="max-width:680px;margin:0 auto;padding:32px 24px;">

    <!-- Header -->
    <div style="border-bottom:1px solid #222;margin-bottom:28px;padding-bottom:20px;">
      <div style="font-size:10px;letter-spacing:3px;text-transform:uppercase;color:#666;margin-bottom:6px;">ORBITAL INTEL BRIEF</div>
      <div style="font-size:26px;font-weight:800;color:#ffffff;">{today}</div>
      <div style="font-size:13px;color:#888;margin-top:6px;">{total} new item{'s' if total != 1 else ''} across {companies_active} competitor{'s' if companies_active != 1 else ''}</div>
    </div>

    <!-- Articles -->
    {sections}

    <!-- Footer -->
    <div style="border-top:1px solid #222;margin-top:32px;padding-top:16px;font-size:11px;color:#555;">
      Generated by your OSINT Competitor Dashboard · <a href="https://github.com" style="color:#444;">View on GitHub</a>
    </div>

  </div>
</body>
</html>
"""

    payload = json.dumps({
        "personalizations": [{"to": [{"email": DIGEST_EMAIL_TO}]}],
        "from": {"email": DIGEST_EMAIL_FROM, "name": "Orbital Intel Brief"},
        "subject": f"[INTEL BRIEF] {today} — {total} competitor update{'s' if total != 1 else ''}",
        "content": [{"type": "text/html", "value": html_body}],
    }).encode("utf-8")

    req = urllib.request.Request(
        "https://api.sendgrid.com/v3/mail/send",
        data=payload,
        headers={
            "Authorization": f"Bearer {SENDGRID_API_KEY}",
            "Content-Type": "application/json",
        },
        method="POST"
    )
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            print(f"[INFO] Email digest sent → {DIGEST_EMAIL_TO} (status {resp.status})")
    except Exception as e:
        print(f"[ERROR] Failed to send email: {e}", file=sys.stderr)


# ─── Main ───────────────────────────────────────────────────────────────────────

def main():
    print(f"[{datetime.now(timezone.utc).isoformat()}] Starting news fetch...")

    companies = load_companies()
    existing = load_existing_news()

    # Determine date range
    from_date = (datetime.now(timezone.utc) - timedelta(days=3)).strftime("%Y-%m-%d")

    all_new_articles = []

    for company in companies:
        print(f"  → {company['name']}")

        # 1. Google News RSS (free, always runs)
        rss_articles = fetch_google_news_rss(company)
        all_new_articles.extend(rss_articles)
        time.sleep(0.5)  # be polite

        # 2. NewsAPI (if key available)
        if NEWS_API_KEY:
            newsapi_articles = fetch_newsapi(company, from_date)
            all_new_articles.extend(newsapi_articles)
            time.sleep(0.3)

        # 3. Press releases
        pr_articles = fetch_press_releases(company)
        all_new_articles.extend(pr_articles)
        time.sleep(0.5)

        # 4. SAM.gov contracts
        sam_articles = fetch_sam_contracts(company, from_date)
        all_new_articles.extend(sam_articles)
        time.sleep(0.3)

    print(f"[INFO] Fetched {len(all_new_articles)} raw articles")

    # Merge with existing, dedup, sort by date
    combined = existing.get("articles", []) + all_new_articles
    combined = dedup_articles(combined)
    combined.sort(key=lambda a: a.get("publishedAt", ""), reverse=True)

    # Keep last 90 days only (prevent unbounded growth)
    cutoff_90 = (datetime.now(timezone.utc) - timedelta(days=90)).isoformat()
    combined = [a for a in combined if a.get("publishedAt", "") >= cutoff_90]

    # Save news.json
    output = {
        "articles": combined,
        "lastUpdated": datetime.now(timezone.utc).isoformat(),
        "totalArticles": len(combined),
    }
    with open(NEWS_FILE, "w") as f:
        json.dump(output, f, indent=2)
    print(f"[INFO] Saved {len(combined)} articles to data/news.json")

    # Build digest (articles from last 28h)
    new_articles = [a for a in combined if is_recent(a, DIGEST_LOOKBACK_HOURS)]
    digest = {
        "articles": new_articles,
        "generatedAt": datetime.now(timezone.utc).isoformat(),
        "periodHours": DIGEST_LOOKBACK_HOURS,
        "count": len(new_articles),
    }
    with open(DIGEST_FILE, "w") as f:
        json.dump(digest, f, indent=2)
    print(f"[INFO] Digest: {len(new_articles)} articles in last {DIGEST_LOOKBACK_HOURS}h")

    # Send email digest
    send_email_digest(new_articles, companies)

    print("[INFO] Done.")


if __name__ == "__main__":
    main()
