# Day-0 Operator Checklist (Minimal Path)

Status: Active
Owner: nova release architecture
Last reviewed: 2026-03-02

## Purpose

Run first-time Nova CI/CD provisioning and release promotion using the shortest
safe operator path.

## Prerequisites

1. AWS CLI v2 authenticated.
2. GitHub CLI authenticated.
3. Repository admin access to `BjornMelin/nova`.
4. Required environment values prepared.

## Minimal execution path

1. From repo root, export required vars and run:

```bash
./scripts/release/day-0-operator-command-pack.sh
```

2. Validate stack outputs:

```bash
aws cloudformation describe-stacks --region "${AWS_REGION}" --stack-name "${PROJECT}-${APPLICATION}-nova-iam-roles" --query 'Stacks[0].Outputs'
aws cloudformation describe-stacks --region "${AWS_REGION}" --stack-name "${PROJECT}-${APPLICATION}-nova-ci-cd" --query 'Stacks[0].Outputs'
```

3. Verify GitHub secret/variable wiring:

```bash
gh secret list --repo "${GITHUB_OWNER}/${GITHUB_REPO}"
gh variable list --repo "${GITHUB_OWNER}/${GITHUB_REPO}"
```

4. Confirm CodeConnections status is `AVAILABLE`:

```bash
aws codeconnections get-connection --region "${AWS_REGION}" --connection-arn "${CONNECTION_ARN}" --query 'Connection.ConnectionStatus' --output text
```

5. Trigger and verify release workflows/pipeline progression.

## Acceptance checks

1. Release signing and workflow auth are valid.
2. Pipeline completes Dev -> ManualApproval -> Prod in order.
3. `IMAGE_DIGEST` continuity is preserved Dev to Prod.
4. Evidence links are added to release docs/plan artifacts.

## References

- [documentation-index.md](documentation-index.md)
- [governance-lock-runbook.md](governance-lock-runbook.md)
- [troubleshooting-and-break-glass-guide.md](troubleshooting-and-break-glass-guide.md)
