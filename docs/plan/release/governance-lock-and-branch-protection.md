# Governance lock and branch protection (`main`)

Status: Active
Owner: nova release architecture
Last reviewed: 2026-03-19

## Purpose

Define the **policy** for protected `main` (required checks and branch rules)
and the **operator runbook** to verify or apply the lock with auditable
outputs. Replaces separate branch-protection and governance-lock-only docs.

## Part A — Policy (PR-14 governance lock)

### Target branch

- `main`

### Required status checks

Configure the following checks as **required** for `main`.

From workflow `Nova CI` (`.github/workflows/ci.yml`):

- `classify-changes`
- `runtime-security-reliability-gates`
- `quality-gates`

From workflow `Conformance Clients` (`.github/workflows/conformance-clients.yml`):

- `dash-conformance`
- `shiny-conformance`
- `typescript-conformance` (release-grade TypeScript SDK conformance; required
  check name remains stable)

From workflow `CFN Contract Validate` (`.github/workflows/cfn-contract-validate.yml`):

- `cfn-and-contracts`

### Required branch protection rules

Enable all of the following on `main`:

1. **Require a pull request before merging**
2. **Require approvals** (recommended: at least 1)
3. **Require review from Code Owners**
4. **Require status checks to pass before merging**
5. **Require branches to be up to date before merging**
6. **Require conversation resolution before merging**
7. **Do not allow bypassing the above settings** except designated admins (if your org policy allows it)

### CODEOWNERS governance scope

CODEOWNERS must explicitly cover these authority domains:

- architecture docs (`docs/architecture/**`)
- infrastructure (`infra/**`)
- contracts (`contracts/**`, `packages/contracts/**`, `specs/**` where present)
- workflows (`.github/workflows/**`)

The canonical owner mapping is defined in `.github/CODEOWNERS`.

### GitHub CLI verification snippets (read-only)

```bash
# Show branch protection JSON for main
gh api repos/${OWNER}/${REPO}/branches/main/protection

# Show currently required status checks context names
gh api repos/${OWNER}/${REPO}/branches/main/protection \
  --jq '.required_status_checks.contexts'

# Validate CODEOWNERS file exists at default location
gh api repos/${OWNER}/${REPO}/contents/.github/CODEOWNERS --jq '.path'
```

### Optional apply snippet (manual execution only)

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
      "classify-changes",
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

### Scope guardrails

TypeScript conformance lane scope remains intentionally minimal and now
verifies the release-grade CodeArtifact package shape:

- contract fixture typing
- SDK/client envelope verification
- auth verify + queue/transfer contract parity
- subpath/export boundary enforcement

Required-check workflows must stay always-triggered for protected-branch PRs.
Minute reduction is handled inside those workflows with classifier jobs and
job-level `if:` guards, not top-level workflow `paths` filters.

No broad app feature tests are part of this required check set.

## Part B — Operator verification flow

### Preconditions

1. `main` is green on required checks.
2. `.github/CODEOWNERS` is merged.
3. Operator has `gh` auth to target repo.

### Operator flow

1. Set scope.

```bash
OWNER="${GITHUB_OWNER:?Set GITHUB_OWNER (e.g., BjornMelin)}"
REPO="${GITHUB_REPO:?Set GITHUB_REPO (e.g., nova)}"
```

2. Verify CODEOWNERS snapshot.

```bash
gh api repos/${OWNER}/${REPO}/contents/.github/CODEOWNERS --jq '{path: .path, sha: .sha}'
gh api repos/${OWNER}/${REPO}/contents/.github/CODEOWNERS --jq '.content | @base64d' | sha256sum
```

3. Verify protection + required check contexts.

```bash
gh api repos/${OWNER}/${REPO}/branches/main/protection
gh api repos/${OWNER}/${REPO}/branches/main/protection --jq '.required_status_checks.contexts'
```

4. If drift exists, reconcile **Part A** (required checks and rules) via GitHub
   UI or the optional apply snippet after review.

5. Capture evidence.

```bash
EVIDENCE_DIR="${TMPDIR:-/tmp}/nova-governance-evidence/governance/$(date -u +%Y%m%dT%H%M%SZ)"
export EVIDENCE_DIR
mkdir -p "${EVIDENCE_DIR}"

gh api repos/${OWNER}/${REPO}/contents/.github/CODEOWNERS --jq '{path: .path, sha: .sha}' > "${EVIDENCE_DIR}/codeowners-snapshot.json"
gh api repos/${OWNER}/${REPO}/branches/main/protection > "${EVIDENCE_DIR}/branch-protection.json"
gh api repos/${OWNER}/${REPO}/branches/main/protection --jq '.required_status_checks.contexts' > "${EVIDENCE_DIR}/required-check-contexts.json"
sha256sum "${EVIDENCE_DIR}"/* > "${EVIDENCE_DIR}/SHA256SUMS"
```

Do not commit `${EVIDENCE_DIR}`; it is intentionally outside the repository path.

### Acceptance

- Required checks match **Part A** (including `classify-changes` and
  `cfn-and-contracts`).
- `require_code_owner_reviews=true`.
- `required_conversation_resolution=true`.
- Evidence directory recorded in release artifacts.
