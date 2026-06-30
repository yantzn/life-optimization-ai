# --------------------------------------------------------------------------------
# Service Account for Cloud Run Job
# --------------------------------------------------------------------------------
locals {
  app_runtime_service_account_email = coalesce(
    var.app_runtime_service_account_email,
    try(google_service_account.app_sa[0].email, null)
  )
  scheduler_service_account_email = coalesce(
    var.scheduler_invoker_service_account_email,
    try(google_service_account.scheduler_sa[0].email, null)
  )
}

resource "google_service_account" "app_sa" {
  count = var.app_runtime_service_account_email == null ? 1 : 0

  project      = var.project_id
  account_id   = "${var.app_name}-job-sa"
  display_name = "Service Account for ${var.app_name} Cloud Run Job"
}

# Grant Firestore access (Datastore User is sufficient for Firestore Data Plane)
resource "google_project_iam_member" "firestore_user" {
  project = var.project_id
  role    = "roles/datastore.user"
  member  = "serviceAccount:${local.app_runtime_service_account_email}"
}

# Grant Secret Manager access
resource "google_secret_manager_secret_iam_member" "secret_accessor" {
  for_each  = google_secret_manager_secret.app_secrets
  project   = var.project_id
  secret_id = each.value.secret_id
  role      = "roles/secretmanager.secretAccessor"
  member    = "serviceAccount:${local.app_runtime_service_account_email}"
}

# --------------------------------------------------------------------------------
# Service Account for Cloud Scheduler
# --------------------------------------------------------------------------------
resource "google_service_account" "scheduler_sa" {
  count = var.scheduler_invoker_service_account_email == null ? 1 : 0

  project      = var.project_id
  account_id   = "${var.app_name}-scheduler-sa"
  display_name = "Service Account for ${var.app_name} Cloud Scheduler"
}

# Grant Invoker access to Cloud Scheduler so it can trigger the Cloud Run Job
resource "google_project_iam_member" "scheduler_run_invoker" {
  project = var.project_id
  role    = "roles/run.invoker"
  member  = "serviceAccount:${local.scheduler_service_account_email}"
}
