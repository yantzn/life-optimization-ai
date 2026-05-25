# Firestore Native Database
resource "google_firestore_database" "default" {
  project     = var.project_id
  name        = "(default)"
  location_id = var.region
  type        = "FIRESTORE_NATIVE"

  # Setting to "DELETE" allows teardown for MVP. 
  # In production, this should be removed or set to "RETAIN" to avoid accidental data loss.
  deletion_policy = "DELETE" 
  
  depends_on = [google_project_service.services]
}
