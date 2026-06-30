# Threads Affiliate Auto-Operation MVP

Gemini API、Firestore、Threads APIを前提にした Threads アフィリエイト自動運用システムのMVPです。初期運用では `DRY_RUN=true` をデフォルトとし、外部API本番投稿やASP API完全連携は行いません。

## 実装範囲

- ローカルJSON/CSVから `product_candidates` へ商品候補を投入
- Gemini `google-genai` SDKによる一次スコアリング用クライアント
- `accepted` / `review` / `rejected` の状態遷移と `products` / `review_products` への振り分け
- Python純粋関数によるROI計算と `enriched_products` 保存
- `affiliate` / `two_line_copy` / `story` の投稿候補生成
- Python側のPR表記、500文字、URL数、A8直接リンク、薬機法・誇大表現、アフィリエイト臭表現チェック
- DRY_RUN時のThreads投稿抑止と `post_logs` への `dry_run_success` 保存
- Firestore未接続時に使えるJSON永続ローカルモック

## 未実装・今後の範囲

- Amazon PA-API、楽天API、A8.net APIの本番連携
- GAS / Spreadsheet 自動同期
- Cloud Tasksによる投稿キュー分散、Threadsレート制限の動的監視
- BigQueryへのエンゲージメント・クリックログ集約
- Secret Managerからの実シークレット読み込み

## セットアップ

Python 3.11+ を推奨します。

```bash
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
cp .env.example .env
```

`.env` の主な設定:

```env
GCP_PROJECT_ID=your-gcp-project-id
GEMINI_API_KEY=
GEMINI_MODEL=gemini-2.0-flash
THREADS_ACCESS_TOKEN=
THREADS_USER_ID=
DRY_RUN=true
DEFAULT_HOURLY_VALUE=2000
TARGET_PLATFORM=threads
LOG_LEVEL=INFO
LOCAL_FIRESTORE_PATH=.local/firestore_mock.json
```

## ローカル実行

```bash
python -m src.cli ingest-products --file sample_products.json
python -m src.cli score-products --limit 10
python -m src.cli enrich-products --limit 10
python -m src.cli generate-posts --limit 10
python -m src.cli quality-check-posts --limit 10
python -m src.cli publish-posts --dry-run --limit 5
python -m src.cli run-mvp --limit 5
```

互換入口として、既存形式も残しています。

```bash
python -m src.main --mode all --limit 5
```

`DRY_RUN=true` では Firestore の代わりに `.local/firestore_mock.json` に保存され、Threads APIには投稿しません。

## ローカル投稿確認

まずdry-runで投稿フェーズまで通します。

```powershell
$env:DRY_RUN="true"
$env:LOCAL_FIRESTORE_PATH="C:\work\sns-af\.local\threads_local_check.json"
python -m src.cli run-mvp --limit 2
```

確認ポイント:

- `.local/threads_local_check.json` に `post_logs` が保存される
- `post_logs.result` が `dry_run_success`
- `post_candidates.post_text` の冒頭PR表記、文字数、URL数、NG表現を確認する

本番投稿確認は、本文を確認した後に1件だけ行います。

```powershell
$env:THREADS_ACCESS_TOKEN="..."
$env:THREADS_USER_ID="..."
$env:DRY_RUN="false"
python -m src.cli publish-posts --limit 1
```

`DRY_RUN=false` では実際にThreads APIへ2段階publishを実行します。必ず `--limit 1` から始めてください。

## Firestoreコレクション

- `product_candidates`: 収集済み商品候補
- `product_scores`: Gemini一次スコア
- `products`: 採用商品
- `review_products`: 人手確認商品
- `enriched_products`: 詳細分析とROI
- `post_candidates`: 投稿候補
- `post_logs`: 投稿結果ログ

## 処理フロー

商品候補投入:

```text
local JSON / CSV
  -> product_candidates(status=fetched)
```

商品評価:

```text
product_candidates(status=fetched)
  -> Gemini scoring
  -> product_scores
  -> products(status=raw) / review_products
```

ROI付与:

```text
products(status=raw)
  -> ROI calculator
  -> enriched_products(status=enriched)
```

投稿生成:

```text
enriched_products(status=enriched)
  -> Gemini / template generation
  -> post_candidates(status=draft)
```

承認・予約:

```text
post_candidates(status=draft)
  -> human approval
  -> status=approved
  -> schedule-posts
  -> status=queued
```

投稿:

```text
post_candidates(status=queued or approved)
  -> quality checker
  -> Threads client
  -> post_logs(result=dry_run_success / success / failed)
  -> status=dry_run_posted or posted
```

現MVPでは `schedule-posts`、`publish-due-posts`、`publish-post`、`doctor`、`threads-me` は未実装です。後続拡張では以下の役割で追加する想定です。

- `schedule-posts`: JSTの投稿枠に合わせて `scheduled_at` を付与し、`MAX_DAILY_POSTS` と `MIN_POST_INTERVAL_MINUTES` で投稿間隔を平準化する
- `publish-due-posts`: `scheduled_at <= now` の `approved / queued` だけをpublish対象にする
- `publish-post`: `post_id` 指定で1件だけ最終投稿テストする
- `doctor`: GCP / Firestore / Threads / Gemini / env の疎通を確認する。secret値は表示しない
- `threads-me`: Threads APIの認証確認だけを行う。access tokenはログに出さない

## 本番投稿時の注意

本番投稿は `DRY_RUN=false`、`THREADS_ACCESS_TOKEN`、`THREADS_USER_ID` が揃った場合のみ許可されます。投稿前には必ず品質チェックを通過させてください。A8.netの直接リンクはThreads本文に入れず、プロフィールやまとめLPへの誘導に変換してください。

`DRY_RUN=true` の場合、Threads APIは呼びません。`post_logs.result=dry_run_success` を保存し、Firestore上で投稿候補と状態遷移だけを確認します。`DRY_RUN=false` の場合のみ実投稿します。

実投稿前には、後続実装予定の `threads-me` と `publish-post --dry-run` 相当の1件確認を行ってください。affiliate_urlは原則Threads本文に出さず、LP側に置きます。URL直貼りがなくても、商品紹介やLP誘導がある場合はPR表記が必要です。

CMS / LPは後続拡張としてNext.jsで実装予定です。Firestoreの `enriched_products` や将来の `cms_products` を入力に、プロフィールリンク先のまとめLPを生成する想定です。

## GCPデプロイ

Terraformは `terraform/` にあります。Cloud Run Job、Cloud Scheduler、Firestore、Secret Manager、Artifact Registryを作成します。

安全なデプロイ順:

1. `terraform/infra/terraform.tfvars` を作成し、`dry_run = true` のまま適用
2. Docker imageをArtifact Registryへpush
3. Cloud Run Jobを手動実行
4. Firestoreの `post_logs.result = dry_run_success` を確認
5. Threads Secretを登録
6. `dry_run = false` に切り替え、手動で1回だけ実行
7. 問題なければScheduler運用へ移行

詳細は [terraform/README.md](terraform/README.md) を参照してください。

## 法規制・制約

アフィリエイトURLまたはLP誘導を含む投稿は、冒頭に `【PR】` または `#PR` が必要です。末尾ハッシュタグだけのPR表記は許可しません。薬機法・誇大表現の検出はMVPの静的チェックであり、法的な完全保証ではありません。外部ASP APIの利用には各社の資格、審査、規約遵守が必要です。

## テスト

```bash
pytest
```
