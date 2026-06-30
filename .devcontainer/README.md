# Dev Container

`loto-predict` の `.devcontainer` 構成を踏襲し、ローカルPCへTerraformやgcloudを直接入れずに、Docker内でGCP bootstrap / infra作業を行うための開発環境です。

## 含まれるもの

- Python 3.11
- Terraform
- Google Cloud CLI
- Python dependencies from `requirements.txt`
- VS Code extensions:
  - Python
  - HashiCorp Terraform
  - Google Cloud Code

## 永続化する設定

- `gcloud-config`: `/home/vscode/.config/gcloud`
- `terraform-cache`: `/home/vscode/.terraform.d/plugin-cache`

gcloud認証情報やTerraform provider cacheはDocker volumeに保存し、リポジトリには含めません。

## 初回手順

Dev Containerを起動後、コンテナ内で実行します。

```bash
gcloud auth login
gcloud auth application-default login
gcloud config set project affiliate-automation-platform-dev
```

bootstrap:

```bash
cd terraform/bootstrap
terraform init
terraform plan -var="project_id=affiliate-automation-platform-dev"
terraform apply -var="project_id=affiliate-automation-platform-dev"
```

infra:

```bash
cd ../infra
cp terraform.tfvars.sample terraform.tfvars
terraform init
terraform plan
```
