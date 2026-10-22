"""PDF ダウンロード（タイムアウト・リトライ・SHA256 計算）"""

import hashlib
import re
import time
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import unquote, urlparse

import requests

from src.crawler import is_retryable
from src.logger import get_logger

CHUNK_SIZE = 64 * 1024


@dataclass
class DownloadResult:
    path: Path        # 保存したファイル（一時ファイル）
    sha256: str
    size: int
    filename: str     # サーバが示すファイル名（Content-Disposition / URL 由来）


class Downloader:
    """URL のファイルを path に保存し、SHA256 を返す。"""

    def __init__(self, session: requests.Session, timeout: float = 30, max_retries: int = 3):
        self.session = session
        self.timeout = timeout
        self.max_retries = max_retries
        self.log = get_logger()

    def download(self, url: str, path: Path) -> DownloadResult:
        last_error: Exception | None = None
        for attempt in range(1, self.max_retries + 1):
            try:
                return self._download_once(url, path)
            except (requests.RequestException, OSError) as e:
                last_error = e
                path.unlink(missing_ok=True)
                if not is_retryable(e):
                    break
                self.log.warning(f"DOWNLOAD RETRY ({attempt}/{self.max_retries}): {url} - {e}")
                if attempt < self.max_retries:
                    time.sleep(2 * attempt)
        raise RuntimeError(f"ダウンロードに失敗しました ({last_error})") from last_error

    def _download_once(self, url: str, path: Path) -> DownloadResult:
        path.parent.mkdir(parents=True, exist_ok=True)
        sha = hashlib.sha256()
        size = 0
        with self.session.get(url, timeout=self.timeout, stream=True) as resp:
            resp.raise_for_status()
            filename = filename_from_response(resp, url)
            with open(path, "wb") as f:
                for chunk in resp.iter_content(CHUNK_SIZE):
                    if chunk:
                        f.write(chunk)
                        sha.update(chunk)
                        size += len(chunk)
        return DownloadResult(path=path, sha256=sha.hexdigest(), size=size, filename=filename)


def filename_from_response(resp: requests.Response, url: str) -> str:
    cd = resp.headers.get("Content-Disposition", "")
    name = None
    m = re.search(r"filename\*\s*=\s*[^']*''([^;]+)", cd, re.IGNORECASE)
    if m:
        name = unquote(m.group(1).strip('"'))
    else:
        m = re.search(r'filename\s*=\s*"?([^";]+)"?', cd, re.IGNORECASE)
        if m:
            name = m.group(1)
    if not name:
        name = unquote(Path(urlparse(url).path).name)
    return sanitize_filename(name or "download.pdf")


def sanitize_filename(name: str) -> str:
    """Windows / Linux 双方で使えるファイル名に整える。"""
    name = re.sub(r'[\\/:*?"<>|\x00-\x1f]', "_", name).strip(" .")
    if not name.lower().endswith(".pdf"):
        name += ".pdf"
    stem, ext = name[:-4], name[-4:]
    return stem[:150] + ext
