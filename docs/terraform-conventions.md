# Terraform Conventions — Azure RAG Member Support

> IaC standards for this project. Applies to everything under `terraform/`.

## Directory layout

```
terraform/
  backend.tf        # remote state (Azure Blob) — do not edit casually
  providers.tf      # azurerm + required_version pinning
  main.tf           # resource definitions (flat for a prototype)
  variables.tf      # input variables (typed, described)
  outputs.tf        # values other steps need (endpoints, names)
  locals.tf         # naming/tagging helpers
```

- **Keep it flat** — no `modules/` until a resource set is reused by a second project.
  Extraction rule: extract a module only when you'd otherwise copy-paste ≥ 2 identical blocks.

## Remote state (Azure Blob)

- Backend: `azurerm` with an Azure Storage blob. **State is the source of truth.**
- Bootstrap once (manual, not managed by Terraform): resource group `ai-rag-tfstate`, storage account `stragstaterl01`, container `tfstate`.
- State key: `ai-rag/terraform.tfstate` (path-per-project so future projects can share the account).
- Locking: the Azure backend locks state via blob lease automatically — never run two applies concurrently.
- Never commit `*.tfstate*` (already in `.gitignore`).

## Naming convention

Follow the existing IDP pattern `{abbrev}-{project}-rl{NN}`:

| Resource | Name |
|---|---|
| Resource group | `ai-rag-prototype` |
| Azure AI Search | `srch-rag-rl01` |
| App Service (Flask API) | `web-rag-rl01` |
| Static Web App | `swa-rag-rl01` |
| Key Vault | `kv-rag-rl01` |
| Storage (raw docs) | `stragrl01` |
| App Insights | `appi-rag-rl01` |
| Log Analytics | `law-rag-rl01` |

- Azure OpenAI is **reused** (`oai-idp-rl01`) via a `data` source — do NOT create a new one.
- Key Vault secret names (kebab-case): `ai-search-key`, `openai-key`.

## Tagging (apply to all resources)

```hcl
project    = "ai-rag"
env        = "dev"
managed-by = "terraform"
```

## Secrets & variables

- **Secrets never live in Terraform code or `.tfvars`.**
  1. Manually set in Key Vault (one-time, see `deployment-runbook.md`): `openai-key`, `ai-search-key`
  2. Referenced from App Service via `@Microsoft.KeyVault(SecretUri=...)` in App Settings
- Non-secret config → `variables.tf` with `type` + `description`; overrides in `terraform.tfvars` (ignored).
- Provide a committed `terraform.tfvars.example` so others can copy.

## Providers & versions

- `azurerm` pinned to a specific minor version (no floating `~>` across majors).
- `terraform { required_version = ">= 1.6" }`.

## Do / Don't

- ✅ Use `data` sources for shared/existing resources (`oai-idp-rl01`).
- ✅ Pin SKUs explicitly (`sku = "free"`, `sku = "F1"`, `sku = "Free"`).
- ✅ `terraform plan` before every apply; review the diff.
- ❌ No `terraform apply -auto-approve` outside CI.
- ❌ No secrets in variables, locals, or outputs.
