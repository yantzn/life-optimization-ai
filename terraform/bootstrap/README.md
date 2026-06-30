# bootstrap Terraform Runbook

`bootstrap` は `terraform/infra` を安全に運用するための土台を作るモジュールです。アプリ本体のCloud Run JobやFirestore collection設計ではなく、Terraform state、API有効化、GitHub Actionsの鍵レス認証、基礎Service Accountを作成します。

## 作成されるリソース

共通基盤:

- Terraform backend 用 GCS bucket
- downstream infra で必要な Google Cloud API の有効化
- GitHub Actions deployer Service Account
- Cloud Run Job runtime 用 Service Account
- Cloud Scheduler invoker 用 Service Account

認証基盤:

- Workload Identity Pool
- Workload Identity Provider
- `roles/iam.workloadIdentityUser` binding

## 有効化する主なAPI

- IAM / IAM Credentials / STS
- Cloud Resource Manager / Service Usage
- Cloud Storage
- Firestore / Datastore
- Cloud Run
- Artifact Registry / Cloud Build
- Secret Manager
- Cloud Scheduler / Cloud Tasks
- Cloud Logging
- BigQuery

## 実行手順

```bash
cd terraform/bootstrap
cp terraform.tfvars.example terraform.tfvars
terraform init
terraform validate
terraform plan -lock-timeout=5m -var-file=terraform.tfvars -out=tfplan
terraform apply -lock-timeout=5m tfplan
```

既に `affiliate-automation-platform-tfstate` を作成済みのため、`tfstate_location` は既存bucketと同じ `asia-northeast1` を使います。GCS bucketのlocationは後から変更できないため、ここを変えると再作成差分になります。

## GitHub Actions設定

apply後のoutputをGitHub Actionsに設定します。

Variables:

- `TFSTATE_BUCKET`: `tfstate_bucket_name`

Secrets:

- `WIF_PROVIDER`: `workload_identity_provider_name`
- `WIF_SERVICE_ACCOUNT`: `github_actions_service_account_email`

`github_repository` は `owner/repo` 形式で固定します。これにより、フォークや別リポジトリから発行されたOIDC tokenではdeployer Service Accountを利用できません。
