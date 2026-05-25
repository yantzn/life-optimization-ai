# Threads Affiliate Auto-Operation System

## システム概要
Gemini API・Firestore・Threads APIを利用したアフィリエイト自動運用システムのMVPです。
「商品を売る」のではなく、「時間価値」を売るというコンセプトに基づき、人間味のある投稿を自動生成・投稿します。

## ローカルでの実行方法 (セットアップ手順)

ローカル環境で安全にテストおよび動作確認を行うための手順です。

### 1. Python 仮想環境の構築 (推奨)
Python 3.11以上が必要です。プロジェクトルートで仮想環境を作成し、有効化します。

**Windows (PowerShell) の場合:**
```powershell
python -m venv venv
.\venv\Scripts\Activate.ps1
```

**macOS/Linux の場合:**
```bash
python3 -m venv venv
source venv/bin/activate
```

### 2. 依存パッケージのインストール
```bash
pip install -r requirements.txt
```

### 3. 環境変数の設定
`.env.example` をコピーして `.env` ファイルを作成します。
MVPでは `DRY_RUN=true` を標準としており、APIキー等の実データがなくてもローカルで安全にテスト可能です。

```bash
cp .env.example .env
```

## .env 設定
```env
GCP_PROJECT_ID=your-gcp-project-id
GEMINI_API_KEY=your-gemini-api-key
GEMINI_MODEL=gemini-2.0-flash
THREADS_ACCESS_TOKEN=your-threads-access-token
THREADS_USER_ID=your-threads-user-id
DRY_RUN=true
DEFAULT_HOURLY_VALUE=2000
```

### 4. テストの実行
環境変数の設定が完了したら、モックを用いたテストを実行してロジックの動作確認を行います。

```bash
pytest
```

## CLI実行方法

テストが成功したら、CLIからパイプラインをローカルで実行できます。

```bash
python -m src.main --mode collect   # 商品候補収集
python -m src.main --mode score     # 一次スコアリング
python -m src.main --mode analyze   # 詳細分析
python -m src.main --mode generate  # 投稿生成
python -m src.main --mode publish   # Threads投稿 (DRY_RUN時はAPI呼び出しをスキップ)
python -m src.main --mode all       # 全て実行
```

## DRY_RUN運用方法
`.env` の `DRY_RUN=true` に設定することで、実際のAPIを呼び出さず、内部のモックやローカル状態でのテストが可能です。

## 本番投稿前チェックリスト
- DRY_RUNで一連の動作（all）がエラーなく完了すること
- `post_candidates` に期待通りの投稿文が生成されていること
- 薬機法、誇大表現に抵触していないこと
- 文字数やPR表記ルールが遵守されていること

## Firestoreコレクション説明
- `product_candidates`: 収集した商品候補
- `product_scores`: スコアリング結果
- `products`: 採用された商品
- `enriched_products`: 分析・拡張された商品情報
- `post_candidates`: 生成された投稿候補
- `post_logs`: 投稿の実行ログ

## コンプライアンス上の注意点
- 必ず【PR】を冒頭につけること
- 誇大表現、薬機法違反（「完治」「絶対痩せる」など）を含まないこと
- リンクは原則1件まで