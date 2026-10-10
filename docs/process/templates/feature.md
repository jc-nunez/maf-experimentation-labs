---
id: A<n>.F<n>
title: <feature name>
area: A<n> <area name>
status: draft            # draft | G1-approved YYYY-MM-DD
owner: Jean
created: YYYY-MM-DD
---
# A<n>.F<n>: <feature name>

## Problem
<1 to 3 sentences: who is affected, what goes wrong or is missing, why it matters now.>

## Outcome
<What is observably true when this is done.>

## Scope
- In: <...>
- Non-goals: <what this item will not do, even if related>

## Requirements
| ID | Requirement (the system shall ...) | Priority | Acceptance check |
|---|---|---|---|
| A<n>.F<n>.R1 | ... | Must | `command` returns ... / test `test_x` passes / steps 1..n then ... |
| A<n>.F<n>.R2 | ... | Should | ... |

Priority: Must (item fails without it), Should (expected, can move to a follow-up with owner approval), Could (only if free).

## Constraints
- Runtimes: python | declarative | dotnet (which ones, and parity expectations)
- Providers: sglang | openai | azure-openai | foundry | mock
- Offline first: testable on the mock provider
- Security / data handling: <...>

## Assumptions
- <...>

## Open questions
| # | Question | Answer | Status |
|---|---|---|---|
| Q1 | ... | | open |

## Change log
| Date | Change | Reason |
|---|---|---|
