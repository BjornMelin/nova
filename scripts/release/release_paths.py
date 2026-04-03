"""Canonical repo-root-relative paths for release machine artifacts.

Narrative operator runbooks live under docs/runbooks/release/.
Machine-owned release inputs live under the repo-root release/ directory.
"""

from __future__ import annotations

# Machine-owned committed release inputs live here.
RELEASE_ARTIFACTS_DIR = "release"

RELEASE_VERSION_MANIFEST_PATH = (
    f"{RELEASE_ARTIFACTS_DIR}/RELEASE-VERSION-MANIFEST.md"
)

RELEASE_PREP_PATH = f"{RELEASE_ARTIFACTS_DIR}/RELEASE-PREP.json"

RELEASE_EXECUTION_MANIFEST_PATH = (
    f"{RELEASE_ARTIFACTS_DIR}/release-execution-manifest.json"
)

RUNTIME_CONFIG_GENERATED_MD_PATH = (
    "docs/contracts/runtime-config-contract.generated.md"
)
