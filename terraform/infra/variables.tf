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
