---
ADR: <zero-padded number>
Title: <clear decision title>
Status: <Proposed|Accepted|Implemented|Deprecated|Superseded>
Version: 0.1
Date: <YYYY-MM-DD>
Related:
  - "[<ADR|SPEC|REQ id and title>](<relative-link>)"
References:
  - "[<authoritative source title>](<url>)"
---

<!--
ADR authoring rules:
1) Replace every placeholder token (`<...>`). Do not leave template text in final ADRs.
2) Use markdown-clickable links for all ADR/SPEC/requirements/reference links.
3) Keep content decision-specific; avoid generic statements.
4) Document concrete constraints, alternatives, trade-offs, and implementation commitments.
5) For Accepted/Implemented ADRs, winning weighted score MUST be >= 9.0.
-->

## Summary

<1-3 sentences: what decision was made and why it matters now.>

## Context

<Describe the decision context with concrete details. Include:>

- <business/product need>
- <technical constraints and operational constraints>
- <rejected assumptions or risks discovered>
- <links to related ADR/SPEC/requirements where relevant>

## Alternatives

- A: <option A description>
- B: <option B description>
- C: <option C description>
<!-- Add D/E rows if needed; keep lettering consistent with scoring table. -->

## Decision Framework

### Option Scoring

| Option | Solution leverage (35%) (0-10) | Application value (30%) (0-10) | Maintenance and cognitive load (25%) (0-10) | Architectural adaptability (10%) (0-10) | Weighted total (/10.0) |
| --- | --- | --- | --- | --- | --- |
| **A** | **<raw>** | **<raw>** | **<raw>** | **<raw>** | **<calc>** |
| B | <raw> | <raw> | <raw> | <raw> | <calc> |
| C | <raw> | <raw> | <raw> | <raw> | <calc> |

`weighted total = (leverage * 0.35) + (value * 0.30) + (maintenance * 0.25) + (adaptability * 0.10)`

<!--
Decision-framework rules:
- Bold the actual winning row only.
- Recompute scores; do not reuse template/example values.
- Finalized decisions (Accepted/Implemented) must score >= 9.0.
-->

## Decision

<State chosen option explicitly.>

Implementation commitments:

- <commitment 1>
- <commitment 2>
- <commitment 3>

## Related Requirements

- [FR-xxxx](<relative-link-to-heading>)
- [NFR-xxxx](<relative-link-to-heading>)
- [IR-xxxx](<relative-link-to-heading>)
<!-- Include PR-xxxx only if your requirements taxonomy uses PR IDs. -->

## Consequences

1. Positive outcomes: <specific benefit and who benefits>.
2. Trade-offs/costs: <specific downside and operational impact>.
3. Ongoing considerations: <monitoring, migration, compatibility, or future ADR triggers>.

## Changelog

- YYYY-MM-DD: <initial creation or adoption summary>
- YYYY-MM-DD: <follow-up revision summary>

---

## ADR Completion Checklist

- [ ] All placeholders (`<...>`) and bracketed guidance are removed/replaced.
- [ ] All links are markdown-clickable and resolve to valid local docs or sources.
- [ ] Context includes concrete constraints, not generic boilerplate.
- [ ] Alternatives are decision-relevant and scored consistently.
- [ ] Winning row is bold and matches the Decision section.
- [ ] Accepted/Implemented ADR score is `>= 9.0`.
- [ ] Related requirements link to exact requirement anchors.
- [ ] Consequences include both benefits and trade-offs.
