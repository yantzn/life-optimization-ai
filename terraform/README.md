# Terraform Deployment

Threads Affiliate MVPをGCPへデプロイするためのTerraformです。まず `dry_run = true` のままCloud Run Jobを動かし、FirestoreとCloud Loggingで結果を確認してから本番投稿を解禁します。

## 構成

- `bootstrap/`: Terraform state用GCS bucketとGitHub Actions向けWorkload Identity Federation
- `infra/`: Cloud Run Job、Cloud Scheduler、Firestore、Secret Manager、Artifact Registry、IAM

`bootstrap` はアプリ本体ではありません。Terraformを安全に実行するための基盤を先に作る層です。

bootstrapの役割:

- tfstate用GCS bucket
- downstream infraに必要なAPI有効化
- GitHub Actions Workload Identity Federation
- GitHub Actions deployer Service Account
- Cloud Run Job runtime Service Account
- Cloud Scheduler invoker Service Account

bootstrapで有効化する主なAPI:

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

`infra` はdev環境相当のアプリ実行基盤です。

- Firestore: パイプライン状態管理DB
- Secret Manager: Gemini / Threadsのsecret保管場所
- Cloud Run service account: Job実行権限
- Cloud Scheduler: JST基準の定期実行入口
- Cloud Tasks: 後続拡張で投稿キュー平準化に利用予定

## 初回準備

```bash
gcloud auth application-default login
gcloud config set project <PROJECT_ID>
```

`terraform/bootstrap` を先に適用します。

```bash
cd terraform/bootstrap
cp terraform.tfvars.example terraform.tfvars
terraform init
terraform validate
terraform plan -lock-timeout=5m -var-file=terraform.tfvars -out=tfplan
terraform apply -lock-timeout=5m tfplan
```

apply後、以下のoutputをGitHub Actionsに設定します。

- `tfstate_bucket_name` -> Variable `TFSTATE_BUCKET`
- `workload_identity_provider_name` -> Secret `WIF_PROVIDER`
- `github_actions_service_account_email` -> Secret `WIF_SERVICE_ACCOUNT`

## Infra適用

```bash
cd terraform/infra
cp terraform.tfvars.sample terraform.tfvars
```

`terraform.tfvars` の最小設定:

```hcl
project_id = "your-gcp-project-id"
region     = "asia-northeast1"
app_name   = "sns-af"
dry_run    = true
mvp_limit  = 5
```

`project_id` は `affiliate-automation-platform` 系のGCPプロジェクトを想定しています。`region` はレイテンシと運用場所を考慮して `asia-northeast1` をデフォルトにします。

`backend.tf` は最初からGCS backendにできません。bootstrap後、出力された実bucket名を `backend.tf.example` 相当の設定に差し替えて `terraform init` で移行します。

適用:

```bash
terraform init
terraform plan
terraform apply
```

## GitHub ActionsでのInfra更新

`.github/workflows/terraform-infra.yml` は `terraform/infra/**` の変更時に実行されます。
Pull Requestでは `fmt / init / validate / plan` まで、`main` へのpushでは `apply` まで行います。

GitHub Actions Variables:

```text
GCP_PROJECT_ID=<GCP project id>
GCP_REGION=<GCP region>
TFSTATE_BUCKET=<bootstrap output: tfstate_bucket_name>
APP_RUNTIME_SERVICE_ACCOUNT=<bootstrap output: app_runtime_service_account_email>
SCHEDULER_INVOKER_SERVICE_ACCOUNT=<bootstrap output: scheduler_invoker_service_account_email>
```

GitHub Actions Secrets:

```text
WIF_PROVIDER=<bootstrap output: workload_identity_provider_name>
WIF_SERVICE_ACCOUNT=<bootstrap output: github_actions_service_account_email>
```

`WIF_PROVIDER` は bootstrap の output `workload_identity_provider_name` を使います。
`WIF_SERVICE_ACCOUNT` は GitHub Actions から Terraform を実行するためのdeploy用サービスアカウントです。
`APP_RUNTIME_SERVICE_ACCOUNT` はCloud Run Jobの実行主体、`SCHEDULER_INVOKER_SERVICE_ACCOUNT` はCloud SchedulerからJobを起動する主体として `terraform/infra` に渡します。どちらも認証キーではなくサービスアカウントの参照先ですが、環境ごとに固定する基盤値なのでGitHub Actions Variablesで管理します。

Terraformのstateは bootstrap で作成したGCS bucketを使います。`terraform/infra/backend.tf` にはbucket名を固定せず、workflowの `terraform init -backend-config="bucket=${TFSTATE_BUCKET}"` で注入します。

### bootstrap outputs を GitHub Actions に設定する

GitHubリポジトリの `Settings > Secrets and variables > Actions` で設定します。

`Variables` タブに追加:

```text
TFSTATE_BUCKET=<bootstrap output: tfstate_bucket_name>
GCP_PROJECT_ID=<GCP project id>
GCP_REGION=<GCP region, e.g. asia-northeast1>
APP_RUNTIME_SERVICE_ACCOUNT=<bootstrap output: app_runtime_service_account_email>
SCHEDULER_INVOKER_SERVICE_ACCOUNT=<bootstrap output: scheduler_invoker_service_account_email>
```

以下のようなアプリ動作設定はGitHub Actions Variablesではなく、`terraform/infra/terraform.tfvars` で管理します。値を変える可能性があるため、環境ごとのtfvars差分としてレビューできる形にします。

```hcl
app_name             = "sns-af"
schedule_cron        = "0 21 * * *"
dry_run              = true
gemini_model         = "gemini-2.0-flash"
default_hourly_value = 2000
target_platform      = "threads"
log_level            = "INFO"
mvp_limit            = 5
```

`Secrets` タブに追加:

```text
WIF_PROVIDER=<bootstrap output: workload_identity_provider_name>
WIF_SERVICE_ACCOUNT=<bootstrap output: github_actions_service_account_email>
```

bootstrap outputとの対応:

```text
tfstate_bucket または tfstate_bucket_name
  -> GitHub Actions Variable: TFSTATE_BUCKET

workload_identity_provider_name
  -> GitHub Actions Secret: WIF_PROVIDER

github_actions_service_account_email
  -> GitHub Actions Secret: WIF_SERVICE_ACCOUNT

app_runtime_service_account_email
  -> GitHub Actions Variable: APP_RUNTIME_SERVICE_ACCOUNT

scheduler_invoker_service_account_email
  -> GitHub Actions Variable: SCHEDULER_INVOKER_SERVICE_ACCOUNT
```

## Secret Manager

TerraformはSecretの入れ物だけを作成します。値はapply後に登録します。

```bash
echo -n "your-gemini-api-key" | gcloud secrets versions add sns-af-GEMINI_API_KEY --data-file=-
echo -n "your-threads-access-token" | gcloud secrets versions add sns-af-THREADS_ACCESS_TOKEN --data-file=-
echo -n "your-threads-user-id" | gcloud secrets versions add sns-af-THREADS_USER_ID --data-file=-
```

dry-runだけを確認する段階ではThreadsのSecretは空でも構いません。本番投稿前には必須です。

## コンテナイメージ

```bash
docker build -t asia-northeast1-docker.pkg.dev/<PROJECT_ID>/sns-af/app:latest -f Dockerfile .
docker push asia-northeast1-docker.pkg.dev/<PROJECT_ID>/sns-af/app:latest
gcloud run jobs update sns-af-job \
  --image asia-northeast1-docker.pkg.dev/<PROJECT_ID>/sns-af/app:latest \
  --region asia-northeast1
```

## GCP dry-run確認

```bash
gcloud run jobs execute sns-af-job --region asia-northeast1 --wait
```

確認ポイント:

- Cloud Loggingに `command_completed command=run-mvp` が出る
- Firestoreに `product_candidates`, `product_scores`, `products`, `enriched_products`, `post_candidates`, `post_logs` が作成される
- `post_logs.result` が `dry_run_success`

## 本番投稿の解禁

1. ローカルで `DRY_RUN=true` の投稿文を確認
2. GCPでも `dry_run = true` のCloud Run Jobを確認
3. Threads tokenとuser idをSecret Managerへ登録
4. `terraform.tfvars` の `dry_run = false` に変更
5. `terraform apply`
6. `gcloud run jobs execute sns-af-job --region asia-northeast1 --wait` を手動で1回だけ実行
7. Threads側と `post_logs.result = success` を確認

Schedulerは本番投稿の手動確認後に有効化してください。
