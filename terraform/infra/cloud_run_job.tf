resource "google_cloud_run_v2_job" "app_job" {
  project  = var.project_id
  name     = "${var.app_name}-job"
  location = var.region

  template {
    template {
      service_account = local.app_runtime_service_account_email

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
          # 初期デプロイは必ずtrue。本番投稿はSecret登録と手動dry-run確認後にfalseへ切り替える。
          value = tostring(var.dry_run)
        }
        env {
          name  = "GEMINI_MODEL"
          value = var.gemini_model
        }
        env {
          name  = "DEFAULT_HOURLY_VALUE"
          value = tostring(var.default_hourly_value)
        }
        env {
          name  = "TARGET_PLATFORM"
          value = var.target_platform
        }
        env {
          name  = "LOG_LEVEL"
          value = var.log_level
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

        # Cloud Run JobではMVPパイプラインを一括実行する。
        # schedule-posts/publish-due-posts導入後は、生成と投稿実行を別Jobに分ける想定。
        command = ["python", "-m", "src.cli"]
        args    = ["run-mvp", "--limit", tostring(var.mvp_limit)]
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
