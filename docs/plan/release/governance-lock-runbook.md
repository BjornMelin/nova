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

### Step 1: Verify CODEOWNERS from default branch

```bash
gh api repos/${OWNER}/${REPO}/contents/.github/CODEOWNERS --jq '.path'
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
