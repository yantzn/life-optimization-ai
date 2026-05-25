locals {
  secrets = [
    "GEMINI_API_KEY",
    "THREADS_ACCESS_TOKEN",
    "THREADS_USER_ID"
  ]
}

resource "google_secret_manager_secret" "app_secrets" {
  for_each  = toset(local.secrets)
  project   = var.project_id
  secret_id = "${var.app_name}-${each.key}"

  replication {
    auto {}
  }

  depends_on = [google_project_service.services]
}
