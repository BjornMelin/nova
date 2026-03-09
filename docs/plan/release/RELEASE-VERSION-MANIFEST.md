# Release Version Manifest

Date: 2026-03-03T20:16:13+00:00
Status: Active
Schema: 1.0

## Release Metadata
- `base_commit`: `249ff2b6b0f9278f4866a063808860863cc3e903`
- `head_commit`: `02f050b42bcfca2e1a41bc2eef6263a514985593`
- `first_release`: `False`
- `global_bump`: `none`

## changed-units.json Schema

```json
{
  "schema_version": "1.0",
  "base_commit": "<git-commit-or-null>",
  "head_commit": "<git-commit>",
  "first_release": true,
  "changed_files": ["path/to/file.py"],
  "changed_units": [
    {
      "unit_id": "packages/nova_file_api",
      "project": "nova-file-api",
      "path": "packages/nova_file_api",
      "version": "0.1.0"
    }
  ]
}
```

## Canonical Runtime Monorepo

| Unit | Package | Version | Changed |
| --- | --- | --- | --- |
| `apps/nova_auth_api_service` | `nova-auth-api-service` | `0.2.2` | no |
| `apps/nova_file_api_service` | `nova-file-api-service` | `0.2.4` | no |
| `packages/nova_auth_api` | `nova-auth-api` | `0.4.0` | no |
| `packages/nova_dash_bridge` | `nova-dash-bridge` | `0.3.1` | no |
| `packages/nova_file_api` | `nova-file-api` | `0.5.0` | no |

This manifest reflects a docs-only release-management change set; no canonical
runtime monorepo units changed in this slice.

## Participating External Repositories

- `container-craft`: `0.0.0`
- `pca_analysis_dash`: `0.2.0`
