# azure-ai-rag

**RAG-based member support knowledge retrieval on Azure** — a service prototype that answers member questions with grounded answers and citations, built on Azure free tiers and an existing Azure OpenAI resource.

> Target: `azure-ai-rag.techcloudup.com` · Cost ceiling: **< $2/month** · Infra: **Terraform**

## What it does

Ingests financial-institution public documents (fees, loans, FAQ) into Azure AI Search and answers questions with **hybrid retrieval (vector + BM25, RRF fusion)** plus **citation-grounded generation** via Azure OpenAI.

## Architecture

```
Static Web App (Free)   — chat UI, custom domain
        │ fetch /ask (CORS)
        ▼
App Service F1          — Flask API (/ask · /ingest · /health)
        │
        ├─► Azure AI Search F0    — hybrid search (vector + BM25, RRF)
        ├─► Azure OpenAI (existing oai-idp-rl01) — text-embedding-3-small + gpt-4.1-mini
        └─► Azure Key Vault       — secrets via Managed Identity
```

## Tech stack

| Layer | Choice |
|---|---|
| Search | Azure AI Search (F0) — hybrid, RRF |
| LLM | Azure OpenAI `gpt-4.1-mini` (generation), `text-embedding-3-small` (embedding) |
| API | Flask (Python 3.12) on App Service F1 |
| UI | Static Web App (Free) |
| Infra | Terraform (azurerm), remote state in Blob |
| CI/CD | GitHub Actions (OIDC → Azure) |
| Secrets | Key Vault + Managed Identity |
| Automation | n8n (existing instance) |

## Cost (target)

| Service | Cost |
|---|---|
| SWA Free + App Service F1 + AI Search F0 | $0 |
| Azure OpenAI `gpt-4.1-mini` (demo traffic) | ~$0.5–1/mo |
| Key Vault + Blob | < $0.02/mo |
| **Total** | **< $2/mo** |

## Repo structure

```
.
├── PRD.md                     # product / requirements
├── BUILD_CHECKLIST.md         # executable build sequence
├── terraform/                 # IaC (providers, main, variables, locals, outputs)
├── docs/
│   ├── terraform-conventions.md
│   ├── deployment-runbook.md
│   └── cicd-pipeline.md
└── .github/workflows/         # terraform + deploy pipelines
```

## Quick start

```bash
# 1. Bootstrap remote state (once)
az group create -n ai-rag-tfstate -l centralus
#    + create storage account `stragstaterl01` and container `tfstate`

# 2. Plan & apply
cd terraform
terraform init
terraform plan
terraform apply

# 3. One-time manual secrets (see docs/deployment-runbook.md)
#    - set openai-key + ai-search-key in Key Vault
```

## Docs

- [PRD](PRD.md) — requirements & design
- [Build checklist](BUILD_CHECKLIST.md) — ordered execution plan
- [Terraform conventions](docs/terraform-conventions.md)
- [Deployment runbook](docs/deployment-runbook.md)
- [CI/CD](docs/cicd-pipeline.md)

## Status

Service prototype — infra scaffold committed; app code (`api/`, `ui/`) and deployment pending. See `BUILD_CHECKLIST.md`.
