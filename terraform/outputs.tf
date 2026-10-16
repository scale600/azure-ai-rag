output "resource_group_name" {
  value = azurerm_resource_group.main.name
}

output "openai_endpoint" {
  description = "Existing Azure OpenAI endpoint (reused)."
  value       = data.azurerm_cognitive_account.oai.endpoint
}

output "search_endpoint" {
  value = "https://${azurerm_search_service.main.name}.search.windows.net"
}

output "flask_api_url" {
  value = "https://${azurerm_linux_web_app.main.default_hostname}"
}

output "static_web_app_default_hostname" {
  value = azurerm_static_web_app.main.default_host_name
}

output "key_vault_uri" {
  value = azurerm_key_vault.main.vault_uri
}
