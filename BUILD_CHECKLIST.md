# Build Checklist — Azure RAG Member Support

> Target: `azure-ai-rag.techcloudup.com` · Cost ceiling: **< $2/month** · English-first
>
> Legend: `⛔ GATE` = hard stop if it fails · `⚠️ DECIDE` = pick a path before proceeding · `✔` = verification

---

## Phase 0 — Pre-flight (verify existing assets, no code yet)

- [x] `az login` and confirm active subscription = `Azure subscription 1`
  - `az account show`
- [x] Confirm existing Azure OpenAI `oai-idp-rl01` (centralus, S0) still has `gpt-4.1-mini` deployed
  - `az cognitiveservices account deployment list -g idp-prototype -n oai-idp-rl01`
- [x] Confirm **no** Azure AI Search service exists yet (F0 free slot must be free)
  - `az resource list --resource-type Microsoft.Search/searchServices`
- [x] Confirm existing n8n is reachable: `https://n8n.techcloudup.com/`
- [ ] Confirm Cloudflare access to `techcloudup.com` DNS (can add CNAME/TXT)
- [x] `git init` + commit `.gitignore` (already ignores `.env`, `.terraform/`, `*.tfstate*`)

## Phase 1 (M1) — Infrastructure + quota gate

- [x] ⛔ **GATE — embedding quota**: request `text-embedding-3-small` deployment on `oai-idp-rl01` (centralus)
  - ⚠️ If denied → drop vector search entirely (keyword-only BM25), skip embedding entirely
  - If approved → record the deployment name (`text-embedding-3-small`)
- [x] Scaffold Terraform: `main.tf`, `variables.tf`, `outputs.tf`, `backend.tf` (remote tfstate in Blob)
- [x] Define resources: resource group, `azurerm_static_web_app` (Free), `azurerm_search_service` (free), `azurerm_linux_web_app` (F1), Key Vault + access policy, storage account + `raw-docs` container, App Insights
- [x] Azure OpenAI: use `data "azurerm_cognitive_account"` for `oai-idp-rl01` (do **not** create a new one); add `azurerm_cognitive_deployment` for the embedding model only
- [x] `terraform plan` → `terraform apply`
  - ✔ `terraform apply` reproduces infra from empty state
- [x] Create `member-support` index schema (per PRD §6); set `content_vector` as `Collection(Edm.Single)` vector(1536), HNSW
- [x] ⛔ **GATE — F0 vector index**: confirm the vector index provisions without hanging at "Allocating compute"
  - ⚠️ If it hangs/fails → drop `content_vector`, go keyword-only BM25
- [x] Manually inject secrets into Key Vault: `ai-search-key`, `openai-key` (from `oai-idp-rl01`)
  - `az keyvault secret set --name openai-key --vault-name <kv> --value <key>`
- [x] Grant App Service system-assigned MI `get` on Key Vault (access policy)
- [x] Wire App Settings with `@Microsoft.KeyVault(SecretUri=...)` references (no hardcoded keys)
- [x] GitHub Actions: `terraform plan` (PR) + `terraform apply` (main) + build/deploy steps

## Phase 2 (M2) — Data + ingestion

- [x] Collect 30+ FAQ / fee / loan documents into `data/` (Markdown/text)
- [x] Write `ingest.py`: chunk (500 tokens / 50 overlap) → embed (`text-embedding-3-small`) → upsert (`IndexDocumentsBatch`)
- [x] Idempotency: `id = sha256(content)[:16] + '-' + chunk_idx`
- [x] Run ingestion → index (Blob `raw-docs` upload deferred to Phase 4 n8n sync)
  - ✔ Documents visible in AI Search portal; citation `source_url` populated

## Phase 3 (M3) — RAG API

- [x] Flask app: `POST /ask`, `POST /ingest`, `GET /health`
- [x] Hybrid search: vector + BM25, RRF fusion, top-k=5
- [x] Prompt template per PRD §8.2 (grounded + `[Sources: ...]`)
- [x] Response format per PRD §8.3 (answer + sources + latency + model)
- [x] CORS: allow only `azure-ai-rag.techcloudup.com`
- [x] Cost guardrail on `/ask`: daily query cap (e.g. 100/day) + rate limit (e.g. 1 req/5s per IP)
- [x] `X-API-Key` auth on `/ingest`
- [x] Eval: 20-question set → accuracy ≥ 80%, p95 < 5s (warm path) — result: 100% (20/20), ~3s
  - ⚠️ If accuracy < 80% → tune chunk size / top-k / prompt before moving on

## Phase 4 (M4) — Automation (re-index on doc change)

- [x] ⚠️ **DECIDE** sync mechanism — chose (a) n8n Schedule Trigger (hourly) (n8n has no native Azure Storage trigger):
  - (a) n8n **Schedule Trigger** polling Blob → `Flask /ingest` (simplest)
  - (b) **Event Grid → Webhook** → n8n
  - (c) **Azure Function (Blob trigger) → Flask /ingest**
- [x] Implement chosen path on the existing n8n instance (`n8n.techcloudup.com`) — workflow "azure-ai-rag reindex" created + active
  - ✔ Upload a new doc → index auto-refreshes (end-to-end verify pending Phase 5 deploy)

## Phase 5 (M5) — Deploy, domain, docs, keep-warm

- [x] Build chat UI (static HTML/JS) → deploy to Static Web App (`azure/static-web-apps-deploy`)
- [x] Cloudflare DNS: `CNAME azure-ai-rag → green-mud-0bccf6910.3.azurestaticapps.net` (proxy OFF for validation)
- [x] Add custom domain `azure-ai-rag.techcloudup.com` to SWA (Free tier, free TLS)
  - ✔ HTTPS works on the custom domain (DigiCert cert, status Ready)
- [ ] Set Azure Cost Management budget alert at **$2**
- [x] Keep-warm: GH Actions cron pinging `/health` every ~5 min (keeps F1 warm + F0 alive)
- [x] Write `README.md` (architecture / tech stack / structure / quick start)
- [x] Write `runbook.md` (re-index, key rotation, quota increase)
- [x] Final acceptance sweep (PRD §15) — eval 100% (20/20), warm p95 ~3s, HTTPS live

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
