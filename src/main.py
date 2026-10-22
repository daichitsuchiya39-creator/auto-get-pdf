"""PDF 収集 CLI

実行:
    python src/main.py
    python -m src.main
    python src/main.py --config config/sites.yaml --site JST
"""

import argparse
import sys
import time
from datetime import datetime
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:  # python src/main.py で実行された場合に src パッケージを解決する
    sys.path.insert(0, str(PROJECT_ROOT))

import yaml  # noqa: E402
from tqdm import tqdm  # noqa: E402

from src.crawler import DEFAULT_USER_AGENT, Crawler, PdfExtractor  # noqa: E402
from src.downloader import Downloader  # noqa: E402
from src.file_classifier import Classifier, KeywordClassifier  # noqa: E402
from src.logger import setup_logger  # noqa: E402
from src.pdf_manager import FileManager, PdfIndex  # noqa: E402

DEFAULT_SETTINGS = {
    "timeout": 30,
    "max_retries": 3,
    "request_interval": 1.0,
    "skip_known_urls": True,
    "user_agent": DEFAULT_USER_AGENT,
}


def load_config(path: Path) -> tuple[list[dict], dict]:
    with open(path, encoding="utf-8") as f:
        config = yaml.safe_load(f) or {}
    sites = config.get("sites") or []
    for site in sites:
        if not site.get("name") or not site.get("url"):
            raise ValueError(f"sites.yaml の各サイトには name と url が必要です: {site}")
    settings = {**DEFAULT_SETTINGS, **(config.get("settings") or {})}
    return sites, settings


def build_classifier() -> Classifier:
    # 将来は AI 分類器（OpenAI API 等）に差し替える
    return KeywordClassifier()


def collect_site(site: dict, crawler: Crawler, extractor: PdfExtractor, downloader: Downloader,
                 files: FileManager, index: PdfIndex, classifier: Classifier, settings: dict, log) -> dict:
    name, url = site["name"], site["url"]
    stats = {"found": 0, "downloaded": 0, "skipped": 0, "failed": 0}
    log.info(f"SITE: {name} {url}")

    html = crawler.fetch(url)
    links = extractor.extract_pdf_entries(html, base_url=url)
    stats["found"] = len(links)
    log.info(f"PDF LINKS: {len(links)}")

    for link in tqdm(links, desc=name, unit="pdf", leave=False):
        if settings["skip_known_urls"] and index.has_url(link.url):
            stats["skipped"] += 1
            log.info(f"SKIP (取得済みURL): {link.url}")
            continue

        time.sleep(settings["request_interval"])
        tmp = files.temp_path(name)
        try:
            result = downloader.download(link.url, tmp)
        except Exception as e:
            stats["failed"] += 1
            log.error(f"FAILED: {link.url} - {e}")
            continue

        if index.has_hash(result.sha256):
            tmp.unlink(missing_ok=True)
            stats["skipped"] += 1
            log.info(f"SKIP (重複 SHA256): {result.filename}")
            continue

        log.info(f"DOWNLOAD: {result.filename}")
        saved = files.save_file(tmp, name, result.filename)
        index.add(result.sha256, {
            "site": name,
            "url": link.url,
            "page_url": url,
            "link_text": link.text,
            "path": saved.relative_to(files.data_dir).as_posix(),
            "size": result.size,
            "downloaded_at": datetime.now().isoformat(timespec="seconds"),
            "categories": classifier.classify(f"{link.text} {result.filename}"),
            # Phase2 で "title" / "agency" / "deadline" / "summary" を追記する
        })
        index.save()
        stats["downloaded"] += 1
        log.info(f"SUCCESS: {saved}")

    return stats


def parse_args(argv: list[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="指定サイトを巡回して PDF を収集します。")
    parser.add_argument("--config", type=Path, default=PROJECT_ROOT / "config" / "sites.yaml",
                        help="サイト設定ファイル (既定: config/sites.yaml)")
    parser.add_argument("--data-dir", type=Path, default=PROJECT_ROOT / "data", help="PDF 保存先")
    parser.add_argument("--log-dir", type=Path, default=PROJECT_ROOT / "logs", help="ログ出力先")
    parser.add_argument("--site", action="append", help="対象サイト名で絞り込み（複数指定可）")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    log = setup_logger(args.log_dir)
    log.info("START")

    try:
        sites, settings = load_config(args.config)
    except Exception as e:
        log.error(f"設定ファイルの読み込みに失敗しました: {args.config} - {e}")
        log.info("END")
        return 1

    if args.site:
        sites = [s for s in sites if s["name"] in args.site]
    if not sites:
        log.warning("対象サイトがありません")

    crawler = Crawler(timeout=settings["timeout"], max_retries=settings["max_retries"],
                      user_agent=settings["user_agent"])
    downloader = Downloader(crawler.session, timeout=settings["timeout"], max_retries=settings["max_retries"])
    extractor = PdfExtractor()
    files = FileManager(args.data_dir)
    index = PdfIndex(args.data_dir)
    classifier = build_classifier()

    total = {"found": 0, "downloaded": 0, "skipped": 0, "failed": 0}
    failed_sites = []
    for site in sites:
        try:
            stats = collect_site(site, crawler, extractor, downloader, files, index, classifier, settings, log)
        except Exception as e:
            failed_sites.append(site["name"])
            log.error(f"SITE FAILED: {site['name']} - {e}")
            continue
        for k in total:
            total[k] += stats[k]
        log.info(f"SITE DONE: {site['name']} "
                 f"(検出 {stats['found']} / 新規 {stats['downloaded']} / スキップ {stats['skipped']} / 失敗 {stats['failed']})")

    log.info(f"SUMMARY: 検出 {total['found']} / 新規 {total['downloaded']} / "
             f"スキップ {total['skipped']} / 失敗 {total['failed']} / サイトエラー {len(failed_sites)}")
    log.info("END")
    return 1 if failed_sites or total["failed"] else 0


if __name__ == "__main__":
    sys.exit(main())
