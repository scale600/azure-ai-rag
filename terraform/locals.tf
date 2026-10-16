locals {
  resource_group_name = "ai-rag-prototype"

  # `{abbrev}-{project}-rl{NN}` — continues the existing IDP convention (`oai-idp-rl01`).
  # NOTE: App Service / Static Web App / Storage names must be globally unique; adjust if taken.
  names = {
    search        = "srch-rag-rl01"
    service_plan  = "plan-rag-rl01"
    app_service   = "web-rag-rl01"
    static_web    = "swa-rag-rl01"
    key_vault     = "kv-rag-rl01"
    storage       = "stragrl01"
    app_insights  = "appi-rag-rl01"
    log_analytics = "law-rag-rl01"
  }

  tags = {
    project    = "ai-rag"
    env        = "dev"
    managed-by = "terraform"
  }
}
