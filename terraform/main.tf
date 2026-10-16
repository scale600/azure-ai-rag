# ── Resource group ─────────────────────────────────────────────
resource "azurerm_resource_group" "main" {
  name     = local.resource_group_name
  location = var.location
  tags     = local.tags
}

# ── Azure OpenAI: REUSE existing resource (do NOT create) ──────
data "azurerm_cognitive_account" "oai" {
  name                = var.existing_openai_name
  resource_group_name = var.existing_openai_rg
}

# Embedding deployment — M1 quota gate. `terraform apply` fails here if quota is denied.
resource "azurerm_cognitive_deployment" "embedding" {
  name                 = var.embedding_model
  cognitive_account_id = data.azurerm_cognitive_account.oai.id

  model {
    format  = "OpenAI"
    name    = var.embedding_model
    version = var.embedding_model_version
  }

  sku {
    name = "GlobalStandard"
  }
}

# ── Azure AI Search (F0) ───────────────────────────────────────
resource "azurerm_search_service" "main" {
  name                = local.names.search
  resource_group_name = azurerm_resource_group.main.name
  location            = azurerm_resource_group.main.location
  sku                 = "free" # F0 — 1 per subscription, no MI / no semantic ranker
  tags                = local.tags
}

# The search index is a data-plane resource created at runtime by ingest.py
# (azure-search-documents SDK) — not an ARM resource, so it isn't defined here.

# ── Storage (raw docs) ─────────────────────────────────────────
resource "azurerm_storage_account" "main" {
  name                     = local.names.storage
  resource_group_name      = azurerm_resource_group.main.name
  location                 = azurerm_resource_group.main.location
  account_tier             = "Standard"
  account_replication_type = "LRS"
  tags                     = local.tags
}

resource "azurerm_storage_container" "raw_docs" {
  name                  = "raw-docs"
  storage_account_id    = azurerm_storage_account.main.id
  container_access_type = "private"
}

# ── Key Vault + secrets + access policy ────────────────────────
resource "azurerm_key_vault" "main" {
  name                = local.names.key_vault
  resource_group_name = azurerm_resource_group.main.name
  location            = azurerm_resource_group.main.location
  tenant_id           = data.azurerm_client_config.current.tenant_id
  sku_name            = "standard"
  tags                = local.tags
}

# App Service MI → Key Vault `get` (secrets themselves are set manually, see runbook).
resource "azurerm_key_vault_access_policy" "app_service" {
  key_vault_id = azurerm_key_vault.main.id
  tenant_id    = data.azurerm_client_config.current.tenant_id
  object_id    = azurerm_linux_web_app.main.identity[0].principal_id

  secret_permissions = ["Get"]
}

# Grants the operator (Terraform runner) permission to inject secrets manually.
resource "azurerm_key_vault_access_policy" "operator" {
  key_vault_id = azurerm_key_vault.main.id
  tenant_id    = data.azurerm_client_config.current.tenant_id
  object_id    = data.azurerm_client_config.current.object_id

  secret_permissions = ["Get", "Set", "List", "Delete"]
}

# ── App Service (Flask API) ────────────────────────────────────
resource "azurerm_service_plan" "main" {
  name                = local.names.service_plan
  resource_group_name = azurerm_resource_group.main.name
  location            = azurerm_resource_group.main.location
  os_type             = "Linux"
  sku_name            = "B1" # Basic — dedicated compute, no daily CPU quota
  tags                = local.tags
}

resource "azurerm_linux_web_app" "main" {
  name                = local.names.app_service
  resource_group_name = azurerm_resource_group.main.name
  location            = azurerm_service_plan.main.location
  service_plan_id     = azurerm_service_plan.main.id
  tags                = local.tags

  identity {
    type = "SystemAssigned"
  }

  app_settings = {
    "AZURE_OPENAI_ENDPOINT"                = data.azurerm_cognitive_account.oai.endpoint
    "AZURE_OPENAI_KEY"                     = "@Microsoft.KeyVault(SecretUri=${azurerm_key_vault.main.vault_uri}secrets/openai-key/)"
    "AZURE_OPENAI_CHAT_DEPLOYMENT"         = var.chat_model_deployment
    "AZURE_OPENAI_EMBEDDING_DEPLOYMENT"    = var.embedding_model
    "AZURE_SEARCH_ENDPOINT"                = "https://${azurerm_search_service.main.name}.search.windows.net"
    "AZURE_SEARCH_KEY"                     = "@Microsoft.KeyVault(SecretUri=${azurerm_key_vault.main.vault_uri}secrets/ai-search-key/)"
    "INGEST_API_KEY"                       = "@Microsoft.KeyVault(SecretUri=${azurerm_key_vault.main.vault_uri}secrets/ingest-api-key/)"
    "AZURE_STORAGE_CONNECTION_STRING"      = "@Microsoft.KeyVault(SecretUri=${azurerm_key_vault.main.vault_uri}secrets/storage-conn/)"
    "DATA_DIR"                             = "/app/data"
  }

  site_config {
    always_on = true
    application_stack {
      python_version = "3.12"
    }
  }
}

# ── Static Web App (chat UI) ───────────────────────────────────
resource "azurerm_static_web_app" "main" {
  name                = local.names.static_web
  resource_group_name = azurerm_resource_group.main.name
  location            = var.location
  sku_tier            = "Free"
  sku_size            = "Free"
  tags                = local.tags
}

# ── Monitoring ─────────────────────────────────────────────────
resource "azurerm_log_analytics_workspace" "main" {
  name                = local.names.log_analytics
  resource_group_name = azurerm_resource_group.main.name
  location            = azurerm_resource_group.main.location
  sku                 = "PerGB2018"
  retention_in_days   = 30
  tags                = local.tags
}

resource "azurerm_application_insights" "main" {
  name                = local.names.app_insights
  resource_group_name = azurerm_resource_group.main.name
  location            = azurerm_resource_group.main.location
  workspace_id        = azurerm_log_analytics_workspace.main.id
  application_type    = "web"
  tags                = local.tags
}
