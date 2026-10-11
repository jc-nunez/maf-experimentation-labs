# Demo Loop

How ideas become things Jean uses. One page, on purpose.

```
  INBOX ──► SHAPE ──► SLICE ──► BUILD ──► DEMO ──┐
  any idea   1 page    thin      Claude    Jean   │
                                 Code      uses it│
               ▲                                  │
               └── next slice · adjust · stop ◄───┘
```

| Step | What happens | Output |
|---|---|---|
| Inbox | any idea or tangent, one line, no processing | `docs/inbox.md` |
| Shape | problem, so that, **the demo**, time box, not doing | `docs/bets/NNN-name.md` |
| Slice | 3 to 6 thin slices; slice 1 runs within 1 or 2 sessions; only the current slice gets a spec | slice spec in the bet folder |
| Build | Claude writes the spec and a Claude Code prompt; Claude Code builds and tests | code + tests |
| Demo | Jean runs it and uses it; result logged | demo log in the bet |

## Rules
1. **No demo, no work.** Every bet and slice starts with: "When done, I can run ___ and see ___."
2. **One bet at a time.** Everything else goes to the inbox. Inside a bet, independent slices (no dependency, no shared
   files) may run in parallel: one handoff, branch and worktree each, at most 3 in progress.
3. **Fixed time, flexible scope.** Cut scope, never stretch time.
4. **Design only the current slice.** The platform map is a reference library, not a prerequisite.
5. **Every bet ends Shipped, Paused or Killed.** Nothing is silently dropped.

## Roles
| Who | Does |
|---|---|
| Jean | picks the bet, approves the demo, uses the result, decides next slice / adjust / stop |
| Claude (Cowork) | shapes, slices, writes slice specs and Claude Code prompts, keeps `docs/NOW.md`, flags tangents |
| Claude Code | builds and tests the slice |

## Files
```
docs/NOW.md                  start here: current bet, slice, demo command, next action
docs/inbox.md                ideas and tangents
docs/bets/NNN-name/bet.md    one page per bet (shape, slices, demo log, outcome)
docs/bets/NNN-name/sNN.md    spec for the current slice (demo, acceptance, design, tasks, prompt)
docs/platform/               reference: map, areas, features, backlog
docs/process/templates/      bet.md, slice.md
docs/process/reference/      the earlier stage-gate process (reference only)
```

## Session
```
 OPEN   read docs/NOW.md, show bet + slice + next action, confirm
 WORK   current slice only; tangents go to docs/inbox.md
 CLOSE  update docs/NOW.md and the bet's demo log; say what moved and the next action
```
