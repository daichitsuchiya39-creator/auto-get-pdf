"""保存先管理（FileManager）と取得済み PDF の台帳（SHA256 重複判定）"""

import json
import shutil
from datetime import datetime
from pathlib import Path

from src.downloader import sanitize_filename

INDEX_FILENAME = "index.json"


class FileManager:
    """data/<サイト名>/<取得日>/ の作成とファイル保存を担う。"""

    def __init__(self, data_dir: Path, run_date: str | None = None):
        self.data_dir = data_dir
        self.run_date = run_date or f"{datetime.now():%Y-%m-%d}"
        self.data_dir.mkdir(parents=True, exist_ok=True)

    def create_folder(self, site_name: str) -> Path:
        folder = self.data_dir / sanitize_dirname(site_name) / self.run_date
        folder.mkdir(parents=True, exist_ok=True)
        return folder

    def temp_path(self, site_name: str) -> Path:
        """ダウンロード中の一時ファイル。重複判定後に save_file で正式名へ移動する。"""
        tmp_dir = self.data_dir / ".tmp"
        tmp_dir.mkdir(parents=True, exist_ok=True)
        return tmp_dir / f"{sanitize_dirname(site_name)}_{datetime.now():%H%M%S%f}.part"

    def save_file(self, src: Path, site_name: str, filename: str) -> Path:
        """同名ファイルがあれば sample_1.pdf, sample_2.pdf ... として保存する。"""
        folder = self.create_folder(site_name)
        dest = unique_path(folder / filename)
        shutil.move(str(src), dest)
        return dest


class PdfIndex:
    """取得済み PDF の台帳（data/index.json）。SHA256 をキーに保持する。

    各レコードは将来の AI 要約・分類の入力にも使えるよう、
    取得元やリンク文字列などのメタデータを保持する。
    """

    def __init__(self, data_dir: Path):
        self.path = data_dir / INDEX_FILENAME
        self.records: dict[str, dict] = {}
        if self.path.exists():
            self.records = json.loads(self.path.read_text(encoding="utf-8"))
        self._urls = {r["url"] for r in self.records.values()}

    def has_hash(self, sha256: str) -> bool:
        return sha256 in self.records

    def has_url(self, url: str) -> bool:
        return url in self._urls

    def add(self, sha256: str, record: dict) -> None:
        self.records[sha256] = record
        self._urls.add(record["url"])

    def save(self) -> None:
        tmp = self.path.with_suffix(".json.tmp")
        tmp.write_text(json.dumps(self.records, ensure_ascii=False, indent=2), encoding="utf-8")
        tmp.replace(self.path)


def unique_path(path: Path) -> Path:
    if not path.exists():
        return path
    i = 1
    while True:
        candidate = path.with_name(f"{path.stem}_{i}{path.suffix}")
        if not candidate.exists():
            return candidate
        i += 1


def sanitize_dirname(name: str) -> str:
    return sanitize_filename(name)[:-4] or "site"
