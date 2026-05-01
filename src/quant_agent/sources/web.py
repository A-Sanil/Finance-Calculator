from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List
from urllib.parse import urlparse

import requests
from bs4 import BeautifulSoup
from feedparser import parse as parse_feed


@dataclass
class WebSourceClient:
    timeout: int = 30

    def fetch_url(self, url: str) -> Dict[str, str]:
        response = requests.get(url, timeout=self.timeout, headers={"User-Agent": "quant-agent/0.1"})
        response.raise_for_status()
        soup = BeautifulSoup(response.text, "html.parser")
        text = " ".join(part.strip() for part in soup.get_text(" ").split())
        title = soup.title.text.strip() if soup.title and soup.title.text else urlparse(url).netloc
        return {"url": url, "title": title, "text": text}

    def fetch_rss(self, feed_url: str, limit: int = 20) -> List[Dict[str, str]]:
        feed = parse_feed(feed_url)
        items: list[Dict[str, str]] = []
        for entry in feed.entries[:limit]:
            items.append(
                {
                    "url": entry.get("link", ""),
                    "title": entry.get("title", ""),
                    "summary": entry.get("summary", ""),
                    "published": entry.get("published", ""),
                }
            )
        return items
