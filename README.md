# ProcureIQ

AI-powered vendor risk copilot. LangGraph multi-agent backend, React frontend, deployed on Azure.

## Infrastructure

All Azure resources are provisioned via Terraform in `infra/`. The backend uses Azure Storage Account for remote state.

### One-time bootstrap (run once before `terraform init`)

Create the storage account that holds Terraform remote state. These resources are intentionally outside Terraform management.

```bash
# Set variables
RESOURCE_GROUP="rg-procureiq-tfstate"
STORAGE_ACCOUNT="stprocureiqtfstate"
CONTAINER="tfstate"
LOCATION="eastus"

# Create resource group
az group create --name $RESOURCE_GROUP --location $LOCATION

# Create storage account
az storage account create \
  --name $STORAGE_ACCOUNT \
  --resource-group $RESOURCE_GROUP \
  --location $LOCATION \
  --sku Standard_LRS \
  --encryption-services blob

# Create blob container
az storage container create \
  --name $CONTAINER \
  --account-name $STORAGE_ACCOUNT
```

### Deploy infrastructure

After the bootstrap step:

```bash
cd infra

# Copy and edit the vars file
cp terraform.tfvars.example terraform.tfvars
# Set subscription_id (and dynatrace_env_url) in terraform.tfvars

# Remote state uses a partial backend — supply state config at init:
cp backend.hcl.example backend.hcl
terraform init -backend-config=backend.hcl
terraform plan
terraform apply
```

### Resources provisioned

| Resource | Name |
|---|---|
| Resource Group | `rg-procureiq-prod` |
| Container Registry | `crprocureiqprod` |
| Key Vault | `kv-procureiq-prod` |
| Log Analytics Workspace | `law-procureiq-prod` (Azure platform/system logs only) |
| Azure OpenAI (`gpt-4o` + `text-embedding-3-small`) | `oai-procureiq-prod` |
| Azure AI Search | `srch-procureiq-prod` |
| Container Apps Environment + App | `cae-procureiq-prod` / `ca-procureiq-backend-prod` |
| Static Web App | `stapp-procureiq-frontend-prod` |

> **Observability** is **Dynatrace** (external SaaS), not an Azure resource. The backend exports app + AI spans via OTLP (`DT_ENV_URL` + `DT_API_TOKEN`); infra telemetry comes from the Dynatrace Azure-native integration (Container Apps has no OneAgent sidecar path). The Dynatrace environment URL and ingest token are stored in Key Vault. Log Analytics is retained only for Azure platform/system logs.

### Variables

| Variable | Default | Description |
|---|---|---|
| `subscription_id` | — | Azure subscription ID (required) |
| `location` | `eastus` | Azure region |
| `environment` | `prod` | Deployment environment |
| `openai_gpt4o_capacity` | `30` | gpt-4o TPM (thousands) |
| `openai_embedding_capacity` | `120` | embedding TPM (thousands) |
| `dynatrace_env_url` | `""` | Dynatrace environment URL for OTLP (no trailing slash) |

## CI/CD

`.github/workflows/ci.yml` runs three jobs on push to `main` (PRs run lint/test/build only):

1. **lint-test** — `ruff check` + `pytest` on `backend/`. Any failure blocks the rest.
2. **build** — `docker build ./backend` → push to ACR (tags: commit SHA + `latest`).
3. **deploy** — `terraform apply` (idempotent infra) + `az containerapp update` (rolls out the new image).

### Required GitHub secrets

| Secret | Purpose |
|---|---|
| `AZURE_CREDENTIALS` | Service-principal JSON for `azure/login` (ACR push, Terraform, Container App update) |
| `ACR_LOGIN_SERVER` | e.g. `crprocureiqprod.azurecr.io` |
| `ARM_SUBSCRIPTION_ID` | Azure subscription ID → `TF_VAR_subscription_id` |
| `DT_ENV_URL` | Dynatrace env URL → `TF_VAR_dynatrace_env_url` |
| `TF_BACKEND_RESOURCE_GROUP` | Terraform remote-state resource group |
| `TF_BACKEND_STORAGE_ACCOUNT` | Terraform remote-state storage account |
| `TF_BACKEND_CONTAINER` | Terraform remote-state blob container |
| `TF_BACKEND_KEY` | Terraform remote-state key (blob name) |

> The Dynatrace **ingest token** (`dynatrace-api-token`) lives in Key Vault, not GitHub — the Container App reads it at runtime via managed identity.
