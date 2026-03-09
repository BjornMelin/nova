# Release Version Manifest

Date: 2026-03-09T10:27:27+00:00
Status: Active
Schema: 1.0

## Release Metadata
- `base_commit`: `0704b452c80513b38c2a08e46c6d8605fe55705d`
- `head_commit`: `0704b452c80513b38c2a08e46c6d8605fe55705d`
- `first_release`: `False`
- `global_bump`: `None`

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
| `packages/nova_runtime_support` | `nova-runtime-support` | `0.1.0` | no |
| `packages/nova_sdk_py_auth` | `nova-sdk-py-auth` | `0.1.0` | no |
| `packages/nova_sdk_py_file` | `nova-sdk-py-file` | `0.1.0` | no |

## Participating External Repositories

- `container-craft`: `0.0.0`
- `pca_analysis_dash`: `0.2.0`
