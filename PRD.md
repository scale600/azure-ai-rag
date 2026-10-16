# PRD — AI-Powered Member Support Knowledge Retrieval (RAG)

| Item | Detail |
|---|---|
| Status | Draft v1.0 |
| Date | 2026-10-16 |
| Target | Financial institution member support — "AI-powered member support, agent assist, knowledge retrieval" |
| Key constraint | Azure free tiers (SWA/F0/F1) + reuse existing Azure OpenAI resource, target < $2/month pay-as-you-go |
| Deployment domain | `azure-ai-rag.techcloudup.com` |

---

## 1. Overview

Build a knowledge base from a financial institution's public documents (fee schedules, loan terms, member FAQ, etc.) and generate **grounded answers with citations** to member questions via RAG (Retrieval-Augmented Generation).

The goal of this project is not a throwaway demo but to **validate "AI/LLM integration patterns proven in the financial domain" as a service prototype**. It must therefore be (1) reproducible via IaC, (2) production-grade in its security configuration (secret management), and (3) explicit about its cost boundary.

### 1.1 Background

- Existing skill stack: Flask, n8n, GCP/Azure, Python, Terraform, GitHub Actions
- Goal: complete a service prototype that combines AI/LLM integration capability with cloud infrastructure expertise
- Required capabilities: knowledge retrieval, member support, agent assist

### 1.2 Success Criteria

1. Return **accurate answers + source URLs** for real FAQ questions (accuracy ≥ 80% on a demo evaluation set)
2. End-to-end response latency p95 < 5s (warm path; cold start excluded — F1 has no Always On)
3. All secrets (AI Search key, Azure OpenAI key) stored in Key Vault; no hardcoding in code or commits
4. Infrastructure reproducible from scratch with `terraform apply` alone
5. Monthly operating cost (Azure OpenAI pay-as-you-go) < $2 (service prototype, minimal demo traffic)

---

## 2. Goals & Non-Goals

### 2.1 Goals (In-scope)

- Text ingestion → chunking → embedding → AI Search indexing pipeline
- RAG query API based on hybrid search (vector + keyword)
- Answer generation with citations
- Simple chat UI (Azure Static Web App — static frontend)
- Automated index synchronization via n8n
- Terraform + GitHub Actions deployment, Key Vault secret management

### 2.2 Non-Goals (Out-of-scope)

- Multimodal (image/scanned PDF) document processing — that's Project 1 (IDP) territory
- Semantic Ranker (unsupported on F0) — extension item if upgraded to Basic
- Real-time streaming responses (SSE), multi-turn conversation memory
- User authentication/authorization (internal demo purpose)
- MLOps / model fine-tuning

---

## 3. User Stories

| ID | User | Story |
|---|---|---|
| US-1 | Member | Asks "What are the fee refund conditions?" and receives an answer with links to source documents |
| US-2 | Member | When a question isn't in the FAQ, receives an honest "I don't know" plus contact center info |
| US-3 | Operator | Uploads a new FAQ document and n8n automatically refreshes the index |
| US-4 | Operator | Clicks an answer's citation to view the source document |

---

## 4. Architecture

```
                    ┌─────────────────────────────────────────────────┐
                    │         Azure Static Web App (Free)             │
                    │     Chat UI — azure-ai-rag.techcloudup.com      │
                    └──────────────────────┬──────────────────────────┘
                                           │ fetch /ask (CORS)
                                           ▼
                    ┌─────────────────────────────────────────────────┐
                    │       Azure App Service (F1 Free)               │
                    │       Flask API (/ask · /ingest · /health)      │
                    └──────────────┬───────────────────┬──────────────┘
                          (a) query │                   │ (b) document upload
                                    ▼                   ▼
                    ┌──────────────────────────┐  ┌──────────────────────┐
                    │  Azure AI Search (F0)    │  │  Azure Blob Storage  │
                    │  hybrid search           │  │  (raw doc store)     │
                    │  (vector + BM25, RRF)    │  └──────────┬───────────┘
                    └──────────────┬───────────┘             │
                                   │                         │ Blob trigger
                                   ▼                         ▼
                    ┌──────────────────────────┐  ┌──────────────────────┐
                    │   Azure OpenAI           │  │  n8n (existing)      │
                    │  - text-embedding-3-small│  │  detect doc changes  │
                    │  - GPT-4.1 mini (gen)    │  │  call ingestion      │
                    └──────────────┬───────────┘  └──────────────────────┘
                                   │
                    ┌──────────────▼───────────┐
                    │   Azure Key Vault        │
                    │  (AI Search/OpenAI keys) │
                    └──────────────────────────┘
```

### 4.1 Component Responsibilities

| Component | Responsibility | Tier |
|---|---|---|
| Chat UI (Static Web App) | Static frontend, calls `/ask`, custom domain | **SWA Free** |
| Flask API | `/ask` query, `/ingest` manual re-index | App Service F1 |
| Azure AI Search | Document index + hybrid search | **F0 (Free)** |
| Azure OpenAI (existing `oai-idp-rl01`) | Embedding generation + answer generation | Pay-as-you-go (S0, reuse existing resource) |
| Azure Blob Storage | Raw document storage | LRS, a few cents |
| Azure Key Vault | AI Search key, OpenAI key, (optional) storage key | Standard |
| n8n | Detect document changes → re-index automation | Reuse existing instance (`n8n.techcloudup.com`) |

---

## 5. Tech Stack & Tier Decisions (post-review)

### 5.1 Tier choice: AI Search F0 (Free) — confirmed

| F0 constraint | Design response |
|---|---|
| Managed Identity **not supported** | Use API-key auth; keys fetched from Key Vault (see §10) |
| Semantic Ranker **not supported** | Compensate with hybrid search + RRF (Reciprocal Rank Fusion) |
| 50MB storage | Index text only (exclude images/binary), compress with 500-token chunks |
| 3 indexes | Use only 1 index |
| 1 free service per subscription | Create only 1 for this project |
| May be deleted when inactive | Document in README + keep alive with periodic health check (or ping) |

> ⚠️ **Design point**: recognizing free-tier constraints (inactive deletion, no MI) and designing around them (key auth + RRF) itself demonstrates operational awareness.

### 5.2 Model selection

| Use | Model | Cost (per 1M tokens) | Rationale |
|---|---|---|---|
| Embedding | `text-embedding-3-small` (1536-dim) | $0.02 input | Cheapest + 1536d is sufficient (new deployment — quota request required; fall back to local embedding 384d if denied) |
| Generation (default) | `gpt-4.1-mini` | ~$0.40 in / ~$1.60 out | Already deployed on existing resource, optimal for demo traffic |
| Generation (optional upgrade) | `gpt-5.4-mini` | $0.75 in / $4.50 out | Latest/higher quality (new quota request required) |

> **Selection guide**: this is a service prototype with minimal demo traffic, so **`gpt-4.1-mini` is the default** (already deployed, under $1/month). Upgrade to `gpt-5.4-mini` only when quality/latest-model emphasis is needed (separate quota request). GlobalStandard/Flex deployment types can cut input cost by 50%.

### 5.3 Hybrid search strategy (Semantic Ranker substitute)

- **Vector search**: HNSW, cosine similarity against query embedding (top-k=5)
- **Keyword search**: BM25 full-text (top-k=5)
- **Fusion**: merge both result sets via RRF (Reciprocal Rank Fusion) → final top-k=5

This runs fully free on F0 and substitutes a large part of Semantic Ranker (paid).

---

## 6. Data Model (AI Search index schema)

Index name: `member-support`

| Field | Type | Attributes | Description |
|---|---|---|---|
| `id` | Edm.String | key, retrievable | `{doc_hash}-{chunk_idx}` |
| `content` | Edm.String | searchable, retrievable | Chunk body |
| `content_vector` | Collection(Edm.Single) | vector(1536), HNSW | Chunk embedding |
| `title` | Edm.String | searchable, retrievable | Document title |
| `source_url` | Edm.String | retrievable | Source URL (for citation) |
| `category` | Edm.String | filterable, facetable | e.g. fees / loans / faq / kyc |
| `chunk_id` | Edm.Int32 | retrievable | Chunk ordinal (for reconstructing source) |
| `last_updated` | Edm.DateTimeOffset | sortable | Indexed timestamp |

### 6.1 Chunking strategy

- Chunk size: **500 tokens** (tiktoken), overlap **50 tokens (10%)**
- Split at paragraph/heading boundaries (avoid mid-sentence cuts)
- Replicate metadata (title, URL, category) into each chunk
- Expected capacity within 50MB: thousands of chunks (hundreds of source documents) — sufficient for demo

---

## 7. Ingestion Pipeline (detail)

### 7.1 Flow

```
Source documents (HTML/Markdown/PDF-text) → [n8n or manual] → Blob upload
        → text extraction → cleanup → chunking → embedding (text-embedding-3-small)
        → AI Search index upsert (id = doc_hash-chunk_idx)
```

### 7.2 Implementation

- **Collection**: organize financial institution public pages into Markdown/text in `docs/` → upload to Blob container `raw-docs`
- **Text extraction/chunking**: Python script (`ingest.py`)
  - PDF via `pypdf`/`pdfplumber`, HTML via `BeautifulSoup`
  - Chunking via `langchain-text-splitters` or hand-rolled (paragraph-boundary split)
- **Embedding**: call `text-embedding-3-small` via `openai` SDK (batch of 16)
- **Upload**: `azure-search-documents` SDK `IndexDocumentsBatch`
- **Idempotency**: `id = sha256(doc_content)[:16] + '-' + chunk_idx` → upsert without duplicates on re-run

### 7.3 n8n automation (US-3)

- **Reuse the existing n8n instance (`n8n.techcloudup.com`)** — no new hosting. Only add Azure Blob/HTTP nodes to the existing instance.
- n8n has **no native Azure Storage trigger** — document changes must be detected one of three ways:
  1. **Schedule Trigger** (cron) polling Blob for new/changed blobs → `HTTP Request → Flask /ingest` (simplest)
  2. **Event Grid → Webhook** → n8n: subscribe Blob `BlobCreated` events to an n8n webhook URL (event-driven, near real-time)
  3. **Azure Function (Blob trigger) → Flask /ingest** (most correct event-driven path, no n8n)
- **Start with manual `/ingest` in M1–M3, connect automation in M4** (incremental).

---

## 8. Query / RAG Pipeline (detail)

### 8.1 Flow

```
Question → (1) generate query embedding (text-embedding-3-small)
         → (2) AI Search hybrid search (vector + BM25, RRF, top-k=5)
         → (3) assemble context (chunks + sources)
         → (4) send prompt to GPT-4.1 mini
         → (5) return answer + source list
```

### 8.2 Prompt template

```
System:
You are a member support assistant for a financial institution.
Answer only based on the [Reference Material] below.
If the material has no answer, do not guess; respond:
"We could not confirm the information. For accurate guidance, please
contact the customer center (phone/email)."
Always append the reference numbers used at the end in the format [Sources: 1, 3].

[Reference Material]
[1] (title: ...) (URL: ...) content: ...
[2] ...
[3] ...

User:
Question: {question}
```

### 8.3 Response format

```json
{
  "answer": "Fee refunds are ...",
  "sources": [
    {"title": "Fee schedule", "url": "https://...", "chunk_id": 3}
  ],
  "latency_ms": 1800,
  "model": "gpt-4.1-mini"
}
```

---

## 9. API Spec (Flask)

> The chat UI is served by the Static Web App, so Flask is **API-only**. UI→API calls are handled by registering the SWA domain (`azure-ai-rag.techcloudup.com`) in the CORS allowlist.
>
> ⚠️ **Cost guardrail**: `/ask` consumes OpenAI tokens, so it is protected by a **per-day query cap** (in-memory counter, e.g. 100/day) plus basic **rate limiting** (e.g. 1 req/5s per IP). Optional: `X-API-Key` on `/ask` for stricter control.

| Method | Path | Description | Auth |
|---|---|---|---|
| POST | `/ask` | `{"question": "..."}` → answer+sources | Rate limit + daily cap (optional `X-API-Key`) |
| POST | `/ingest` | Manual re-index (optional: `?doc=...`) | `X-API-Key` header |
| GET | `/health` | Health check (ping to keep F0 alive) | None |

---

## 10. Security (post-review — revised strategy)

> ❗ **F0 constraint**: Azure AI Search F0 cannot authenticate via Managed Identity. So AI Search access uses API keys. However, secret management itself still relies on Managed Identity to preserve the security story.

```
App Service (system-assigned Managed Identity)  ← F1 supports MI too
        │  Allow MI in Key Vault Access Policy
        ▼
Azure Key Vault
   ├─ ai-search-key      (AI Search API key)
   ├─ openai-key         (Azure OpenAI key)
   └─ (optional) storage-conn
        │  Inject via Key Vault Reference in App Settings
        ▼
Flask app (fetches keys at runtime; keys not exposed in code/env)
```

- App Service F1 supports system-assigned MI → can access Key Vault
- Inject keys via `@Microsoft.KeyVault(SecretUri=...)` references in App Settings (no hardcoding)
- AI Search/OpenAI calls are key-based (explicit F0 limitation)
- **Phrase the docs accurately as "Key Vault + Managed Identity (secret access)"** — do not claim "AI Search authenticated via MI"

---

## 11. Cost Model (post-review — corrected)

### 11.1 Always free ($0)

| Service | Free allowance |
|---|---|
| Static Web App (Free) | Custom domain + free TLS — always free |
| AI Search F0 | 50MB, 3 indexes — always free |
| App Service F1 | 60 CPU-min/day — always free |
| Functions (if used) | 1M executions/month — always free |
| Event Grid (if used) | 100K ops/month — always free |

### 11.2 Pay-as-you-go (⚠️ the only ongoing cost = Azure OpenAI)

| Item | Est. monthly cost |
|---|---|
| Embedding `text-embedding-3-small` | A few cents for a few hundred docs |
| Generation `gpt-4.1-mini` (demo traffic, <50/day) | ~$0.5–1 |
| Key Vault | < $0.01 |
| Blob Storage | < $0.01 |

> **Key correction**: "free services keep working after 30 days" applies only to the F0 tier family. **Azure OpenAI is pay-as-you-go (actual usage)**. Budget $1–2/month for a service prototype (minimal demo traffic) and set a budget alert ($2) in Azure Cost Management.

### 11.3 Cost strategy (reuse existing account)

- This is an **existing account (not new)**, so **we do not rely on the $200 new-account credit**. Proceed with free tiers (SWA/F0/F1) + Azure OpenAI pay-as-you-go only.
- **Reuse the existing Azure OpenAI resource (`oai-idp-rl01`, centralus)** → minimize new resources/quota requests.
- (Reference) Azure for Students **$100** requires academic email verification and may not be auto-listed; keep expectations low.

---

## 12. Deployment (IaC + CI/CD)

### 12.1 Terraform resources

```
azurerm_resource_group
azurerm_static_web_app            (sku = "Free")        # chat UI + custom domain
azurerm_search_service            (sku = "free")
azurerm_search_index              (schema definition)
# ── Azure OpenAI: reuse existing resource (oai-idp-rl01), no new cognitive_account ──
data "azurerm_cognitive_account" "existing_oai"   (centralus)
azurerm_cognitive_deployment "text_embedding"     # text-embedding-3-small (new deployment — quota request)
# gpt-4.1-mini reuses the existing deployment (terraform import)
azurerm_linux_web_app             (sku = F1)            # Flask API
azurerm_key_vault + access_policy (allow get for App Service MI)
azurerm_key_vault_secret          (ai-search-key, openai-key)
azurerm_storage_account + container (raw-docs)
azurerm_application_insights      (free 5GB/month)
```

> ⚠️ Manually inject the Azure OpenAI key from the existing resource (`oai-idp-rl01`) into Key Vault (hard to automate) → document as a one-time manual step in README

### 12.2 GitHub Actions pipeline

1. `terraform plan` (on PR)
2. `terraform apply` (on merge to main)
3. Build chat UI → deploy to Static Web App (`azure/static-web-apps-deploy`)
4. Build Flask app → deploy to App Service (`azure/webapps-deploy`)

### 12.3 DNS / Custom domain (Cloudflare)

- `techcloudup.com` is hosted on **Cloudflare**. Register the `azure-ai-rag` subdomain in Cloudflare DNS to point at the dashboard (chat UI).
- **Decision (confirmed)**: the chat UI is served by **Azure Static Web App (Free)**. The SWA free tier supports custom domains + free TLS, which sidesteps the App Service F1 custom-domain limitation. The Flask `/ask` API stays on F1 (no custom domain needed); UI→API is via CORS.
- Cloudflare DNS records (proxied):
  - `CNAME azure-ai-rag → <swa-host>.azurestaticapps.net` (SWA default domain)
  - One ownership-verification record (`TXT`/`CNAME`) required by SWA
- ⚠️ App Service F1 does not support custom domains → do not bind a custom domain to F1. (B1 upgrade remains an optional alternative.)

---

## 13. Monitoring / Operations (Runbook, SLO)

| Item | Detail |
|---|---|
| Logging/tracing | Application Insights (free 5GB/month) |
| Metrics | Query latency, answer failure rate, token usage |
| SLO (demo) | Availability 95%, response p95 < 5s (warm path; cold start excluded — F1 has no Always On) |
| Keep-warm | `/health` pinged by a free uptime monitor (or GitHub Actions cron) every ~5 min to keep F1 warm + F0 alive |
| Runbook | Document re-index procedure, key rotation, quota increase request procedure |

> Satisfy "operational documentation / Runbook / SLO" requirements with README + runbook.md.

---

## 14. Milestones

| Phase | Deliverable | Verification |
|---|---|---|
| M1 Infrastructure + quota gate | Terraform + Key Vault + GitHub Actions; **embedding model (`text-embedding-3-small`) approved on `oai-idp-rl01`** | Clean `terraform apply`; embedding deployable (blocker — stop if denied) |
| M2 Data | 30+ FAQ docs in `docs/`, ingestion script, index | Docs visible in AI Search portal; **F0 vector index provisioning succeeds** (fall back to keyword-only BM25 if it hangs) |
| M3 RAG API | Flask `/ask` + prompt + hybrid search | 20-question eval set accuracy ≥ 80% |
| M4 Automation | n8n sync workflow | Doc added → auto-reflected confirmed |
| M5 Deploy/docs | Chat UI, README (architecture/cost/security), runbook | Domain live |

---

## 15. Acceptance Criteria

- [ ] 20-question FAQ eval set accuracy ≥ 80%, answers include source URLs
- [ ] p95 response < 5s
- [ ] No API keys exposed in commits/code/env (use Key Vault Reference)
- [ ] Infrastructure reproducible with `terraform apply` alone
- [ ] Free tiers (SWA/F0/F1) operate normally (the only cost = Azure OpenAI pay-as-you-go)
- [ ] README includes architecture diagram + free-tier notes + security description

---

## 16. Risks & Mitigations

| Risk | Impact | Mitigation |
|---|---|---|
| F0 vector index provisioning hangs (shared infra, no dedicated compute) | Hybrid RAG blocked | M2 gate: validate vector index early; fall back to keyword-only BM25 on F0, or reopen budget for Basic (~$66–73/mo) |
| New embedding model (text-embedding-3-small) deployment quota | Cannot index | M1 gate: request deployment on `oai-idp-rl01` before building the pipeline (gpt-4.1-mini already deployed) |
| Azure OpenAI pay-as-you-go cost overrun | Budget overrun | gpt-4.1-mini (cheapest, already deployed) + $2 budget alert + daily query cap on `/ask` |
| AI Search F0 deleted on inactivity | Demo outage | Periodic `/health` ping (GitHub Actions cron) |
| F0 no MI → key auth | Weakened security story | Offset with §10 strategy (app MI → Key Vault access) |
| App Service F1 cold start (no Always On) | First request after idle > 5s | Keep-warm ping every ~5 min (uptime monitor/cron); SLO scoped to warm path |
| Model availability by region | Deployment delay | Verify Azure OpenAI model availability before deploy (existing resource: centralus) |

---

## 17. Project Statement (Service Prototype)

> Designed and deployed a **RAG-based member support knowledge retrieval system on Azure**, implementing **hybrid retrieval (vector + BM25 with RRF fusion)** on Azure AI Search and context-grounded answer generation with Azure OpenAI, packaged as **reproducible IaC (Terraform/GitHub Actions)** with **Key Vault-managed secrets accessed via Managed Identity** and automated index synchronization via n8n.

### 17.1 Capability mapping (prototype → required capability)

| Required capability | Mapping |
|---|---|
| AI/LLM integration patterns | Azure OpenAI (embedding+generation) + AI Search integration |
| Knowledge retrieval / member support | Hybrid RAG + citation-grounded answers |
| Operational handoff | Terraform + GitHub Actions + Runbook + SLO |
| Security/compliance | Key Vault + Managed Identity (secret access) + no key hardcoding |

---

## 18. Future Extensions (when paid budget allows)

1. **Upgrade AI Search to Basic** → Managed Identity auth + Semantic Ranker
2. Multi-turn conversation + conversation history
3. Integrate with Project 1 (IDP): scanned document OCR → index into this pipeline
4. Evaluation automation (RAGAS etc.) for accuracy regression testing
