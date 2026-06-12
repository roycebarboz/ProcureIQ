resource "azurerm_search_service" "main" {
  name                = "srch-${var.project}-${var.environment}"
  resource_group_name = azurerm_resource_group.main.name
  location            = azurerm_resource_group.main.location
  sku                 = "basic"
  replica_count       = 1
  partition_count     = 1

  tags = local.common_tags
}
