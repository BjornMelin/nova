# AWS Secrets Provisioning Guide

Status: Active
Owner: nova release architecture
Last reviewed: 2026-02-24

## Purpose

Provision and rotate the release signing key in AWS Secrets Manager for the
`Nova Release Apply` workflow.

## Required secret contract

The release workflow expects JSON with these keys:

- `private_key`
- `public_key`
- `signer_name`
- `signer_email`

Reference workflow:
`/home/bjorn/repos/work/infra-stack/nova/.github/workflows/release-apply.yml`

## Prerequisites

1. AWS CLI v2 configured for target account.
2. IAM permissions for `secretsmanager:CreateSecret`,
   `secretsmanager:PutSecretValue`, `secretsmanager:GetSecretValue`.
3. Local OpenSSH `ssh-keygen` available.

## Inputs

Use these placeholders:

- `${AWS_REGION}` example: `us-east-1`
- `${SECRET_NAME}` example: `nova/release/signing-key`
- `${SIGNER_NAME}` example: `Nova Release Bot`
- `${SIGNER_EMAIL}` example: `nova-release@example.com`

## Step-by-step commands

1. Generate SSH signing key pair.

    ```bash
    ssh-keygen -t ed25519 -C "${SIGNER_EMAIL}" -N "" -f /tmp/nova-release-signing
    ```

2. Build secret payload file.

    ```bash
    cat >/tmp/nova-release-signing-secret.json <<JSON
    {
      "private_key": $(jq -Rs . </tmp/nova-release-signing),
      "public_key": $(jq -Rs . </tmp/nova-release-signing.pub),
      "signer_name": "${SIGNER_NAME}",
      "signer_email": "${SIGNER_EMAIL}"
    }
    JSON
    ```

3. Create secret.

    ```bash
    aws secretsmanager create-secret \
      --region "${AWS_REGION}" \
      --name "${SECRET_NAME}" \
      --description "Nova release SSH signing key" \
      --secret-string file:///tmp/nova-release-signing-secret.json
    ```

4. If secret already exists, rotate value.

    ```bash
    aws secretsmanager put-secret-value \
      --region "${AWS_REGION}" \
      --secret-id "${SECRET_NAME}" \
      --secret-string file:///tmp/nova-release-signing-secret.json
    ```

5. Verify payload schema at rest.

    ```bash
    aws secretsmanager get-secret-value \
      --region "${AWS_REGION}" \
      --secret-id "${SECRET_NAME}" \
      --query SecretString \
      --output text | jq '{private_key, public_key, signer_name, signer_email}'
    ```

## Acceptance checks

1. `get-secret-value` returns JSON with all four required keys.
2. `private_key` contains an OpenSSH private key block.
3. `public_key` begins with `ssh-ed25519`.

## Security notes

1. Never commit generated private keys.
2. Restrict read access to the dedicated GitHub OIDC release role.
3. Rotate key immediately after any suspected exposure.

## References

- Secrets Manager create-secret API:
  <https://docs.aws.amazon.com/cli/latest/reference/secretsmanager/create-secret.html>
- Secrets Manager put-secret-value API:
  <https://docs.aws.amazon.com/cli/latest/reference/secretsmanager/put-secret-value.html>
- Secrets Manager get-secret-value API:
  <https://docs.aws.amazon.com/cli/latest/reference/secretsmanager/get-secret-value.html>
- GitHub commit signature verification:
  <https://docs.github.com/en/authentication/managing-commit-signature-verification/about-commit-signature-verification>
