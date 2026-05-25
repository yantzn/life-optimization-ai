resource "google_cloud_scheduler_job" "run_app_job" {
  project     = var.project_id
  region      = var.region
  name        = "${var.app_name}-scheduler"
  description = "Trigger ${var.app_name} Cloud Run Job periodically"
  schedule    = var.schedule_cron
  time_zone   = "Asia/Tokyo"

  http_target {
    http_method = "POST"
    # Cloud Run Job execution API endpoint
    uri         = "https://${var.region}-run.googleapis.com/apis/run.googleapis.com/v1/namespaces/${var.project_id}/jobs/${google_cloud_run_v2_job.app_job.name}:run"
    
    oauth_token {
      service_account_email = google_service_account.scheduler_sa.email
    }
  }

  depends_on = [
    google_project_service.services,
    google_project_iam_member.scheduler_run_invoker
  ]
}
