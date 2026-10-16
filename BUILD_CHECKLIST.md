# Build Checklist — Azure RAG Member Support

> Target: `azure-ai-rag.techcloudup.com` · Cost ceiling: **< $2/month** · English-first
>
> Legend: `⛔ GATE` = hard stop if it fails · `⚠️ DECIDE` = pick a path before proceeding · `✔` = verification

---

## Phase 0 — Pre-flight (verify existing assets, no code yet)

- [ ] `az login` and confirm active subscription = `Azure subscription 1`
  - `az account show`
- [ ] Confirm existing Azure OpenAI `oai-idp-rl01` (centralus, S0) still has `gpt-4.1-mini` deployed
  - `az cognitiveservices account deployment list -g idp-prototype -n oai-idp-rl01`
- [ ] Confirm **no** Azure AI Search service exists yet (F0 free slot must be free)
  - `az resource list --resource-type Microsoft.Search/searchServices`
- [ ] Confirm existing n8n is reachable: `https://n8n.techcloudup.com/`
- [ ] Confirm Cloudflare access to `techcloudup.com` DNS (can add CNAME/TXT)
- [ ] `git init` + commit `.gitignore` (already ignores `.env`, `.terraform/`, `*.tfstate*`)

## Phase 1 (M1) — Infrastructure + quota gate

- [ ] ⛔ **GATE — embedding quota**: request `text-embedding-3-small` deployment on `oai-idp-rl01` (centralus)
  - ⚠️ If denied → drop vector search entirely (keyword-only BM25), skip embedding entirely
  - If approved → record the deployment name (`text-embedding-3-small`)
- [ ] Scaffold Terraform: `main.tf`, `variables.tf`, `outputs.tf`, `backend.tf` (remote tfstate in Blob)
- [ ] Define resources: resource group, `azurerm_static_web_app` (Free), `azurerm_search_service` (free), `azurerm_linux_web_app` (F1), Key Vault + access policy, storage account + `raw-docs` container, App Insights
- [ ] Azure OpenAI: use `data "azurerm_cognitive_account"` for `oai-idp-rl01` (do **not** create a new one); add `azurerm_cognitive_deployment` for the embedding model only
- [ ] `terraform plan` → `terraform apply`
  - ✔ `terraform apply` reproduces infra from empty state
- [ ] Create `member-support` index schema (per PRD §6); set `content_vector` as `Collection(Edm.Single)` vector(1536), HNSW
- [ ] ⛔ **GATE — F0 vector index**: confirm the vector index provisions without hanging at "Allocating compute"
  - ⚠️ If it hangs/fails → drop `content_vector`, go keyword-only BM25
- [ ] Manually inject secrets into Key Vault: `ai-search-key`, `openai-key` (from `oai-idp-rl01`)
  - `az keyvault secret set --name openai-key --vault-name <kv> --value <key>`
- [ ] Grant App Service system-assigned MI `get` on Key Vault (access policy)
- [ ] Wire App Settings with `@Microsoft.KeyVault(SecretUri=...)` references (no hardcoded keys)
- [ ] GitHub Actions: `terraform plan` (PR) + `terraform apply` (main) + build/deploy steps

## Phase 2 (M2) — Data + ingestion

- [ ] Collect 30+ FAQ / fee / loan documents into `docs/` (Markdown/text)
- [ ] Write `ingest.py`: extract (`pypdf`/`BeautifulSoup`) → chunk (500 tokens / 50 overlap) → embed (`text-embedding-3-small`, batch 16) → upsert (`IndexDocumentsBatch`)
- [ ] Idempotency: `id = sha256(content)[:16] + '-' + chunk_idx`
- [ ] Run ingestion → upload to Blob `raw-docs` → index
  - ✔ Documents visible in AI Search portal; citation `source_url` populated

## Phase 3 (M3) — RAG API

- [ ] Flask app: `POST /ask`, `POST /ingest`, `GET /health`
- [ ] Hybrid search: vector + BM25, RRF fusion, top-k=5
- [ ] Prompt template per PRD §8.2 (grounded + `[Sources: ...]`)
- [ ] Response format per PRD §8.3 (answer + sources + latency + model)
- [ ] CORS: allow only `azure-ai-rag.techcloudup.com`
- [ ] Cost guardrail on `/ask`: daily query cap (e.g. 100/day) + rate limit (e.g. 1 req/5s per IP)
- [ ] `X-API-Key` auth on `/ingest`
- [ ] Eval: 20-question set → accuracy ≥ 80%, p95 < 5s (warm path)
  - ⚠️ If accuracy < 80% → tune chunk size / top-k / prompt before moving on

## Phase 4 (M4) — Automation (re-index on doc change)

- [ ] ⚠️ **DECIDE** sync mechanism (n8n has no native Azure Storage trigger):
  - (a) n8n **Schedule Trigger** polling Blob → `Flask /ingest` (simplest)
  - (b) **Event Grid → Webhook** → n8n
  - (c) **Azure Function (Blob trigger) → Flask /ingest**
- [ ] Implement chosen path on the existing n8n instance (`n8n.techcloudup.com`)
  - ✔ Upload a new doc → index auto-refreshes

## Phase 5 (M5) — Deploy, domain, docs, keep-warm

- [ ] Build chat UI (static HTML/JS) → deploy to Static Web App (`azure/static-web-apps-deploy`)
- [ ] Cloudflare DNS: `CNAME azure-ai-rag → <swa-host>.azurestaticapps.net` (proxied) + SWA verification record
- [ ] Add custom domain `azure-ai-rag.techcloudup.com` to SWA (Free tier, free TLS)
  - ✔ HTTPS works on the custom domain
- [ ] Set Azure Cost Management budget alert at **$2**
- [ ] Keep-warm: free uptime monitor (or GH Actions cron) pinging `/health` every ~5 min (keeps F1 warm + F0 alive)
- [ ] Write `README.md` (architecture / cost / security) + `runbook.md` (re-index, key rotation, quota increase)
- [ ] Final acceptance sweep (PRD §15)

---

## Go/No-go summary

| Gate | Where | Pass → | Fail → |
|---|---|---|---|
| Embedding `text-embedding-3-small` quota | Phase 1 | Build hybrid RAG | Keyword-only BM25 (drop embeddings) |
| F0 vector index provisioning | Phase 1 | Hybrid RAG viable on Free | Keyword-only BM25, or reopen budget for Basic (~$66–73/mo) |
| Eval accuracy ≥ 80% | Phase 3 | Proceed to automation | Tune chunk/top-k/prompt first |

## Cost recap (target)

| Service | Cost |
|---|---|
| SWA Free + App Service F1 + AI Search F0 | $0 |
| Azure OpenAI `gpt-4.1-mini` (demo traffic) | ~$0.5–1/mo |
| Key Vault + Blob | < $0.02/mo |
| **Total** | **< $2/mo** |
