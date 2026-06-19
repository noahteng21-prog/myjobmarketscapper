import requests
from bs4 import BeautifulSoup

# This script scrapes the Lowyat.NET Jobs & Careers forum page.
# It fetches the HTML, parses it with BeautifulSoup, prints the page title,
# and lists the first 30 hyperlinks found on the page.
#
# 3 questions (3Q):
# 1) Is the target URL correct and publicly accessible?
# 2) Do you want to save the scraped links instead of printing them?
# 3) Should the script follow pagination or only scrape this single page?

url = "https://forum.lowyat.net/Jobs&Careers"

headers = {
    "User-Agent": "Mozilla/5.0"
}

# Send HTTP GET request with a browser-like User-Agent header.
response = requests.get(url, headers=headers)

# Print the HTTP status code to confirm whether the request succeeded.
print(response.status_code)

# Parse the page HTML using the lxml parser.
soup = BeautifulSoup(response.text, "lxml")

# Print the title of the page for quick verification.
print(soup.title.text)

# Find all anchor tags in the page.
links = soup.find_all("a")

print(f"Found {len(links)} links\n")

# Loop through every link
for link in links:

    # Get the href attribute (the URL)
    href = link.get("href")

    # Only keep links that look like forum topics
    if href and href.startswith("/topic/"):
        print("--------------------")
        print("Title:", link.get_text(strip=True))
        print("URL  :", href)