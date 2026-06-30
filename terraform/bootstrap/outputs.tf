output "tfstate_bucket_name" {
  description = "Terraform backend bucket name for downstream infra"
  value       = google_storage_bucket.terraform_state.name
}

output "tfstate_bucket" {
  description = "Backward-compatible alias for the Terraform backend bucket name"
  value       = google_storage_bucket.terraform_state.name
}

output "workload_identity_provider_name" {
  description = "Full Workload Identity Provider resource name"
  value       = google_iam_workload_identity_pool_provider.github_actions_provider.name
}

output "github_actions_service_account_email" {
  description = "GitHub Actions deployer service account email"
  value       = google_service_account.github_actions.email
}

output "app_runtime_service_account_email" {
  description = "Runtime service account email for Cloud Run Job"
  value       = google_service_account.app_runtime.email
}

output "scheduler_invoker_service_account_email" {
  description = "Cloud Scheduler invoker service account email"
  value       = google_service_account.scheduler_invoker.email
}
