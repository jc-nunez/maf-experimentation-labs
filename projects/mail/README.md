# mail

Mail organizer ([bet 001](../../docs/bets/001-mail-organizer/bet.md)). Slice 1: a **read-only** triage report
of an outlook.com inbox, grouped into **needs me · newsletters · receipts · notifications · noise**, plus the top
senders by volume. Mail is read through Microsoft Graph with `Mail.Read` only; no message is ever changed.

| Component | Runtime | What it does |
|---|---|---|
| `triage` | python agent | calls `mail_digest`, classifies each sender, answers with one table per bucket |
| `mail-digest` | python tool | `mail_digest(account, days, max_messages)`: inbox since N days, grouped by sender (count, unread, focused ratio, 3 samples) |

## Setup (once)

1. **App registration.** Azure portal, Trossitec tenant → App registrations → New registration:
   - Name: `mafx-mail`
   - Supported account types: **Personal Microsoft accounts only**
   - Redirect URI: leave empty
2. **Authentication** → Advanced settings → Allow public client flows: **Yes** → Save.
3. **API permissions** → Add a permission → Microsoft Graph → Delegated → `Mail.Read` → Add.
   (`User.Read` may already be listed; it is harmless. No admin consent is needed for personal accounts.)
4. **Client id.** Overview → copy the Application (client) ID into `.env` at the repo root:
   ```bash
   MAIL_OUTLOOK_CLIENT_ID=<application-client-id>
   ```
5. **Sign in** (device code, no password stored):
   ```bash
   uv run python -m mail_agent.auth outlook --alias personal
   ```
   Open the URL it prints, enter the code, sign in with the outlook.com account and accept the `Mail.Read`
   consent. The token cache is written to `.mafx/secrets/mail/outlook-personal.bin` (mode 600, gitignored).
   Tools refresh the token silently; if it expires, run step 5 again.

## Demo

```bash
MAF_PROVIDER=sglang mafx run mail/triage -p "last 7 days"
```

Expect: a "Needs me" table first, then the other buckets, then "Top 10 senders by volume". The run footer shows
the elapsed time. Other prompts: `"today"`, `"last 30 days"`, `"last 7 days for account personal"`.

```bash
mafx show mail                                              # only read tools: mail-digest
mafx tool run mail/mail-digest -a '{"days": 1}'             # the raw digest, no model involved
uv run pytest projects/mail                                 # offline: fixtures + mock provider
```

## Notes

- Mail content goes only to the provider you run with; keep `MAF_PROVIDER=sglang` (local model) for real mail.
- `max_messages` (default 500) bounds a run; the digest says `truncated: true` when the limit was hit.
- Another account: sign in with a different `--alias` and name it in the prompt.
