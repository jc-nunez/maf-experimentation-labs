# Local infrastructure

Supporting services for agents, run with Docker on this machine.

| Service | Purpose | Endpoint |
|---|---|---|
| `searxng` | Web search backend for `tools/python/web-search` | `http://127.0.0.1:8888` (`SEARXNG_URL`) |

```bash
mafx infra up searxng       # generates the secret on first run, starts the container
mafx infra status
mafx infra down searxng
```

Each service is a folder with a `compose.yaml`. Secrets go in the folder's `.env`, which is gitignored and
generated when missing. Containers bind to loopback only and are memory-capped.
