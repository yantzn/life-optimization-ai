variable "project_id" {
  description = "GCP project id"
  type        = string
}

variable "region" {
  description = "Default GCP region"
  type        = string
  default     = "asia-northeast1"
}

variable "tfstate_location" {
  description = "Location for Terraform state bucket"
  type        = string
  default     = "asia-northeast1"
}

variable "app_name" {
  description = "Application name used as resource prefix"
  type        = string
  default     = "sns-af"
}

variable "github_repository" {
  description = "GitHub repository allowed to use Workload Identity Federation, in owner/name format"
  type        = string
  default     = "yantzn/life-optimization-ai"
}

variable "github_repository_owner" {
  description = "GitHub repository owner"
  type        = string
  default     = "yantzn"
}

variable "wif_pool_id" {
  description = "Workload Identity Pool id"
  type        = string
  default     = "github-actions-pool"
}

variable "wif_provider_id" {
  description = "Workload Identity Provider id"
  type        = string
  default     = "github-actions-provider"
}
