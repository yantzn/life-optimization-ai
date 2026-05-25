terraform {
  required_version = ">= 1.5.0"
  required_providers {
    google = {
      source  = "hashicorp/google"
      version = "~> 5.0"
    }
  }
}

provider "google" {
  project = var.project_id
  region  = var.region
}

# --------------------------------------------------------------------------------
# Terraform State Bucket
# --------------------------------------------------------------------------------
resource "google_storage_bucket" "terraform_state" {
  name          = "${var.project_id}-tfstate"
  location      = var.region
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
}

# --------------------------------------------------------------------------------
# GitHub Actions Workload Identity Federation (Best Practice)
# --------------------------------------------------------------------------------
# Enables GitHub Actions to authenticate to GCP without long-lived Service Account keys
resource "google_iam_workload_identity_pool" "github_actions_pool" {
  workload_identity_pool_id = "github-actions-pool"
  display_name              = "GitHub Actions Pool"
  description               = "Identity pool for GitHub Actions deployments"
}

resource "google_iam_workload_identity_pool_provider" "github_actions_provider" {
  workload_identity_pool_id          = google_iam_workload_identity_pool.github_actions_pool.workload_identity_pool_id
  workload_identity_pool_provider_id = "github-actions-provider"
  display_name                       = "GitHub Actions Provider"
  
  attribute_mapping = {
    "google.subject"       = "assertion.sub"
    "attribute.actor"      = "assertion.actor"
    "attribute.repository" = "assertion.repository"
  }
  
  # Change `YOUR_GITHUB_ORG/YOUR_REPO` to the actual GitHub repository
  # Example: "attribute.repository == \"yantzn/sns-af\""
  # Here we allow any repo in the attribute condition, or you can restrict it.
  # attribute_condition = "assertion.repository == \"YOUR_GITHUB_ORG/${var.app_name}\""

  oidc {
    issuer_uri = "https://token.actions.githubusercontent.com"
  }
}

output "tfstate_bucket" {
  value = google_storage_bucket.terraform_state.name
}

output "workload_identity_provider_name" {
  value = google_iam_workload_identity_pool_provider.github_actions_provider.name
}
