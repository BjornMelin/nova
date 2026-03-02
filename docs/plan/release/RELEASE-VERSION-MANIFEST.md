# Release Version Manifest

Date: 2026-03-02T08:49:00+00:00
Status: Active
Schema: 1.0

## Release Metadata
- `base_commit`: `4d46e9f5159441e3164d333725a0108dbb78c5c5`
- `head_commit`: `8b55dd18f7aaf413a52628ffd27dbc4096872360`
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
| `apps/nova_auth_api_service` | `nova-auth-api-service` | `0.2.0` | no |
| `apps/nova_file_api_service` | `nova-file-api-service` | `0.2.2` | yes |
| `packages/nova_auth_api` | `nova-auth-api` | `0.2.0` | no |
| `packages/nova_dash_bridge` | `nova-dash-bridge` | `0.2.1` | yes |
| `packages/nova_file_api` | `nova-file-api` | `0.3.0` | yes |

## Participating External Repositories

- `container-craft`: `0.0.0`
- `pca_analysis_dash`: `0.2.0`
