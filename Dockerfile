# ベースイメージとして軽量なPython 3.11を使用
FROM python:3.11-slim

# 作業ディレクトリの設定
WORKDIR /app

# 依存関係ファイルのコピーとインストール
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# アプリケーションコードとプロンプトのコピー
COPY src/ ./src/

# PYTHONPATHを設定
ENV PYTHONPATH=/app

# コンテナ起動時のデフォルトコマンド
# (TerraformのCloud Run Job定義で上書き可能)
CMD ["python", "-m", "src.main", "--mode", "all"]