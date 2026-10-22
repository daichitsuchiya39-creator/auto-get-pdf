# 研究費・公募情報 PDF 収集システム

`config/sites.yaml` に登録した Web ページを巡回し、ページ内の PDF を自動でダウンロードします。

- 取得先はサイト別・日付別のフォルダに整理して保存します
- 取得済みの PDF は重複判定（URL と SHA256）で除外するので、毎日実行しても新しい PDF だけが増えます
- 実行の記録は `logs/` に残ります

---

## 1. はじめて使う（GitHub から入手）

必要なもの：Git、Python 3.12 以上

```bash
# 1) 入手
git clone https://github.com/daichitsuchiya39-creator/auto-get-pdf.git
cd auto-get-pdf

# 2) ライブラリをインストール（初回のみ）
pip install -r requirements.txt

# 3) 実行
python src/main.py
```


実行すると `data/` と `logs/` が自動で作られ、PDF が保存されます。

---

## 2. 使い方

```bash
python src/main.py                    # 登録した全サイトを巡回
python src/main.py --site IPA         # 指定したサイトだけ実行
python src/main.py --site IPA --site JST   # 複数指定
python -m src.main                    # 別の起動方法（結果は同じ）
```

| オプション | 説明 |
|---|---|
| `--config PATH` | 設定ファイル（既定: `config/sites.yaml`） |
| `--site NAME` | 指定サイトのみ実行（複数指定可） |
| `--data-dir PATH` | PDF の保存先（既定: `data/`） |
| `--log-dir PATH` | ログの出力先（既定: `logs/`） |

終了コード：すべて成功なら `0`、サイト取得の失敗やダウンロード失敗が 1 件でもあれば `1`。

### 巡回サイトを増やす

`config/sites.yaml` の `sites` に追記します。`name` が保存フォルダ名になります。

```yaml
sites:
  - name: 文部科学省
    url: https://www.mext.go.jp/...
```

`settings` では、タイムアウト・リトライ回数・リクエスト間隔などを変更できます。

> 巡回するのは、URL に書いた**そのページ 1 枚だけ**です。リンク先のページはたどりません。
> PDF が一覧ページの先にあるサイトは、一覧ページの URL を指定してください。

---

## 3. 出力

```text
data/
├─ index.json            # 取得済み PDF の台帳（SHA256 → 取得元URL・保存先・分類など）
├─ IPA/
│   └─ 2026-10-22/
│       ├─ sample.pdf
│       └─ sample_1.pdf  # 同名・別内容のファイルは連番で保存
└─ JST/
    └─ 2026-10-22/
logs/
└─ 2026-10-22.log
```

取得日のフォルダは、その日に新規 PDF を保存したサイトにのみ作成されます。

### 重複判定

1. `skip_known_urls: true`（既定）なら、台帳に登録済みの URL はダウンロードしません。
2. ダウンロードしたファイルの SHA256 が台帳にあれば、保存せず破棄します（URL が違っても内容が同じなら重複）。

同じ URL の PDF が更新されたかも確認したい場合は `skip_known_urls: false` にしてください。

---

## 4. Git で管理する（開発者向け）

### Git に含めるもの・含めないもの

| 含める | 含めない（`.gitignore` 済み） |
|---|---|
| `src/`、`config/sites.yaml`、`requirements.txt`、`README.md` | `data/`（取得した PDF と台帳） |
| | `logs/`（実行ログ） |
| | `__pycache__/`、`.venv/` |

取得した PDF は容量が大きく、実行のたびに変わるため、Git には入れません。
PDF を共有したい場合は、共有フォルダなど別の方法を使ってください。

### 変更をリポジトリに反映する（push）

```bash
git status                       # 変更の確認
git add .
git commit -m "巡回サイトにNEDOを追加"
git push
```

巡回サイトの追加は `config/sites.yaml` の変更だけで済むので、コミットも小さくなります。

### 最新版を取り込む（pull）

```bash
git pull
pip install -r requirements.txt   # requirements.txt が更新されたときだけ
```

### 新しくリポジトリを作る場合

```bash
git init
git add .
git commit -m "初回コミット"
git branch -M main
git remote add origin https://github.com/daichitsuchiya39-creator/auto-get-pdf.git
git push -u origin main
```

> **注意：** `config/sites.yaml` に、パスワードや個人のトークンが入った URL を書かないでください。
> GitHub に公開される可能性があります。

---

## 5. 定期的に自動で実行する（Windows）

プログラム自体に定期実行の機能はありません。Windows のタスクスケジューラに登録します。

```powershell
schtasks /create /tn "PDF自動取得" /sc daily /st 08:00 /tr "python C:\パス\src\main.py"
```

`C:\パス` は、実際のプロジェクトの場所に書き換えてください。

---

## 6. モジュール構成

| ファイル | クラス | 責務 |
|---|---|---|
| `src/crawler.py` | `Crawler` / `PdfExtractor` | HTML 取得（リトライ・タイムアウト） / PDF リンク抽出（`.pdf` `.PDF`） |
| `src/downloader.py` | `Downloader` | PDF ダウンロード・SHA256 計算 |
| `src/pdf_manager.py` | `FileManager` / `PdfIndex` | 保存先フォルダ管理・連番保存 / 取得済み台帳 |
| `src/file_classifier.py` | `KeywordClassifier` | 分類タグ付け（現状はキーワード判定） |
| `src/logger.py` | — | ログ出力 |
| `src/main.py` | — | CLI・処理フロー |

## 7. 将来拡張

- **PDF 内容解析・AI 要約（Phase2）**: `data/index.json` の各レコードに保存パスとリンク文字列が入っているため、
  ここを入力に pymupdf / pdfplumber でテキスト抽出 → LLM で要約し、`title` `deadline` `summary` を追記する処理を追加できます。
- **AI 分類**: `file_classifier.Classifier` を継承した分類器を作り、`main.build_classifier()` で差し替えます。
- **通知**: `main.collect_site()` で新規保存したタイミング（`SUCCESS` ログ直後）に通知処理を追加できます。
- **リンクをたどる巡回**: ページ内のリンク先も巡回する機能を追加できます。
- **JavaScript で描画されるサイト**: `Crawler.fetch()` を Playwright 版に差し替えます。
