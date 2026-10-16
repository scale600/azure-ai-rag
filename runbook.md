# Runbook — Azure RAG Member Support

Day-2 operations for the `azure-ai-rag` service prototype.

## Deploy

```bash
# Infrastructure (Terraform)
cd terraform && terraform plan && terraform apply

# App (Flask API) — pre-built deps (no build on App Service, keeps F1 free-tier quota)
pip install --platform manylinux2014_x86_64 --implementation cp --python-version 3.12 \
  --only-binary=:all: --target /tmp/deps -r api/requirements.txt
# then bundle api/*.py + data/ + deps/ into a zip and:
az webapp deployment source config-zip -g ai-rag-prototype -n web-rag-rl01 --src /tmp/app.zip

# UI — via GitHub Actions (push to main) or SWA CLI
#   azure/static-web-apps-deploy with app_location: ui/
```

> App Service runs on the **F1 free tier** with dependencies pre-installed (bundled in the zip),
> so deployment does NOT run `pip install`. Startup: `python -m gunicorn ... app:app` with
> `PYTHONPATH=/home/site/wwwroot/deps`. This avoids the 60 CPU-min/day quota.

## Re-index

- Manual: `POST /ingest` with `X-API-Key` header.
- Automated: n8n workflow "azure-ai-rag reindex" (hourly Schedule Trigger → `/ingest`).
- Direct: `python api/ingest.py` (reads `data/`, embeds, upserts; uploads raw docs to Blob `raw-docs`).

## Key rotation

```bash
# Azure OpenAI key
az cognitiveservices account keys regenerate -g idp-prototype -n oai-idp-rl01 --key-type primary
NEW_KEY=$(az cognitiveservices account keys list -g idp-prototype -n oai-idp-rl01 --query key1 -o tsv)
az keyvault secret set --name openai-key --vault-name kv-rag-rl01 --value "$NEW_KEY"
az webapp restart -g ai-rag-prototype -n web-rag-rl01

# AI Search key
az search admin-key renew -g ai-rag-prototype --service-name srch-rag-rl01 --key-kind primary
NEW_KEY=$(az search admin-key show -g ai-rag-prototype --service-name srch-rag-rl01 --query primaryKey -o tsv)
az keyvault secret set --name ai-search-key --vault-name kv-rag-rl01 --value "$NEW_KEY"
az webapp restart -g ai-rag-prototype -n web-rag-rl01
```

## Quota increase

Azure OpenAI quota increases are requested at https://aka.ms/oai/quotaincrease
(specify `oai-idp-rl01`, model, and requested TPM/RPM). Current limits are low on the
S0 tier — embedding bursts hit 429 rate limits; `ingest.py` retries with backoff.

## Custom domain

1. In Cloudflare, add `CNAME azure-ai-rag → green-mud-0bccf6910.3.azurestaticapps.net` (proxied).
2. In Azure portal → Static Web App `swa-rag-rl01` → Custom domains → add `azure-ai-rag.techcloudup.com`.
3. Wait for TLS to auto-provision (Free tier, managed cert).

## Budget alert

Azure portal → Cost Management → Budgets → create a monthly budget of **$2** with an
email alert at 80% and 100%. The only metered cost is Azure OpenAI (`gpt-4.1-mini`).

## Tear down

```bash
cd terraform && terraform destroy
# Existing Azure OpenAI (oai-idp-rl01) is a data source and is NOT destroyed.
```
