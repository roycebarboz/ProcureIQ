# Observability is Dynatrace (external SaaS), not Azure-native — see Slice 13.
# Application Insights has been removed. Log Analytics is retained only for
# Azure platform / Container Apps system logs (stdout/stderr, system metrics).
resource "azurerm_log_analytics_workspace" "main" {
  name                = "law-${var.project}-${var.environment}"
  resource_group_name = azurerm_resource_group.main.name
  location            = azurerm_resource_group.main.location
  sku                 = "PerGB2018"
  retention_in_days   = 30

  tags = local.common_tags
}
