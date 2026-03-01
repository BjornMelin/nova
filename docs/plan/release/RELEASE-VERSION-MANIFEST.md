# Release Version Manifest

Date: 2026-03-01T23:21:59+00:00
Status: Active
Schema: 1.0

## Release Metadata
- `base_commit`: `4a5f711d22899502d6086ac0d44f7f2934fc33b3`
- `head_commit`: `bd5277f87036cc809bb534168b2026b922abf3fa`
- `first_release`: `False`
- `global_bump`: `minor`

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
| `apps/nova_auth_api_service` | `nova-auth-api-service` | `0.2.0` | yes |
| `apps/nova_file_api_service` | `nova-file-api-service` | `0.2.0` | yes |
| `packages/nova_auth_api` | `nova-auth-api` | `0.2.0` | yes |
| `packages/nova_dash_bridge` | `nova-dash-bridge` | `0.2.0` | yes |
| `packages/nova_file_api` | `nova-file-api` | `0.2.0` | yes |

## Participating External Repositories

- `container-craft`: `0.0.0`
- `pca_analysis_dash`: `0.2.0`
