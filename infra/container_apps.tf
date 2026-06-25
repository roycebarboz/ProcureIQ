resource "azurerm_container_app_environment" "main" {
  name                       = "cae-${var.project}-${var.environment}"
  resource_group_name        = azurerm_resource_group.main.name
  location                   = azurerm_resource_group.main.location
  log_analytics_workspace_id = azurerm_log_analytics_workspace.main.id

  tags = local.common_tags
}

resource "azurerm_container_app" "backend" {
  name                         = "ca-${var.project}-backend-${var.environment}"
  container_app_environment_id = azurerm_container_app_environment.main.id
  resource_group_name          = azurerm_resource_group.main.name
  revision_mode                = "Single"

  identity {
    type         = "UserAssigned"
    identity_ids = [azurerm_user_assigned_identity.backend.id]
  }

  registry {
    server   = azurerm_container_registry.main.login_server
    identity = azurerm_user_assigned_identity.backend.id
  }

  secret {
    name  = "openai-api-key"
    value = azurerm_cognitive_account.openai.primary_access_key
  }

  secret {
    name  = "search-api-key"
    value = azurerm_search_service.main.primary_key
  }

  secret {
    name                = "tavily-api-key"
    key_vault_secret_id = azurerm_key_vault_secret.tavily.versionless_id
    identity            = azurerm_user_assigned_identity.backend.id
  }

  secret {
    name                = "dynatrace-api-token"
    key_vault_secret_id = azurerm_key_vault_secret.dynatrace_api_token.versionless_id
    identity            = azurerm_user_assigned_identity.backend.id
  }

  template {
    min_replicas = 1
    max_replicas = 5

    container {
      name   = "procureiq-backend"
      image  = "mcr.microsoft.com/azuredocs/containerapps-helloworld:latest"
      cpu    = 0.5
      memory = "1Gi"

      env {
        name  = "AZURE_OPENAI_ENDPOINT"
        value = azurerm_cognitive_account.openai.endpoint
      }

      env {
        name  = "AZURE_OPENAI_DEPLOYMENT_GPT4O"
        value = azurerm_cognitive_deployment.gpt4o.name
      }

      env {
        name  = "AZURE_OPENAI_DEPLOYMENT_EMBEDDING"
        value = azurerm_cognitive_deployment.embedding.name
      }

      env {
        name  = "AZURE_SEARCH_ENDPOINT"
        value = "https://${azurerm_search_service.main.name}.search.windows.net"
      }

      # Dynatrace OTLP — app traces + AI/LLM spans + metrics (observability.py).
      env {
        name  = "DT_ENV_URL"
        value = var.dynatrace_env_url
      }

      env {
        name        = "DT_API_TOKEN"
        secret_name = "dynatrace-api-token"
      }

      env {
        name  = "OTEL_SERVICE_NAME"
        value = "procureiq-backend"
      }

      env {
        name  = "ENVIRONMENT"
        value = var.environment
      }

      env {
        name        = "AZURE_OPENAI_API_KEY"
        secret_name = "openai-api-key"
      }

      env {
        name        = "AZURE_SEARCH_API_KEY"
        secret_name = "search-api-key"
      }

      env {
        name  = "AZURE_SEARCH_INDEX_NAME"
        value = "procureiq-policy"
      }

      env {
        name  = "CORS_ALLOW_ORIGINS"
        value = "https://${azurerm_static_web_app.frontend.default_host_name}"
      }

      env {
        name        = "TAVILY_API_KEY"
        secret_name = "tavily-api-key"
      }
    }

    # ── Dynatrace OneAgent (infra telemetry) ────────────────────────────────
    # NOTE: full-stack OneAgent injection is an AKS/VM pattern and is NOT
    # cleanly supported as an Azure Container Apps sidecar (no privileged
    # init, no host access). The supported path for Container Apps infra
    # telemetry is Dynatrace's Azure-native integration (Azure Monitor →
    # Dynatrace), configured at the subscription/Dynatrace tenant level —
    # outside this module. OTLP above already delivers app + AI telemetry.
    #
    # Infra metrics come from the Dynatrace Azure-native integration instead.
  }

  ingress {
    external_enabled = true
    target_port      = 8000

    traffic_weight {
      percentage      = 100
      latest_revision = true
    }
  }

  # CI/CD owns the image after first deploy — prevent terraform apply from reverting it
  lifecycle {
    ignore_changes = [template[0].container[0].image]
  }

  tags = local.common_tags
}
