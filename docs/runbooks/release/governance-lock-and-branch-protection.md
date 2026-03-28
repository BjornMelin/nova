# Governance lock and branch protection (`main`)

Status: Active
Owner: nova release architecture
Last reviewed: 2026-03-24

## Purpose

Define the policy for protected `main` and the operator runbook to verify or
apply the lock with auditable outputs. This repo currently uses a repository
branch ruleset, not classic branch protection.

## Part A -- Policy

### Target branch

- `main`

### Current hosted policy model

As of 2026-03-24:

- repo visibility is `PRIVATE`
- classic branch protection for `main` returns `404 Branch not protected`
- the active hosted policy surface is repository ruleset `13362504`

Apply required checks through the active ruleset. Do not rely on classic branch
protection for this repository.

### Required status checks

Configure the following leaf jobs as required for `main`.

From workflow `Nova CI` (`.github/workflows/ci.yml`):

- `quality-gates` (Python 3.13 primary lint/type/generation lane)
- `pytest-runtime-gates`
- `pytest-primary`
- `pytest-generated-smoke`
- `pytest-compatibility-3.11`
- `pytest-compatibility-3.12`
- `python-compatibility` (build/packaging compatibility lane)
- `generated-clients`
- `dash-conformance`
- `shiny-conformance`
- `typescript-conformance`

From workflow `CFN Contract Validate` (`.github/workflows/cfn-contract-validate.yml`):

- `cfn-and-contracts`

Do not require:

- `classify-changes`
- `typescript-core-packages`
- `typescript-sdk-smoke`

These are internal orchestration/build jobs, not the hosted branch-protection
surface.

### Required review and merge rules

Enable all of the following in the active ruleset for `main`:

1. Require a pull request before merging.
2. Require 1 approving review.
3. Require Code Owner review.
4. Require status checks to pass before merging.
5. Require branches to be up to date before merging.
6. Require review-thread resolution before merging.
7. Disallow non-fast-forward updates and branch deletion.

### CODEOWNERS governance scope

CODEOWNERS must explicitly cover these authority domains:

- architecture docs (`docs/architecture/**`)
- infrastructure (`infra/**`)
- contracts (`contracts/**`, `packages/contracts/**`, `specs/**` where present)
- workflows (`.github/workflows/**`)

The canonical owner mapping is defined in `.github/CODEOWNERS`.

### Scope guardrails

Required-check workflows must stay always-triggered for protected-branch PRs.
Minute reduction is handled inside those workflows with classifier jobs and
job-level `if:` guards, not top-level workflow `paths` filters.

TypeScript conformance scope remains intentionally minimal and validates the
release-grade CodeArtifact package shape:

- contract fixture typing
- SDK/client envelope verification
- auth verify plus queue/transfer contract parity
- subpath/export boundary enforcement

No broad app feature tests are part of this required check set.

### GitHub CLI verification snippets (read-only)

```bash
# Show all active rulesets
 gh api repos/${OWNER}/${REPO}/rulesets

# Show the active main ruleset in full
 gh api repos/${OWNER}/${REPO}/rulesets/${RULESET_ID}

# Validate CODEOWNERS file exists at default location
 gh api repos/${OWNER}/${REPO}/contents/.github/CODEOWNERS --jq '.path'
```

### Optional apply snippet (manual execution only)

Use this only after review and after the workflow branch that introduces the
new check surface has merged to `main`.

```bash
gh api \
  --method PUT \
  repos/${OWNER}/${REPO}/rulesets/${RULESET_ID} \
  --input - <<'JSON'
{
  "name": "main",
  "target": "branch",
  "enforcement": "active",
  "conditions": {
    "ref_name": {
      "include": ["~DEFAULT_BRANCH"],
      "exclude": []
    }
  },
  "rules": [
    { "type": "deletion" },
    { "type": "non_fast_forward" },
    {
      "type": "pull_request",
      "parameters": {
        "required_approving_review_count": 1,
        "dismiss_stale_reviews_on_push": false,
        "required_reviewers": [],
        "require_code_owner_review": true,
        "require_last_push_approval": false,
        "required_review_thread_resolution": true,
        "allowed_merge_methods": ["merge", "squash", "rebase"]
      }
    },
    {
      "type": "required_status_checks",
      "parameters": {
        "strict_required_status_checks_policy": true,
        "required_status_checks": [
          { "context": "quality-gates" },
          { "context": "pytest-runtime-gates" },
          { "context": "pytest-primary" },
          { "context": "pytest-generated-smoke" },
          { "context": "pytest-compatibility-3.11" },
          { "context": "pytest-compatibility-3.12" },
          { "context": "python-compatibility" },
          { "context": "generated-clients" },
          { "context": "dash-conformance" },
          { "context": "shiny-conformance" },
          { "context": "typescript-conformance" },
          { "context": "cfn-and-contracts" }
        ]
      }
    }
  ]
}
JSON
```

If you already use code scanning, code quality, or Copilot review rules in the
same ruleset, preserve them when updating the payload.

## Part B -- Operator verification flow

### Preconditions

1. `main` is green on the target required checks.
2. `.github/CODEOWNERS` is merged.
3. Operator has `gh` auth to the target repo.
4. The unified `Nova CI` workflow change is already merged to `main`.

### Operator flow

1. Set scope.

```bash
OWNER="${GITHUB_OWNER:?Set GITHUB_OWNER (e.g., BjornMelin)}"
REPO="${GITHUB_REPO:?Set GITHUB_REPO (e.g., nova)}"
RULESET_ID="${RULESET_ID:?Set RULESET_ID (current repo main ruleset id)}"
```

2. Verify CODEOWNERS snapshot.

   ```bash
   gh api repos/${OWNER}/${REPO}/contents/.github/CODEOWNERS --jq '{path: .path, sha: .sha}'
   gh api repos/${OWNER}/${REPO}/contents/.github/CODEOWNERS --jq '.content | @base64d' | sha256sum
   ```

3. Verify the active ruleset and current required checks.

   ```bash
   gh api repos/${OWNER}/${REPO}/rulesets
   gh api repos/${OWNER}/${REPO}/rulesets/${RULESET_ID}
   ```

4. If drift exists, reconcile Part A through the GitHub UI or the optional
   apply snippet after review.

5. Capture evidence.

   ```bash
   EVIDENCE_DIR="${TMPDIR:-/tmp}/nova-governance-evidence/governance/$(date -u +%Y%m%dT%H%M%SZ)"
   export EVIDENCE_DIR
   mkdir -p "${EVIDENCE_DIR}"

   gh api repos/${OWNER}/${REPO}/contents/.github/CODEOWNERS --jq '{path: .path, sha: .sha}' > "${EVIDENCE_DIR}/codeowners-snapshot.json"
   gh api repos/${OWNER}/${REPO}/rulesets > "${EVIDENCE_DIR}/rulesets.json"
   gh api repos/${OWNER}/${REPO}/rulesets/${RULESET_ID} > "${EVIDENCE_DIR}/main-ruleset.json"
   sha256sum "${EVIDENCE_DIR}"/* > "${EVIDENCE_DIR}/SHA256SUMS"
   ```
```

Do not commit `${EVIDENCE_DIR}`; it is intentionally outside the repository
path.

### Acceptance

- Required checks match Part A.
- `require_code_owner_review=true`.
- `required_review_thread_resolution=true`.
- Evidence directory recorded in release artifacts or operator evidence.
