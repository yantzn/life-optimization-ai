variable "project_id" {
  description = "GCP Project ID"
  type        = string
}

variable "region" {
  description = "GCP Region"
  type        = string
  default     = "asia-northeast1"
}

variable "app_name" {
  description = "Application name (used for resources prefix)"
  type        = string
  default     = "sns-af"
}

variable "schedule_cron" {
  description = "Cron expression for Cloud Scheduler to run the Cloud Run Job"
  type        = string
  default     = "0 21 * * *" # Example: Run every day at 21:00
}

variable "dry_run" {
  description = "Keep Threads publishing disabled when true. Set false only after dry-run verification."
  type        = bool
  default     = true
}

variable "gemini_model" {
  description = "Gemini model used for scoring and generation"
  type        = string
  default     = "gemini-2.0-flash"
}

variable "default_hourly_value" {
  description = "Default hourly value in JPY for ROI calculation"
  type        = number
  default     = 2000
}

variable "target_platform" {
  description = "Publishing target platform"
  type        = string
  default     = "threads"
}

variable "log_level" {
  description = "Application log level"
  type        = string
  default     = "INFO"
}

variable "mvp_limit" {
  description = "Maximum number of documents processed per MVP job phase"
  type        = number
  default     = 5
}

variable "app_runtime_service_account_email" {
  description = "Optional bootstrap-created runtime service account email for Cloud Run Job. When null, infra creates a local fallback service account."
  type        = string
  default     = null
}

variable "scheduler_invoker_service_account_email" {
  description = "Optional bootstrap-created scheduler invoker service account email. When null, infra creates a local fallback service account."
  type        = string
  default     = null
}
