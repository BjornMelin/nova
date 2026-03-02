# Governance Lock Runbook (PR-14)

Status: Finalization artifact for branch protection and CODEOWNERS lock.
Owner: `@BjornMelin`

## Purpose

Provide an auditable, repeatable runbook for final governance lock on `main`
after Nova consolidation. This runbook is evidence-oriented and safe by default:
verification first, manual apply second.

## Preconditions

1. `main` is green on all required checks.
2. `.github/CODEOWNERS` is merged and covers architecture/infra/contracts/workflows.
3. Repository admins are aligned on bypass policy.

## Required checks set (lock target)

- `runtime-security-reliability-gates`
- `quality-gates`
- `dash-conformance`
- `shiny-conformance`
- `typescript-conformance`

Reference: `docs/plan/release/branch-protection-required-checks.md`

## Final lock procedure

### Step 1: Set repository scope and verify CODEOWNERS snapshot

```bash
OWNER="BjornMelin"
REPO="nova"

gh api repos/${OWNER}/${REPO}/contents/.github/CODEOWNERS --jq '{path: .path, sha: .sha}'
gh api repos/${OWNER}/${REPO}/contents/.github/CODEOWNERS --jq '.content | @base64d' \
  | sha256sum
```

### Step 2: Verify current branch protection state

```bash
gh api repos/${OWNER}/${REPO}/branches/main/protection
```

### Step 3: Compare required check contexts

```bash
gh api repos/${OWNER}/${REPO}/branches/main/protection \
  --jq '.required_status_checks.contexts'
```

### Step 4: Apply/update protections (manual, reviewed)

Use the payload in:
`docs/plan/release/branch-protection-required-checks.md`

Do not run this from unattended automation for governance finalization.

### Step 5: Capture audit evidence

Store command outputs and screenshots/links in your release evidence location.

## Audit evidence checklist

- [ ] Link to PR merging `.github/CODEOWNERS`
- [ ] Branch protection JSON export timestamped
- [ ] Required checks list captured and matches lock target
- [ ] Confirmation `require_code_owner_reviews=true`
- [ ] Confirmation `required_conversation_resolution=true`
- [ ] Confirmation strict status checks/up-to-date branch enabled
- [ ] Reviewer sign-off (operator + repo owner)


## Evidence scaffold and export capture

Use a timestamped evidence directory under repo docs. Example:

```bash
EVIDENCE_DIR="docs/plan/release/evidence/governance/$(date -u +%Y%m%dT%H%M%SZ)"
mkdir -p "${EVIDENCE_DIR}"
```

Capture immutable governance snapshots:

```bash
gh api repos/${OWNER}/${REPO}/contents/.github/CODEOWNERS   --jq '{path: .path, sha: .sha}'   > "${EVIDENCE_DIR}/codeowners-snapshot.json"

gh api repos/${OWNER}/${REPO}/contents/.github/CODEOWNERS   --jq '.content | @base64d'   > "${EVIDENCE_DIR}/CODEOWNERS"

sha256sum "${EVIDENCE_DIR}/CODEOWNERS"   > "${EVIDENCE_DIR}/codeowners-content.sha256"

gh api repos/${OWNER}/${REPO}/branches/main/protection   > "${EVIDENCE_DIR}/branch-protection.json"

gh api repos/${OWNER}/${REPO}/branches/main/protection   --jq '.required_status_checks.contexts'   > "${EVIDENCE_DIR}/required-check-contexts.json"
```

Record SHA256 hashes for evidence payload integrity:

```bash
sha256sum "${EVIDENCE_DIR}"/* > "${EVIDENCE_DIR}/SHA256SUMS"
```

Then reference the evidence directory path in:

- `FINAL-PLAN.md`
- `docs/plan/PLAN.md`
- `docs/plan/release/NONPROD-LIVE-VALIDATION-RUNBOOK.md`

## Suggested evidence record template

```text
Date/Time (UTC):
Operator:
Repo:
Branch:
Protection endpoint snapshot:
Required checks observed:
CODEOWNERS path verified:
Deviations/exceptions:
Final sign-off:
```


## Latest execution record (2026-03-02)

Evidence directories captured:

- `docs/plan/release/evidence/governance/20260302T231154Z`
- `docs/plan/release/evidence/governance/20260302T231223Z`

Observed constraints:

- `GET /repos/{owner}/{repo}/branches/main/protection` returned `403` with
  `"Upgrade to GitHub Pro or make this repository public to enable this feature."`
- `required_status_checks.contexts` could not be exported via REST under current
  repository plan constraints.

Fallback captured:

- immutable `.github/CODEOWNERS` snapshot + content hash (`SHA256SUMS`)
- `main` check-runs snapshot (`main-check-runs*.json`) for current required-check
  evidence candidates

Required manual follow-up:

- capture branch protection and required-check policy evidence via GitHub UI
  screenshots/export in the same timestamped evidence folder
- complete reviewer sign-off checklist
