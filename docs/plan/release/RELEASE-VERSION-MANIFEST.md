# Release Version Manifest

Date: 2026-03-12T00:37:43+00:00
Status: Active
Schema: 1.0

## Release Metadata
- `base_commit`: `09b8659b5ada9c7eb61352ba73f70ca7d7b8e269`
- `head_commit`: `09b8659b5ada9c7eb61352ba73f70ca7d7b8e269`
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
      "format": "pypi",
      "namespace": null,
      "version": "0.1.0"
    }
  ]
}
```

## Canonical Runtime Monorepo

| Unit | Package | Version | Changed |
| --- | --- | --- | --- |
| `packages/nova_auth_api` | `nova-auth-api` | `0.4.0` | no |
| `packages/nova_dash_bridge` | `nova-dash-bridge` | `0.3.1` | no |
| `packages/nova_file_api` | `nova-file-api` | `0.5.0` | no |
| `packages/nova_runtime_support` | `nova-runtime-support` | `0.1.0` | no |
| `packages/nova_sdk_auth` | `@nova/sdk-auth` | `0.1.0` | no |
| `packages/nova_sdk_fetch` | `@nova/sdk-fetch` | `0.1.0` | no |
| `packages/nova_sdk_file` | `@nova/sdk-file` | `0.1.0` | no |
| `packages/nova_sdk_py_auth` | `nova-sdk-py-auth` | `0.1.0` | no |
| `packages/nova_sdk_py_file` | `nova-sdk-py-file` | `0.1.0` | no |

## Participating External Repositories

- `container-craft`: `0.0.0`
- `pca_analysis_dash`: `0.2.0`
