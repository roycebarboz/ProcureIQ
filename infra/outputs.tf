output "resource_group_name" {
  description = "Resource group name"
  value       = azurerm_resource_group.main.name
}

output "container_registry_login_server" {
  description = "Container Registry login server"
  value       = azurerm_container_registry.main.login_server
}

output "key_vault_uri" {
  description = "Key Vault URI"
  value       = azurerm_key_vault.main.vault_uri
}

output "openai_endpoint" {
  description = "Azure OpenAI endpoint"
  value       = azurerm_cognitive_account.openai.endpoint
}

output "search_endpoint" {
  description = "Azure AI Search endpoint"
  value       = "https://${azurerm_search_service.main.name}.search.windows.net"
}

output "backend_url" {
  description = "Container App backend FQDN"
  value       = "https://${azurerm_container_app.backend.latest_revision_fqdn}"
}

output "frontend_default_host_name" {
  description = "Static Web App default host name"
  value       = "https://${azurerm_static_web_app.frontend.default_host_name}"
}
