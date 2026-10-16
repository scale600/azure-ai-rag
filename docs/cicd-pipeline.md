# CI/CD Pipeline — Azure RAG Member Support

> GitHub Actions. Two workflows: infra + app deploy. Auth via OIDC (no raw secrets in the repo).

## Auth (GitHub ↔ Azure)

- Use **OpenID Connect (OIDC)** federation — never store a service-principal secret.
- Azure side: App registration + federated credential scoped to this repo.
- GitHub secrets (OIDC identifiers only, non-sensitive):
  - `AZURE_CLIENT_ID`
  - `AZURE_TENANT_ID`
  - `AZURE_SUBSCRIPTION_ID`

## Workflow 1 — `terraform` (`.github/workflows/terraform.yml`)

```yaml
on:
  pull_request: {}          # plan only
  push:
    branches: [main]        # apply
```

1. `azure/login` (OIDC)
2. `hashicorp/setup-terraform`
3. PR → `terraform plan`, comment the diff on the PR
4. main → `terraform apply`

- Apply runs only on main; `-auto-approve` is acceptable there because the PR plan is the review gate.

## Workflow 2 — `deploy` (`.github/workflows/deploy.yml`)

```yaml
on:
  push:
    branches: [main]
```

1. Build chat UI → `azure/static-web-apps-deploy` (Static Web App)
2. Bundle Flask app with pre-built deps → `az webapp deployment source config-zip` (no on-host build)

- UI and API are independent → run as parallel jobs.
- The API is NOT built on the host: deps are `pip install`-ed into `deps/` on the runner and
  shipped in the zip, so deployment does not consume the F1 60 CPU-min/day quota.

## Branch protection

- `main` protected: PR required, and the `terraform plan` check must pass before merge.

## Environment strategy

- Single environment (`dev`) — service prototype, no prod/staging split.
- If a second environment is ever needed: use Terraform workspaces + `envs/` tfvars, never duplicate code.
