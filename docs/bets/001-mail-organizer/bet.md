---
id: 001
status: active
time_box: 3 weeks of evenings (slice 1 within 2 sessions)
started: 2026-10-10
---
# Bet 001: Mail organizer

## Problem
Jean manages seven mail accounts: four personal, two Trossitec (M365) and one customer tenant (Level C).
Years of backlog and daily noise hide the messages that need him.

## So that
Every day Jean knows what needs him, the noise is gone, and he never opens seven inboxes to find out.

## The demo (bet is done when)
When done, I can run `mafx run mail/triage` and see, across my personal accounts, what needs me today;
cleanup and filing happen with my approval; the report is waiting every morning.

## Constraints
- Mail content is processed by the local model only (Qwen on the DGX through SGLang). Nothing leaves the machine.
- Read-only until a slice explicitly adds write actions; every write goes through tool approval.
- Bulk actions use server-side batch operations, never one call per message.
- Level C (customer tenant): later, read-only, isolated, local model only.
- Tokens and secrets stay out of the repo (`.mafx/`, gitignored, file mode 600).

## Not doing
- Sending or replying to mail, drafting responses.
- Attachments.
- Microsoft employer mail.

## Slices
| # | Slice | Demo | Depends on | Status |
|---|---|---|---|---|
| 1 | Triage report, outlook.com, read-only | `mafx run mail/triage -p "last 7 days"` → buckets + top senders | none | demo pending ([s01.md](s01.md)) |
| 2 | Bulk cleanup with approval | "archive everything from these senders" → approve → done in seconds | 1 | |
| 3 | Filing rules | agent proposes inbox rules from history; on approval they are created server-side | 1 | |
| 4 | One view | gmail, yahoo, hotmail and the fourth personal account in one report | 1 | |
| 5 | Every morning | report generated on a schedule, waiting when Jean wakes up | 1 + platform A3.F7 | |
| 6 | Trossitec ×2 + Level C | separate domains; Level C read-only and isolated | 4 + platform A9.F5 | |

```
 s01 ──┬──► s02 cleanup ─┐
       ├──► s03 rules    ├─ parallel lanes (max 3 in progress, no shared files)
       └──► s04 accounts ┘──► s06 business + Level C
 platform A3.F7 triggers ─────► s05 every morning
```

## Demo log
| Date | Slice | What Jean saw | Decision |
|---|---|---|---|

## Outcome
<open>
