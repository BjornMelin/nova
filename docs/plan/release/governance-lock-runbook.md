# Governance Lock Runbook (Final-State Minimal)

Status: Active  
Owner: `@BjornMelin`

## Purpose

Apply and verify the final governance lock on `main` with minimal operator steps
and auditable outputs.

## Preconditions

1. `main` is green on required checks.
2. `.github/CODEOWNERS` is merged.
3. Operator has `gh` auth to target repo.

## Required checks

- `runtime-security-reliability-gates`
- `quality-gates`
- `dash-conformance`
- `shiny-conformance`
- `typescript-conformance`

## Operator flow

1. Set scope.

```bash
OWNER="BjornMelin"
REPO="nova"
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

4. If drift exists, manually apply the reviewed payload in
   `branch-protection-required-checks.md`.

5. Capture evidence.

```bash
EVIDENCE_DIR="docs/plan/release/evidence/governance/$(date -u +%Y%m%dT%H%M%SZ)"
mkdir -p "${EVIDENCE_DIR}"

gh api repos/${OWNER}/${REPO}/contents/.github/CODEOWNERS --jq '{path: .path, sha: .sha}' > "${EVIDENCE_DIR}/codeowners-snapshot.json"
gh api repos/${OWNER}/${REPO}/branches/main/protection > "${EVIDENCE_DIR}/branch-protection.json"
gh api repos/${OWNER}/${REPO}/branches/main/protection --jq '.required_status_checks.contexts' > "${EVIDENCE_DIR}/required-check-contexts.json"
sha256sum "${EVIDENCE_DIR}"/* > "${EVIDENCE_DIR}/SHA256SUMS"
```

## Acceptance

- Required checks match lock target.
- `require_code_owner_reviews=true`.
- `required_conversation_resolution=true`.
- Evidence directory recorded in release artifacts.
