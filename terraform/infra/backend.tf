terraform {
  required_version = ">= 1.5.0"
  required_providers {
    google = {
      source  = "hashicorp/google"
      version = "~> 5.0"
    }
    google-beta = {
      source  = "hashicorp/google-beta"
      version = "~> 5.0"
    }
  }

  # GitHub Actionsでは -backend-config="bucket=..." でbootstrap済みのtfstate bucketを注入する。
  # bucket名をコードへ固定しないことで、dev/prodなど複数projectへ展開しやすくする。
  backend "gcs" {
    prefix = "sns-af/infra"
  }
}

provider "google" {
  project = var.project_id
  region  = var.region
}

provider "google-beta" {
  project = var.project_id
  region  = var.region
}
