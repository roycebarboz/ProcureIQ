resource "azurerm_user_assigned_identity" "backend" {
  name                = "id-${var.project}-backend-${var.environment}"
  resource_group_name = azurerm_resource_group.main.name
  location            = azurerm_resource_group.main.location

  tags = local.common_tags
}

resource "azurerm_key_vault" "main" {
  name                       = "kv-${var.project}-${var.environment}"
  resource_group_name        = azurerm_resource_group.main.name
  location                   = azurerm_resource_group.main.location
  tenant_id                  = data.azurerm_client_config.current.tenant_id
  sku_name                   = "standard"
  soft_delete_retention_days = 7

  tags = local.common_tags
}

# Backend service identity — get/list secrets only
resource "azurerm_key_vault_access_policy" "backend" {
  key_vault_id = azurerm_key_vault.main.id
  tenant_id    = data.azurerm_client_config.current.tenant_id
  object_id    = azurerm_user_assigned_identity.backend.principal_id

  secret_permissions = ["Get", "List"]
}

# Deployer — full secret lifecycle for seeding keys
resource "azurerm_key_vault_access_policy" "deployer" {
  key_vault_id = azurerm_key_vault.main.id
  tenant_id    = data.azurerm_client_config.current.tenant_id
  object_id    = data.azurerm_client_config.current.object_id

  secret_permissions = ["Get", "List", "Set", "Delete", "Purge", "Recover"]
}

# Placeholder — replace value after first apply:
#   az keyvault secret set --vault-name kv-procureiq-prod --name tavily-api-key --value "tvly-..."
# ignore_changes prevents Terraform from reverting the real key on subsequent applies.
resource "azurerm_key_vault_secret" "tavily" {
  name         = "tavily-api-key"
  value        = "PLACEHOLDER-set-real-key-via-az-keyvault-secret-set"
  key_vault_id = azurerm_key_vault.main.id

  lifecycle {
    ignore_changes = [value]
  }

  depends_on = [azurerm_key_vault_access_policy.deployer]
}
