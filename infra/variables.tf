variable "subscription_id" {
  description = "Azure subscription ID"
  type        = string
}

variable "location" {
  description = "Azure region for all resources"
  type        = string
  default     = "eastus"
}

variable "environment" {
  description = "Deployment environment (prod, staging, dev)"
  type        = string
  default     = "prod"
}

variable "project" {
  description = "Project name prefix for resource naming"
  type        = string
  default     = "procureiq"
}

variable "openai_gpt4o_capacity" {
  description = "TPM capacity for gpt-4o deployment (in thousands)"
  type        = number
  default     = 30
}

variable "openai_embedding_capacity" {
  description = "TPM capacity for text-embedding-3-small deployment (in thousands)"
  type        = number
  default     = 120
}

variable "dynatrace_env_url" {
  description = "Dynatrace environment URL, e.g. https://abc12345.live.dynatrace.com (no trailing slash). Tokens are stored in Key Vault, not here."
  type        = string
  default     = ""
}

# Object IDs (Azure AD) granted full secret permissions on Key Vault. Not
# secrets — just principal identifiers. Stable values avoid policy churn when
# Terraform runs as different principals locally vs in CI.
variable "operator_object_id" {
  description = "Object ID of the human operator who runs Terraform locally."
  type        = string
  default     = "d5035403-b490-4a28-ba9a-818a9fec560b"
}

variable "ci_sp_object_id" {
  description = "Object ID of the CI service principal (procureiq-gh-deploy). Empty disables the CI policy."
  type        = string
  default     = "8995af59-471d-439c-8caf-a9c9bb8205ad"
}
