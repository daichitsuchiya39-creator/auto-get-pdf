"""HTML取得（Crawler）と PDF リンク抽出（PdfExtractor）"""

import time
from dataclasses import dataclass
from urllib.parse import unquote, urldefrag, urljoin, urlparse

import requests
from bs4 import BeautifulSoup

from src.logger import get_logger

DEFAULT_USER_AGENT = "Mozilla/5.0 (compatible; PdfCollector/1.0)"


class Crawler:
    """指定 URL の HTML を取得する。"""

    def __init__(self, session: requests.Session | None = None, timeout: float = 30,
                 max_retries: int = 3, user_agent: str = DEFAULT_USER_AGENT):
        self.session = session or requests.Session()
        self.session.headers.setdefault("User-Agent", user_agent)
        self.timeout = timeout
        self.max_retries = max_retries
        self.log = get_logger()

    def fetch(self, url: str) -> str:
        """HTML を文字列で返す。最大 max_retries 回まで再試行し、全て失敗したら例外を送出する。"""
        last_error: Exception | None = None
        for attempt in range(1, self.max_retries + 1):
            try:
                resp = self.session.get(url, timeout=self.timeout)
                resp.raise_for_status()
                # Content-Type に charset が無い日本語サイト（Shift_JIS 等）の文字化け対策
                if resp.encoding is None or resp.encoding.lower() == "iso-8859-1":
                    resp.encoding = resp.apparent_encoding
                return resp.text
            except requests.RequestException as e:
                last_error = e
                if not is_retryable(e):
                    break
                self.log.warning(f"FETCH RETRY ({attempt}/{self.max_retries}): {url} - {e}")
                if attempt < self.max_retries:
                    time.sleep(2 * attempt)
        raise RuntimeError(f"HTML取得に失敗しました: {url} ({last_error})") from last_error


def is_retryable(error: Exception) -> bool:
    """404 等のクライアントエラーは再試行しても結果が変わらないため再試行しない。"""
    if isinstance(error, requests.HTTPError) and error.response is not None:
        status = error.response.status_code
        return status >= 500 or status in (408, 429)
    return True


@dataclass(frozen=True)
class PdfLink:
    url: str
    text: str  # リンク文字列（公募名などの手掛かり。将来の AI 要約・分類で利用）


class PdfExtractor:
    """HTML から PDF の URL を抽出する。"""

    # (タグ名, URL を持つ属性)
    TARGETS = (("a", "href"), ("embed", "src"), ("iframe", "src"), ("object", "data"))

    def extract_pdf_links(self, html: str, base_url: str | None = None) -> list[str]:
        return [link.url for link in self.extract_pdf_entries(html, base_url)]

    def extract_pdf_entries(self, html: str, base_url: str | None = None) -> list[PdfLink]:
        soup = BeautifulSoup(html, "html.parser")

        base_tag = soup.find("base", href=True)
        if base_tag:
            base_url = urljoin(base_url or "", base_tag["href"])

        results: list[PdfLink] = []
        seen: set[str] = set()
        for tag_name, attr in self.TARGETS:
            for tag in soup.find_all(tag_name, attrs={attr: True}):
                raw = tag[attr].strip()
                if not raw or raw.lower().startswith(("javascript:", "mailto:")):
                    continue
                url, _ = urldefrag(urljoin(base_url or "", raw))
                if not self.is_pdf_url(url) or url in seen:
                    continue
                seen.add(url)
                results.append(PdfLink(url=url, text=tag.get_text(" ", strip=True)))
        return results

    @staticmethod
    def is_pdf_url(url: str) -> bool:
        parsed = urlparse(url)
        if parsed.scheme not in ("http", "https"):
            return False
        return unquote(parsed.path).lower().endswith(".pdf")  # .pdf / .PDF 両対応
