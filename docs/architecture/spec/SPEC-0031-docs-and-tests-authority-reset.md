# SPEC-0031 -- Docs and tests authority reset

> **Implementation state:** Approved target-state SPEC. This docs pack applies the docs side immediately; code/tests remain to be aligned by the implementation branches.

## Problem

The repo has too many active docs and too many tests whose only job is to enforce that sprawl.

## Decision

Keep a smaller active authority set and archive or delete the rest.

## Active docs classes

- current overview
- active ADRs
- active specs
- active runbooks
- active SDK/client docs
- implementation prompts if intentionally retained

## Test rule

Keep tests that protect executable behaviour, contract compatibility for the current API, SDK generation correctness, and platform safety.
Delete or archive tests whose primary purpose is to enforce legacy planning/history surfaces.
