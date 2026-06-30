# Partial backend — values supplied at `terraform init` time.
#   CI:    via -backend-config flags from TF_BACKEND_* secrets (see .github/workflows/ci.yml)
#   Local: `terraform init -backend-config=backend.hcl` (copy backend.hcl.example)
terraform {
  backend "azurerm" {}
}
