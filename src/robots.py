"""robots.txt の確認（RobotsChecker）"""

from urllib.parse import urlparse
from urllib.robotparser import RobotFileParser

import requests

from src.logger import get_logger

# robots.txt の User-agent 行と照合する名前（UA 文字列全体ではなく製品トークン）
ROBOTS_AGENT = "PdfCollector"


class RobotsChecker:
    """URL が robots.txt で取得を許可されているかを確認する。オリジンごとに結果をキャッシュする。"""

    def __init__(self, session: requests.Session, timeout: float = 30, enabled: bool = True):
        self.session = session
        self.timeout = timeout
        self.enabled = enabled
        self.log = get_logger()
        self._parsers: dict[str, RobotFileParser] = {}

    def allowed(self, url: str) -> bool:
        if not self.enabled:
            return True
        parsed = urlparse(url)
        origin = f"{parsed.scheme}://{parsed.netloc}"
        if origin not in self._parsers:
            self._parsers[origin] = self._load(origin)
        return self._parsers[origin].can_fetch(ROBOTS_AGENT, url)

    def _load(self, origin: str) -> RobotFileParser:
        parser = RobotFileParser()
        robots_url = f"{origin}/robots.txt"
        try:
            resp = self.session.get(robots_url, timeout=self.timeout)
        except requests.RequestException as e:
            # 確認できないときは安全側（取得しない）に倒す
            self.log.warning(f"ROBOTS: {robots_url} を取得できないため、このサイトは取得しません - {e}")
            parser.disallow_all = True
            return parser

        if resp.status_code in (401, 403) or resp.status_code >= 500:
            self.log.warning(f"ROBOTS: {robots_url} が {resp.status_code} のため、このサイトは取得しません")
            parser.disallow_all = True
        elif resp.status_code >= 400:
            parser.allow_all = True  # robots.txt が無いサイトは制限なし
        else:
            if resp.encoding is None or resp.encoding.lower() == "iso-8859-1":
                resp.encoding = "utf-8"
            parser.parse(resp.text.splitlines())
        return parser
