"""Web content extractor and cleaner for full-text news articles."""

from __future__ import annotations
import re
import logging
from typing import Optional
import httpx
from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)


class ArticleExtractor:
    """Extracts clean text content from news URLs."""

    DEFAULT_HEADERS = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.9",
    }

    def __init__(self, timeout: float = 3.0):
        self.timeout = timeout

    async def extract(self, url: str) -> str:
        """Fetch URL and extract the substantive text body."""
        if not url or not url.startswith("http"):
            return ""

        try:
            async with httpx.AsyncClient(
                headers=self.DEFAULT_HEADERS,
                timeout=self.timeout,
                follow_redirects=True,
                verify=False
            ) as client:
                resp = await client.get(url)
                if resp.status_code != 200:
                    return ""

                return self.clean_html(resp.text)
        except Exception as e:
            logger.debug(f"Failed to extract content from {url}: {e}")
            return ""

    @staticmethod
    def clean_html(html_text: str) -> str:
        """Parse HTML, remove ads/scripts, and return substantive text."""
        if not html_text:
            return ""

        soup = BeautifulSoup(html_text, "html.parser")

        # Strip unneeded tags
        for element in soup(["script", "style", "nav", "footer", "header", "noscript", "aside", "form", "svg"]):
            element.decompose()

        main_content = (
            soup.find("article")
            or soup.find("main")
            or soup.find("div", class_=re.compile(r"article[-_]body|post[-_]content|story[-_]content|entry[-_]content", re.I))
            or soup.body
        )

        if not main_content:
            return ""

        paragraphs = main_content.find_all("p")
        if paragraphs:
            text_chunks = [p.get_text(separator=" ", strip=True) for p in paragraphs if len(p.get_text(strip=True)) > 25]
            full_text = "\n\n".join(text_chunks)
        else:
            full_text = main_content.get_text(separator=" ", strip=True)

        full_text = re.sub(r"\s+", " ", full_text).strip()
        if len(full_text) > 4000:
            full_text = full_text[:4000] + "..."

        return full_text
