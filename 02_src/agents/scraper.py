"""Web scraping utilities for external market and competitor data."""

import re
import time

import requests
from bs4 import BeautifulSoup

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    )
}


def scrape_page(url: str, max_chars: int = 2500) -> str:
    try:
        if not url.startswith("http"):
            url = "https://" + url
        resp = requests.get(url, headers=HEADERS, timeout=10)
        resp.raise_for_status()
        soup = BeautifulSoup(resp.text, "html.parser")
        for tag in soup(["script", "style", "nav", "footer", "header", "aside"]):
            tag.decompose()
        text = re.sub(r"\s+", " ", soup.get_text(separator=" ", strip=True))
        return text[:max_chars]
    except Exception as exc:
        return f"Could not scrape {url}: {exc}"


def scrape_website(url: str) -> dict:
    base = url.rstrip("/")
    pages = {}
    for name, path in [("homepage", ""), ("about", "/about"), ("services", "/services")]:
        pages[name] = scrape_page(base + path)
        time.sleep(0.5)
    return pages


def scrape_competitor(domain: str) -> dict:
    base = domain.replace("https://", "").replace("http://", "").rstrip("/")
    base_url = f"https://{base}"
    return {
        "domain": domain,
        "homepage": scrape_page(base_url),
        "about": scrape_page(base_url + "/about"),
    }


def scrape_industry_news(company: str, industry: str, year: str = "2025") -> str:
    queries = [
        f"{industry} market trends {year}",
        f"{industry} enterprise challenges {year}",
        f"{company} news",
    ]
    lines = []
    for query in queries:
        try:
            rss_url = (
                "https://news.google.com/rss/search?"
                f"q={requests.utils.quote(query)}&hl=en-US&gl=US&ceid=US:en"
            )
            resp = requests.get(rss_url, headers=HEADERS, timeout=8)
            soup = BeautifulSoup(resp.text, "xml")
            lines.append(f"## Query: {query}")
            for item in soup.find_all("item")[:4]:
                title = item.find("title")
                if title:
                    lines.append(f"- {title.get_text(strip=True)}")
            time.sleep(0.3)
        except Exception as exc:
            lines.append(f"News unavailable for '{query}': {exc}")
    return "\n".join(lines)
