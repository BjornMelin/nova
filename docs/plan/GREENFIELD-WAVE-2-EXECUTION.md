# Green-field wave 2 execution plan

> **Implementation state:** Active implementation program for the approved wave-2 hard cut.


## Goal

Complete the second hard-cut modernization of Nova after the first wave was either not applied to the attached repo or was partially lost.

## Workstreams

1. API/auth hard cut
2. workflow contract hard cut
3. async runtime simplification
4. persistence and idempotency simplification
5. serverless platform migration
6. SDK unification
7. docs authority reset
8. CI/release rebaseline

## Recommended merge cadence

- branch 1 to 5: merge sequentially, no batching
- branch 6: merge after 1 to 5 are stable
- branch 7 to 9: SDK branches may run in parallel after branch 3
- branch 10: after all product-shape changes are merged
- branch 11: last

## Required acceptance conditions before declaring the repo canonical

- all auth-service artifacts deleted
- no remaining session-auth references
- no remaining Redis runtime requirement
- no generic jobs public contract
- no internal callback route
- no `packages/nova_sdk_fetch`
- no auth SDK packages
- new workflow package exists
- new serverless IaC exists
- SDK package names are unified
- docs authority contract is reset to the smaller canonical set
