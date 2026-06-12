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
