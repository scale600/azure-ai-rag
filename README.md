# azure-ai-rag

**RAG-based member support knowledge retrieval on Azure** — a service prototype that answers member questions with grounded answers and citations, built on Azure free tiers and an existing Azure OpenAI resource.

> Target: `azure-ai-rag.techcloudup.com` · Infra: **Terraform**

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

## Repo structure

```
.
├── PRD.md                     # product / requirements
├── BUILD_CHECKLIST.md         # executable build sequence
├── runbook.md                 # day-2 operations
├── api/                       # Flask API (app.py, rag.py, ingest.py, eval.py)
├── data/                      # 31 financial docs (ingestion source)
├── ui/                        # chat UI (index.html)
├── terraform/                 # IaC (providers, main, variables, locals, outputs)
├── docs/
│   ├── terraform-conventions.md
│   ├── deployment-runbook.md
│   └── cicd-pipeline.md
└── .github/workflows/         # terraform + deploy + keep-warm
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

# 4. Deploy the Flask API with pre-built deps (no on-host build → keeps F1 quota)
pip install --platform manylinux2014_x86_64 --implementation cp --python-version 3.12 \
  --only-binary=:all: --target /tmp/deps -r api/requirements.txt
#    bundle api/*.py + data/ + deps/ into a zip, then:
az webapp deployment source config-zip -g ai-rag-prototype -n web-rag-rl01 --src app.zip

# 5. Deploy the chat UI (push to main → GitHub Actions, or SWA CLI)
```

## Docs

- [PRD](PRD.md) — requirements & design
- [Build checklist](BUILD_CHECKLIST.md) — ordered execution plan
- [Terraform conventions](docs/terraform-conventions.md)
- [Deployment runbook](docs/deployment-runbook.md)
- [CI/CD](docs/cicd-pipeline.md)

## Status

**Live** at `https://azure-ai-rag.techcloudup.com` — all phases complete (infra, 31-doc ingestion, RAG API with eval 100% (20/20), n8n re-index automation, deployment). Monthly cost **< $2** (free tiers + Azure OpenAI pay-as-you-go).
