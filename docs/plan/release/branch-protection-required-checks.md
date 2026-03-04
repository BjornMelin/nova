# Branch Protection and Required Checks (PR-14 Governance Lock)

This document defines the final governance lock configuration for the protected
`main` branch, including required status checks and owner review policy.

## Target branch

- `main`

## Required status checks

Configure the following checks as **required** for `main`.

From workflow `Nova CI` (`.github/workflows/ci.yml`):

- `runtime-security-reliability-gates`
- `quality-gates`

From workflow `Conformance Clients` (`.github/workflows/conformance-clients.yml`):

- `dash-conformance`
- `shiny-conformance`
- `typescript-conformance`

From workflow `CFN Contract Validate` (`.github/workflows/cfn-contract-validate.yml`):

- `cfn-and-contracts`

## Required branch protection rules

Enable all of the following on `main`:

1. **Require a pull request before merging**
2. **Require approvals** (recommended: at least 1)
3. **Require review from Code Owners**
4. **Require status checks to pass before merging**
5. **Require branches to be up to date before merging**
6. **Require conversation resolution before merging**
7. **Do not allow bypassing the above settings** except designated admins (if your org policy allows it)

## CODEOWNERS governance scope

CODEOWNERS must explicitly cover these authority domains:

- architecture docs (`docs/architecture/**`)
- infrastructure (`infra/**`)
- contracts (`contracts/**`, `packages/contracts/**`, `specs/**` where present)
- workflows (`.github/workflows/**`)

The canonical owner mapping is defined in `.github/CODEOWNERS`.

## GitHub CLI verification snippets (read-only)

```bash
# Show branch protection JSON for main
gh api repos/${OWNER}/${REPO}/branches/main/protection

# Show currently required status checks context names
gh api repos/${OWNER}/${REPO}/branches/main/protection \
  --jq '.required_status_checks.contexts'

# Validate CODEOWNERS file exists at default location
gh api repos/${OWNER}/${REPO}/contents/.github/CODEOWNERS --jq '.path'
```

## Optional apply snippet (manual execution only)

Use this only after review/approval. This repository does not execute this step
in automation.

```bash
# Example: apply required checks + core protections to main.
# Replace OWNER/REPO and review payload before running.
gh api \
  --method PUT \
  repos/${OWNER}/${REPO}/branches/main/protection \
  --input - <<'JSON'
{
  "required_status_checks": {
    "strict": true,
    "contexts": [
      "runtime-security-reliability-gates",
      "quality-gates",
      "dash-conformance",
      "shiny-conformance",
      "typescript-conformance",
      "cfn-and-contracts"
    ]
  },
  "enforce_admins": true,
  "required_pull_request_reviews": {
    "dismiss_stale_reviews": true,
    "require_code_owner_reviews": true,
    "required_approving_review_count": 1,
    "require_last_push_approval": false
  },
  "restrictions": null,
  "required_linear_history": false,
  "allow_force_pushes": false,
  "allow_deletions": false,
  "block_creations": false,
  "required_conversation_resolution": true,
  "lock_branch": false,
  "allow_fork_syncing": true
}
JSON
```

## Scope guardrails

TypeScript conformance lane scope remains intentionally minimal:

- contract fixture typing
- SDK/client envelope verification
- auth verify + queue/transfer contract parity

No broad app feature tests are part of this required check set.
