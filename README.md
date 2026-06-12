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
# Set subscription_id in terraform.tfvars

terraform init
terraform plan
terraform apply
```

### Resources provisioned

| Resource | Name |
|---|---|
| Resource Group | `rg-procureiq-prod` |
| Container Registry | `crprocureiqprod` |
| Key Vault | `kv-procureiq-prod` |
| Log Analytics Workspace | `law-procureiq-prod` |
| Application Insights | `ai-procureiq-prod` |
| Azure OpenAI (`gpt-4o` + `text-embedding-3-small`) | `oai-procureiq-prod` |
| Azure AI Search | `srch-procureiq-prod` |
| Container Apps Environment + App | `cae-procureiq-prod` / `ca-procureiq-backend-prod` |
| Static Web App | `stapp-procureiq-frontend-prod` |

### Variables

| Variable | Default | Description |
|---|---|---|
| `subscription_id` | — | Azure subscription ID (required) |
| `location` | `eastus` | Azure region |
| `environment` | `prod` | Deployment environment |
| `openai_gpt4o_capacity` | `30` | gpt-4o TPM (thousands) |
| `openai_embedding_capacity` | `120` | embedding TPM (thousands) |
