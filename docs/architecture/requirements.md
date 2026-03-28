# Nova architecture requirements

Status: Active
Repository state: **current implemented baseline plus approved target-state program**
Last reviewed: 2026-03-25

## Purpose

Define the authoritative requirements split between:

- what the current repository still implements
- what the approved wave-2 hard cut must deliver

This file is intentionally explicit so implementation agents do not treat the
target as if it were already shipped.

## Current implemented baseline requirements

These remain true until the wave-2 branches merge:

- preserve the current repository's ability to serve transfer-control APIs
- preserve the current deployed-system operational runbooks until the platform
  migration lands
- preserve current release, deploy, and validation capability long enough to
  execute the migration program safely
- keep current route and package changes status-labelled accurately in docs

## Approved wave-2 target requirements

These are approved and should drive implementation work now:

- remove the dedicated auth service and session-style auth seam
- expose bearer JWT only as the public auth model
- replace generic jobs with explicit export workflow resources
- replace callback-driven async lifecycle handling with workflow-native state
- remove Redis from the canonical runtime correctness path
- adopt one canonical AWS runtime target
- simplify package layout and SDK generation
- reduce documentation authority sprawl

See `requirements-wave-2.md` for the target-state requirement list used by the
branch prompts.

## Quality requirements

Across both current and target states:

- documentation must state whether a surface is current, target, or superseded
- request/response models must stay typed and contract-driven
- tests must remain deterministic
- generated SDKs must be verifiable from committed contracts
- infrastructure and runtime docs must link back to executable source-of-truths

## Success criteria for this docs alignment pass

- no active router falsely claims that the target state is already implemented
- target-state ADRs/SPECs exist at the paths referenced by the implementation prompts
- wave-1 drafts are preserved only in superseded/history locations
- current implemented runbooks remain discoverable for live operations
- current vs target state can be understood from one pass through
  `docs/overview/IMPLEMENTATION-STATUS-MATRIX.md`
