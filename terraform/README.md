# Infrastructure for sns-af

このディレクトリには、`sns-af` プロジェクトの実行に必要な GCP 環境を構築する Terraform コードが含まれています。
参考リポジトリ (`yantzn/loto-predict`) のサーバーレスアーキテクチャをベースに、本プロジェクトに最適化した **Cloud Run Job + Cloud Scheduler** のベストプラクティス構成を採用し、さらに Terraform の状態管理や CI/CD 向けの設定を `bootstrap` と `infra` に分割しています。

## ディレクトリ構成
```
terraform/
├── bootstrap/
│   # Terraform State管理用GCSバケットとGitHub Actions用WIF (Workload Identity Federation) の構築
├── infra/
│   # Cloud Run, Cloud Scheduler, Firestore, Secret Manager 等のアプリケーション本体のインフラ構築
└── README.md
```

## アーキテクチャ構成
1. **Cloud Scheduler**: 定期的にバッチ処理をトリガーします。
2. **Cloud Run Job**: PythonのCLIバッチをコンテナとして実行します。
3. **Firestore**: アプリケーションの状態やデータ保存に使用します。
4. **Secret Manager**: Gemini API KeyやThreadsのアクセストークンなどの機密情報を安全に管理し、Cloud Run Jobに環境変数として注入します。
5. **Artifact Registry**: Cloud Run Jobで使用するコンテナイメージを保存します。
6. **IAM Service Account**: Cloud Run Job実行用とScheduler実行用のサービスアカウントを分離し、最小権限の原則（Least Privilege）を適用しています。
7. **Workload Identity Federation**: サービスアカウントキーをダウンロードすることなく、GitHub Actions等の外部CI/CDからGCPへのセキュアなデプロイを可能にします。

## デプロイ手順

### 1. GCPプロジェクトの準備
GCPプロジェクトを作成し、課金を有効化してください。
また、gcloud CLIをローカル環境で認証しておきます。

```bash
gcloud auth application-default login
```

### 2. Bootstrap (初回のみ)
Terraformの状態を管理するGCSバケットと、GitHub Actions用のWIFを設定します。

```bash
cd terraform/bootstrap
terraform init
# variables.tf に合わせた値を入力するか、terraform.tfvars を作成して実行
terraform apply
```

実行が完了すると、`tfstate_bucket` の名前が出力されます。

### 3. Infra のデプロイ
次に、実際のアプリケーション用インフラをデプロイします。

```bash
cd ../infra
cp terraform.tfvars.sample terraform.tfvars
# terraform.tfvars をご自身の環境に合わせて編集
```

※ 本番環境では、`infra/backend.tf` のコメントアウトを外し、`terraform/bootstrap` で作成されたGCSバケット名 (`YOUR-PROJECT-ID-tfstate`) を指定することで、TerraformのStateをクラウド上で共有・管理することを推奨します。

```bash
terraform init
terraform plan
terraform apply
```

### 4. シークレットの設定
Terraformの適用完了後、作成されたSecret Managerのシークレットに実際の値を設定します（GCPコンソール、またはgcloudコマンドから実行してください）。

- `sns-af-GEMINI_API_KEY`
- `sns-af-THREADS_ACCESS_TOKEN`
- `sns-af-THREADS_USER_ID`

```bash
echo -n "your-gemini-api-key" | gcloud secrets versions add sns-af-GEMINI_API_KEY --data-file=-
echo -n "your-threads-access-token" | gcloud secrets versions add sns-af-THREADS_ACCESS_TOKEN --data-file=-
echo -n "your-threads-user-id" | gcloud secrets versions add sns-af-THREADS_USER_ID --data-file=-
```

### 5. アプリケーションコンテナのデプロイ
TerraformでArtifact Registryが作成された後、アプリケーションのDockerイメージをビルドしてプッシュします（またはGitHub Actions等のCI/CDから実行）。
デプロイ後、Cloud Run Jobのイメージタグを更新して実行します。

```bash
# イメージのビルド
docker build -t asia-northeast1-docker.pkg.dev/<PROJECT_ID>/sns-af/app:latest -f ../../Dockerfile ../../

# イメージのPush
docker push asia-northeast1-docker.pkg.dev/<PROJECT_ID>/sns-af/app:latest

# Cloud Run Jobの更新
gcloud run jobs update sns-af-job \
  --image asia-northeast1-docker.pkg.dev/<PROJECT_ID>/sns-af/app:latest \
  --region asia-northeast1
```

## ベストプラクティスについて (参考リポジトリからの変更点)
- **BootstrapとInfraの分離**: `loto-predict` に倣い、Terraform State用バケットとアプリケーション本体のインフラ構築を分離しました。
- **Workload Identity Federation**: GitHub Actions等から安全にデプロイを行えるよう、WIFのプロビジョニングを `bootstrap` に追加しています。
- **非同期Pub/Sub構成からCloud Run Jobへの変更**: 既存の `main.py --mode all` というCLIベースで一括実行される設計となっているため、Cloud Functions群よりもバッチ処理に適した Cloud Run Job を採用しています。
- **機密情報の管理**: Secret Managerを使用し、Terraform上には平文でシークレットを持たせず、インフラのみをプロビジョニングする構成にしています。
