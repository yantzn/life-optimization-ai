resource "google_cloud_run_v2_job" "app_job" {
  project  = var.project_id
  name     = "${var.app_name}-job"
  location = var.region

  template {
    template {
      service_account = google_service_account.app_sa.email

      containers {
        # Using a placeholder image for initial terraform apply.
        # Actual deployments will be done via CI/CD (GitHub Actions).
        image = "us-docker.pkg.dev/cloudrun/container/hello"
        
        env {
          name  = "GCP_PROJECT_ID"
          value = var.project_id
        }
        env {
          name  = "DRY_RUN"
          value = "true" # Default to true for MVP
        }
        env {
          name  = "GEMINI_MODEL"
          value = "gemini-2.0-flash"
        }
        env {
          name  = "DEFAULT_HOURLY_VALUE"
          value = "2000"
        }
        
        # Inject secrets from Secret Manager
        env {
          name = "GEMINI_API_KEY"
          value_source {
            secret_key_ref {
              secret  = google_secret_manager_secret.app_secrets["GEMINI_API_KEY"].secret_id
              version = "latest"
            }
          }
        }
        env {
          name = "THREADS_ACCESS_TOKEN"
          value_source {
            secret_key_ref {
              secret  = google_secret_manager_secret.app_secrets["THREADS_ACCESS_TOKEN"].secret_id
              version = "latest"
            }
          }
        }
        env {
          name = "THREADS_USER_ID"
          value_source {
            secret_key_ref {
              secret  = google_secret_manager_secret.app_secrets["THREADS_USER_ID"].secret_id
              version = "latest"
            }
          }
        }

        # The command to execute when the job runs
        command = ["python", "-m", "src.main"]
        args    = ["--mode", "all"]
      }
    }
  }

  lifecycle {
    # Ignore changes to the image as it will be updated by CI/CD
    ignore_changes = [
      template[0].template[0].containers[0].image
    ]
  }

  depends_on = [
    google_project_service.services,
    google_project_iam_member.firestore_user,
    google_secret_manager_secret_iam_member.secret_accessor
  ]
}
