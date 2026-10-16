# Deployment Runbook — Azure RAG Member Support

> Day-0 setup through day-2 operations. Complements `BUILD_CHECKLIST.md`.

## Prerequisites

- `az` CLI logged in (`az account show` → `Azure subscription 1`)
- `terraform` ≥ 1.6 installed
- `gh` CLI + repo with GitHub Actions enabled
- Cloudflare access to `techcloudup.com` DNS

## Day-0 one-time setup

1. Bootstrap remote state (manual, once):
   - `az group create -n ai-rag-tfstate -l centralus`
   - Create storage account `stragstaterl01` + container `tfstate`
2. `terraform init` (pulls providers + configures backend)
3. ⛔ **Embedding quota gate**: request `text-embedding-3-small` on `oai-idp-rl01` (centralus). Denied → switch to keyword-only plan.

## Standard deploy

```bash
cd terraform
terraform plan    # review the diff
terraform apply   # after approval
```

- UI deploys via GitHub Actions (`azure/static-web-apps-deploy`).
- API deploys as a **pre-built-deps zip** (no on-host `pip install`, avoids the F1 quota):

```bash
pip install --platform manylinux2014_x86_64 --implementation cp --python-version 3.12 \
  --only-binary=:all: --target /tmp/deps -r api/requirements.txt
# bundle api/*.py + data/ + deps/ → zip
az webapp deployment source config-zip -g ai-rag-prototype -n web-rag-rl01 --src /tmp/app.zip
```

## One-time manual steps (not cleanly automatable)

1. **OpenAI key → Key Vault**: copy the key from `oai-idp-rl01`, then
   `az keyvault secret set --name openai-key --vault-name kv-rag-rl01 --value <key>`
2. **AI Search key → Key Vault**: same pattern with `ai-search-key`.
3. Grant App Service MI `get` on Key Vault (access policy) — created by Terraform, verify once.

## Rollback

- **Infra**: `git revert` the offending commit → `terraform plan` → `apply` (Terraform converges back).
- **App**: redeploy the previous commit via GitHub Actions (UI) / `config-zip` (API).

## Teardown

- `terraform destroy` removes all managed resources.
- ⚠️ Does NOT touch `oai-idp-rl01` (it's a `data` source, not managed) — intentional.

## Disaster recovery

- State lives in Blob (`ai-rag-tfstate` / `stragstaterl01`). Fresh machine: clone repo → `terraform init` → `terraform plan` (should report "no changes").

## Quota / limit changes

- AI Search F0: 50MB / 3 indexes / 1 free per subscription.
- App Service F1: 60 CPU-min/day.
- OpenAI quota changes require an Azure support request (ops notes in `runbook.md`).
