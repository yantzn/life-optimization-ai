# GEMINI.md

## プロジェクト概要

本プロジェクトは、Gemini API・Firestore・Threads API を利用した
「Threads向けアフィリエイト自動運用システム」です。

目的は単なる大量投稿Botではなく、

- 人間味
- 共感
- 時短ROI
- 合理性
- 長期的な信頼

を重視した、持続可能なSNS運用基盤を構築することです。

---

# システムコンセプト

このシステムは「商品を売る」のではなく、

```text
時間を取り戻す
ストレスを減らす
家事を自動化する
思考コストを削減する
```

という価値を販売する。

特に以下のようなターゲットを想定する。

- 30代前後
- 共働き家庭
- 子育て中
- ITリテラシーが高い
- ROI重視
- 感情論より合理性
- 「時間が足りない」が最大の悩み

---

# 技術スタック

| 項目     | 技術                        |
| -------- | --------------------------- |
| 言語     | Python 3.11+                |
| AI       | Gemini API                  |
| DB       | Firestore                   |
| 配信     | Threads API                 |
| インフラ | Cloud Run / Cloud Functions |
| テスト   | pytest                      |
| 設定管理 | dotenv                      |

---

# アーキテクチャ

```text
product_candidates
    ↓
Gemini一次スコアリング
    ↓
product_scores
    ↓
products
    ↓
詳細分析 + ROI算出
    ↓
enriched_products
    ↓
投稿生成
    ↓
品質チェック
    ↓
人間味リライト
    ↓
post_candidates
    ↓
Threads投稿
    ↓
post_logs
```

---

# 開発思想

## 1. AI臭を徹底的に排除する

このプロジェクトで最も重要なのは、

```text
「AIっぽさ」
「広告代理店っぽさ」
「アフィリエイターっぽさ」
```

を徹底的に消すこと。

以下は禁止。

```text
おすすめです！
大人気！
これ一つで解決！
絶対買うべき！
```

目指す文体は：

```text
もっと早く買えばよかった…
```

```text
数千円ケチってた頃の自分を殴りたい
```

のような、

- 疲れている
- 等身大
- 独白
- 本音
- 感情の揺れ

を持つ人間らしい文章。

---

## 2. 商品ではなく「時間価値」を売る

このシステムはスペック紹介Botではない。

重要なのは：

- 何分削減できるか
- どんなストレスが消えるか
- どんな絶望から解放されるか
- 家庭内の摩擦をどう減らすか

である。

機能説明は全体の20%以下に抑える。

感情・情景・生活改善を80%で描写する。

---

## 3. Firestore中心の状態遷移設計

全ての処理は Firestore の status に基づいて進行する。

必須フィールド：

```python
created_at
updated_at
status
```

各サービスは冪等性を持つこと。

例：

```text
fetched
scored
accepted
enriched
generated
queued
posted
rejected
```

---

# ディレクトリ構成

```text
src/
  clients/
  services/
  prompts/
  main.py
  config.py

tests/
```

---

# コーディングルール

## 型ヒント必須

すべての公開関数には型ヒントを付与する。

悪い例：

```python
def calc(a, b):
```

良い例：

```python
def calc(a: int, b: int) -> int:
```

---

## ログ必須

printは禁止。

必ず logging を使用する。

```python
logger.info(...)
logger.warning(...)
logger.error(...)
```

---

## 例外処理必須

外部API呼び出しは必ず：

- try/except
- ログ出力
- 必要ならFirestore保存

を行う。

特に：

- Gemini JSONパース
- Firestore
- Threads API

は必須。

---

# Gemini利用ルール

## Structured Outputを強制

Geminiには必ずJSONのみを返させる。

```python
response_mime_type="application/json"
```

を利用する。

---

## JSONパース失敗対策

GeminiはJSON破損を起こす前提で設計する。

必要：

- リトライ
- raw responseログ
- 明示的例外

サイレント失敗は禁止。

---

## Temperature

基本は：

```python
temperature=0.2
```

創造性が必要な場合のみ上げる。

---

# 投稿ルール

## Threads文字数

推奨：

```text
120〜220文字
```

最大：

```text
500文字
```

500超は rejected。

---

## PR表記

アフィリエイト関連投稿は必ず：

```text
【PR】
```

を冒頭に付与する。

末尾 `#PR` のみは禁止。

---

## リンク

1投稿につき原則1リンク。

直接アフィリエイトリンクより：

```text
プロフィール
まとめLP
```

への導線を優先。

---

# 薬機法・ステマ対策

以下表現は禁止。

```text
シミが消える
免疫力アップ
脂肪分解
完治
絶対痩せる
誰でも必ず
```

検出時は：

- 安全表現へ置換
- 置換不可なら rejected

---

# Threads運用思想

このシステムは：

```text
大量投稿Bot
```

を目指さない。

目標：

```text
少数でも信頼される投稿
```

---

# 投稿トーン

目指す人格：

```text
疲れているけど合理的な共働きパパ
```

避ける人格：

```text
インフルエンサー
営業マン
広告代理店
情報商材屋
```

---

# DRY_RUN思想

デフォルト：

```env
DRY_RUN=true
```

DRY_RUN時：

- Threads APIを呼ばない
- モックレスポンスを返す
- post_logsへ保存
- パイプライン全体を検証可能にする

---

# テスト方針

pytest必須。

最低限テストする内容：

- ROI計算
- PR表記
- 薬機法フィルタ
- Threads文字数制限
- DRY_RUN投稿
- Gemini JSON validation
- Pipeline実行

---

# Prompt設計思想

Promptは：

- 曖昧禁止
- JSON固定
- 禁止事項明示
- 制約明示
- AI臭排除

を徹底する。

---

# ROI思想

ROI計算は重要。

例：

```python
monthly_time_saving_hours = minutes_per_week * 4 / 60
monthly_value = monthly_time_saving_hours * hourly_value
payback_period = price / monthly_value
```

重要なのは：

```text
「いくら得するか」
ではなく
「どれだけ人生が楽になるか」
```

である。

---

# 将来的な拡張

今後追加予定：

- Amazon PA-API
- 楽天API
- GAS同期
- BigQuery分析
- A/Bテスト
- LP自動生成
- Instagram/TikTok対応
- 自動スケジューリング

---

# 最重要思想

このプロジェクトは：

```text
「AIが大量生成した広告」
```

を作るものではない。

目指すのは：

```text
「生活に疲れた誰かが、
深夜に本音でつぶやいたような、
人間味のある投稿」
```

である。
