locals {
  repository_name_sanitized = replace(replace(var.github_repository, "/", "-"), "_", "-")

  common_labels = {
    system     = var.app_name
    managed_by = "terraform"
    module     = "bootstrap"
    repository = local.repository_name_sanitized
  }

  github_actions_sa_account_id = "${var.app_name}-github-actions"
  app_runtime_account_id       = "${var.app_name}-runtime"
  scheduler_invoker_account_id = "${var.app_name}-scheduler-invoker"

  # downstream infraで使うAPIをbootstrap側でまとめて有効化する。
  # infraのapply時にAPI未有効で落ちることを避けるための共通リスト。
  project_services = toset([
    "artifactregistry.googleapis.com",
    "bigquery.googleapis.com",
    "cloudbuild.googleapis.com",
    "cloudresourcemanager.googleapis.com",
    "cloudscheduler.googleapis.com",
    "cloudtasks.googleapis.com",
    "datastore.googleapis.com",
    "firestore.googleapis.com",
    "iam.googleapis.com",
    "iamcredentials.googleapis.com",
    "logging.googleapis.com",
    "run.googleapis.com",
    "secretmanager.googleapis.com",
    "serviceusage.googleapis.com",
    "sts.googleapis.com",
    "storage.googleapis.com",
  ])

  # GitHub Actions deployerはterraform/infraを作成・更新するためのSA。
  # MVPでは基盤作成を優先し、後続でresource単位に絞り込む前提。
  github_actions_project_roles = toset([
    "roles/artifactregistry.admin",
    "roles/bigquery.admin",
    "roles/cloudbuild.builds.editor",
    "roles/cloudscheduler.admin",
    "roles/cloudtasks.admin",
    "roles/datastore.owner",
    "roles/iam.serviceAccountAdmin",
    "roles/iam.serviceAccountUser",
    "roles/iam.workloadIdentityPoolAdmin",
    "roles/logging.configWriter",
    "roles/resourcemanager.projectIamAdmin",
    "roles/run.admin",
    "roles/secretmanager.admin",
    "roles/serviceusage.serviceUsageAdmin",
    "roles/storage.admin",
  ])

  # runtime SAはアプリ実行時に必要な権限だけに寄せる。
  app_runtime_project_roles = toset([
    "roles/datastore.user",
    "roles/logging.logWriter",
    "roles/secretmanager.secretAccessor",
  ])
}

# bootstrapはアプリ本体ではなく、Terraform実行基盤とGitHub Actions認証基盤を作る。
resource "google_project_service" "services" {
  for_each = local.project_services

  project            = var.project_id
  service            = each.value
  disable_on_destroy = false
}

# Terraform backend用GCS bucket。
# 既存bootstrapで作成済みの "${project_id}-tfstate" を維持し、state移行の破壊的変更を避ける。
resource "google_storage_bucket" "terraform_state" {
  name          = "${var.project_id}-tfstate"
  location      = var.tfstate_location
  force_destroy = false

  uniform_bucket_level_access = true

  versioning {
    enabled = true
  }

  lifecycle_rule {
    condition {
      num_newer_versions = 5
    }
    action {
      type = "Delete"
    }
  }

  labels = local.common_labels

  depends_on = [google_project_service.services]
}

# GitHub Actionsがterraform/infraをapplyするためのdeployer SA。
# WIFでなりすますため、長期サービスアカウントキーを発行しない。
resource "google_service_account" "github_actions" {
  account_id   = local.github_actions_sa_account_id
  display_name = "GitHub Actions deployer for ${var.app_name}"

  depends_on = [google_project_service.services]
}

# Cloud Run Job用のruntime SA。現infraでは独自SAも作るが、将来の共通化に備えてbootstrapで出力する。
resource "google_service_account" "app_runtime" {
  account_id   = local.app_runtime_account_id
  display_name = "Runtime service account for ${var.app_name}"

  depends_on = [google_project_service.services]
}

# Cloud SchedulerからCloud Run Jobを起動するためのSA。
resource "google_service_account" "scheduler_invoker" {
  account_id   = local.scheduler_invoker_account_id
  display_name = "Cloud Scheduler invoker for ${var.app_name}"

  depends_on = [google_project_service.services]
}

resource "google_project_iam_member" "github_actions_roles" {
  for_each = local.github_actions_project_roles

  project = var.project_id
  role    = each.value
  member  = "serviceAccount:${google_service_account.github_actions.email}"
}

resource "google_project_iam_member" "app_runtime_roles" {
  for_each = local.app_runtime_project_roles

  project = var.project_id
  role    = each.value
  member  = "serviceAccount:${google_service_account.app_runtime.email}"
}

resource "google_project_iam_member" "scheduler_invoker_token_creator" {
  project = var.project_id
  role    = "roles/iam.serviceAccountTokenCreator"
  member  = "serviceAccount:${google_service_account.scheduler_invoker.email}"
}

# GitHub Actions OIDC用のWorkload Identity Pool / Provider。
resource "google_iam_workload_identity_pool" "github_actions_pool" {
  workload_identity_pool_id = var.wif_pool_id
  display_name              = "GitHub Actions Pool"
  description               = "OIDC pool for GitHub Actions"

  depends_on = [google_project_service.services]
}

resource "google_iam_workload_identity_pool_provider" "github_actions_provider" {
  workload_identity_pool_id          = google_iam_workload_identity_pool.github_actions_pool.workload_identity_pool_id
  workload_identity_pool_provider_id = var.wif_provider_id
  display_name                       = "GitHub Actions Provider"
  description                        = "OIDC provider for GitHub Actions"

  attribute_mapping = {
    "google.subject"       = "assertion.sub"
    "attribute.actor"      = "assertion.actor"
    "attribute.aud"        = "assertion.aud"
    "attribute.owner"      = "assertion.repository_owner"
    "attribute.ref"        = "assertion.ref"
    "attribute.repository" = "assertion.repository"
  }

  # フォークや別repoからのOIDC tokenを拒否するため、連携先GitHubリポジトリを固定する。
  attribute_condition = "assertion.repository == '${var.github_repository}' && assertion.repository_owner == '${var.github_repository_owner}'"

  oidc {
    issuer_uri = "https://token.actions.githubusercontent.com"
  }
}

# 指定リポジトリのGitHub Actionsだけがdeployer SAをimpersonateできる。
resource "google_service_account_iam_member" "github_actions_wif_user" {
  service_account_id = google_service_account.github_actions.name
  role               = "roles/iam.workloadIdentityUser"
  member             = "principalSet://iam.googleapis.com/${google_iam_workload_identity_pool.github_actions_pool.name}/attribute.repository/${var.github_repository}"
}
