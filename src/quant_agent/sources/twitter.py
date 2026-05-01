from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List

try:
    import snscrape.modules.twitter as sntwitter
except Exception:  # pragma: no cover - fallback for environments where snscrape is unavailable
    sntwitter = None


@dataclass
class TwitterClient:
    def search(self, query: str, limit: int = 20) -> List[Dict[str, str]]:
        if sntwitter is None:
            return [
                {
                    "id": "bootstrap-twitter-1",
                    "text": f"Twitter source unavailable; bootstrap result for {query}.",
                    "user": "bootstrap",
                    "url": "https://twitter.com",
                }
            ]

        results: list[Dict[str, str]] = []
        try:
            for item in sntwitter.TwitterSearchScraper(query).get_items():
                results.append(
                    {
                        "id": str(item.id),
                        "text": item.content,
                        "user": getattr(item.user, "username", ""),
                        "url": getattr(item, "url", ""),
                    }
                )
                if len(results) >= limit:
                    break
        except Exception:
            return [
                {
                    "id": "bootstrap-twitter-1",
                    "text": f"Twitter scraping unavailable; bootstrap result for {query}.",
                    "user": "bootstrap",
                    "url": "https://twitter.com",
                }
            ]
        return results or [
            {
                "id": "bootstrap-twitter-1",
                "text": f"Twitter returned no items; bootstrap result for {query}.",
                "user": "bootstrap",
                "url": "https://twitter.com",
            }
        ]
