import requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin
from datetime import datetime
import time
import re
import os
from dotenv import load_dotenv

# ============================================================
# Load environment variables from .env file
# ============================================================
load_dotenv()

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")

if not TELEGRAM_BOT_TOKEN:
    raise ValueError("Missing TELEGRAM_BOT_TOKEN environment variable")
if not TELEGRAM_CHAT_ID:
    raise ValueError("Missing TELEGRAM_CHAT_ID environment variable")

# ============================================================
# Lowyat.NET Jobs & Careers — Top 10 Threads This Month
# ============================================================
# This script crawls the Jobs & Careers forum, extracts thread
# titles, URLs, replies, views, and last activity dates, then
# ranks them by reply count and prints the top 10 for the
# current month.
#
# Usage:
#   python lowyat.py
#
# Dependencies:
#   pip install requests beautifulsoup4 lxml python-dotenv
# ============================================================


BASE_URL = "https://forum.lowyat.net"
START_URL = "https://forum.lowyat.net/Jobs&Careers"

headers = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120 Safari/537.36"
}

session = requests.Session()
session.headers.update(headers)

now = datetime.now()
current_month = now.month
current_year = now.year

all_threads = []
seen_urls = set()


def parse_threads_from_page(soup):
    """Extract thread data from a parsed forum listing page."""
    threads = []

    # Lowyat uses <tr> rows for forum thread listings
    rows = soup.select("tr")

    for row in rows:
        title_link = row.find("a", href=lambda h: h and h.startswith("/topic/"))
        if not title_link:
            continue

        title = title_link.get_text(strip=True)
        if not title:
            continue

        href = title_link.get("href")
        full_url = urljoin(BASE_URL, href)

        if full_url in seen_urls:
            continue
        seen_urls.add(full_url)

        # Get all cell text for parsing
        cells = row.find_all(["td", "th"])
        cell_texts = [cell.get_text(strip=True) for cell in cells]

        # Parse replies and views from the row
        # Lowyat structure:
        #   <td id="forum_topic_replies">  <a href="javascript:who_posted(5263676);">569</a> </td>
        #   <td id="forum_topic_views">    <script>document.write(abbrNum(366221,1));</script> </td>
        replies = 0
        views = 0
        last_activity = None

        # Extract replies from the forum_topic_replies cell
        replies_cell = row.find("td", id="forum_topic_replies")
        if replies_cell:
            a_tag = replies_cell.find("a")
            if a_tag:
                text = a_tag.get_text(strip=True)
                cleaned = text.replace(",", "")
                if cleaned.isdigit():
                    replies = int(cleaned)

        # Extract views from the script tag inside forum_topic_views cell
        views_cell = row.find("td", id="forum_topic_views")
        if views_cell:
            script_tag = views_cell.find("script")
            if script_tag and script_tag.string:
                # Extract number from: document.write(abbrNum(366221,1));
                match = re.search(r'abbrNum\((\d+)', script_tag.string)
                if match:
                    views = int(match.group(1))


        # Parse date from the last cell
        for cell in cells:
            text = cell.get_text(strip=True)
            # Lowyat date format: "24th March 2026 - 04:31 PMLast post by:zlewe"
            month_names = ["January", "February", "March", "April", "May", "June",
                           "July", "August", "September", "October", "November", "December"]
            if any(month in text for month in month_names):
                try:
                    # Extract date part before the dash
                    date_part = text.split("-")[0].strip()
                    # Remove ordinal suffixes like "th", "st", "nd", "rd"
                    date_part = re.sub(r'(st|nd|rd|th)', '', date_part).strip()
                    last_activity = datetime.strptime(date_part, "%d %B %Y")
                except Exception:
                    pass

        threads.append({
            "title": title,
            "url": full_url,
            "replies": replies,
            "views": views,
            "last_activity": last_activity,
        })

    return threads


def get_next_page_url(soup):
    """Find the next page URL from pagination links."""
    # Lowyat pagination: [2] -> /Jobs&Careers/+30, [3] -> /Jobs&Careers/+60
    # The ">" link points to the next page
    for a in soup.find_all("a", href=True):
        text = a.get_text(strip=True)
        href = a["href"]
        if text == ">" and "/Jobs&Careers/" in href:
            return urljoin(BASE_URL, href)
    return None


def is_within_current_month(thread):
    """Check if thread activity is within the current month."""
    if thread["last_activity"]:
        return (
            thread["last_activity"].month == current_month
            and thread["last_activity"].year == current_year
        )
    # If no date found, include it by default (conservative approach)
    return True


# ============================================================
# Telegram sender
# ============================================================

def send_to_telegram(message):
    """Send a message to Telegram using bot token and chat ID from .env."""
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"

    payload = {
        "chat_id": TELEGRAM_CHAT_ID,
        "text": message,
        "parse_mode": "HTML"
    }

    response = requests.post(url, json=payload, timeout=10)
    response.raise_for_status()
    return response.json()


# ============================================================
# MAIN CRAWL
# ============================================================


print(f"Fetching: {START_URL}")
response = session.get(START_URL, timeout=20)
print(f"Status: {response.status_code}")

soup = BeautifulSoup(response.text, "lxml")
print(f"Page title: {soup.title.text.strip() if soup.title else 'N/A'}")

# Parse first page
page_threads = parse_threads_from_page(soup)
all_threads.extend(page_threads)
print(f"Threads found on page 1: {len(page_threads)}")

# Crawl additional pages (up to 5 pages max)
max_pages = 5
for page_num in range(2, max_pages + 1):
    next_url = get_next_page_url(soup)
    if not next_url:
        print("No more pages found.")
        break

    print(f"\nFetching page {page_num}: {next_url}")
    time.sleep(1.5)  # Polite delay

    response = session.get(next_url, timeout=20)
    soup = BeautifulSoup(response.text, "lxml")

    page_threads = parse_threads_from_page(soup)
    all_threads.extend(page_threads)
    print(f"Threads found on page {page_num}: {len(page_threads)}")

    # Stop if no threads found
    if not page_threads:
        break

print(f"\n{'='*60}")
print(f"Total unique threads collected: {len(all_threads)}")

# ============================================================
# FILTER: Keep only threads active this month
# ============================================================

this_month_threads = [t for t in all_threads if is_within_current_month(t)]
print(f"Threads active in {now.strftime('%B %Y')}: {len(this_month_threads)}")

# ============================================================
# SORT: Sort by most recent activity, take latest 10
# ============================================================

recent_threads = sorted(
    this_month_threads,
    key=lambda x: x["last_activity"] or datetime.min,
    reverse=True
)[:10]

print(f"\n{'='*60}")
print(f"LATEST 10 JOBS & CAREERS THREADS — {now.strftime('%B %Y')}")
print(f"{'='*60}\n")

for i, thread in enumerate(recent_threads, 1):
    print(f"{i:>2}. {thread['title']}")
    print(f"    Replies: {thread['replies']}  |  Views: {thread['views']:,}")
    if thread["last_activity"]:
        print(f"    Last activity: {thread['last_activity'].strftime('%b %d %Y')}")
    print(f"    URL: {thread['url']}")
    print()

# ============================================================
# SEND LATEST 10 TO TELEGRAM
# ============================================================

telegram_message = f"<b>LATEST 10 JOBS & CAREERS THREADS — {now.strftime('%B %Y')}</b>\n\n"

for i, thread in enumerate(recent_threads, 1):
    telegram_message += (
        f"{i}. <b>{thread['title']}</b>\n"
        f"   Replies: {thread['replies']}  |  Views: {thread['views']:,}\n"
        f"   {thread['url']}\n\n"
    )

print("Sending top 10 to Telegram...")
send_to_telegram(telegram_message)
print("Done! Check your Telegram.")


