# Deploying the Web Panel on a VPS

This guide walks through deploying AllInclusiveParser **and** its FastAPI +
SvelteKit admin panel to a fresh Linux VPS using Docker Compose.

The image is multi-stage: stage 1 builds the SvelteKit SPA with Node 20, stage
2 installs the parser's Python dependencies plus the FastAPI backend and
serves the SPA from FastAPI itself. There's only one container at runtime.

## 1. Prerequisites on the VPS

- Linux box with at least 1 GB RAM, 5 GB free disk.
- Docker Engine ≥ 24 with the Compose plugin (`docker compose ...`).
- Inbound TCP port (default `8000`) reachable from your machine — or, better,
  put a reverse proxy (nginx / Caddy / Traefik) in front and terminate TLS
  there.

A one-shot installer for Debian/Ubuntu:

```bash
curl -fsSL https://get.docker.com | sudo sh
sudo usermod -aG docker "$USER"
# log out and back in so the new group sticks
```

## 2. Get the code

```bash
git clone https://github.com/antonsilianov6-ship-it/Parser.git
cd Parser
```

## 3. Prepare host files that get bind-mounted

Docker bind-mounts that point at non-existent paths become empty directories,
which is **not** what we want for `config.json` and `channels.txt`. Create
them up-front:

```bash
mkdir -p sessions data logs exports config

# Empty config.json — the panel will populate it via /settings.
[ -f config.json ] || echo '{}' > config.json

# Channels list — empty is fine, edit later from the UI.
[ -f channels.txt ] || touch channels.txt

# Prompts file — keep the repo default if you have it, or start blank.
[ -f config/prompts.json ] || echo '{"prompts":{},"defaults":{}}' > config/prompts.json
```

## 4. Configure secrets

```bash
cp .env.example .env
# Generate a real JWT secret:
sed -i "s|^PANEL_JWT_SECRET=.*|PANEL_JWT_SECRET=$(openssl rand -hex 32)|" .env
```

Open `.env` in an editor if you want to change the public port
(`PANEL_PORT`) or the access token TTL.

> **Never commit `.env`** — it is already in `.gitignore`.

## 5. Build and start the panel

```bash
docker compose build
docker compose up -d
docker compose logs -f parser-panel   # watch startup
```

The container exposes the panel on `http://<vps-ip>:8000`.

## 6. Bootstrap the first admin user

The panel ships with **no users** by default. The first one is created via a
one-time API call (the endpoint becomes a 409 after the first user exists):

```bash
curl -X POST http://localhost:8000/api/users/bootstrap \
     -H "Content-Type: application/json" \
     -d '{"username":"admin","password":"REPLACE_WITH_A_STRONG_PASSWORD"}'
```

You can run this from the VPS directly — port `8000` is already exposed inside
the box. After this you can rotate the password and invite further users from
the UI under `/users`.

## 7. Wire up Telegram

1. Go to <https://my.telegram.org/apps> and grab your `api_id` / `api_hash`.
2. In the panel: **Telegram-аккаунты → Создать слот**.
3. Click **Авторизовать**, enter `api_id`/`api_hash`, then phone, then the SMS
   code Telegram sends, then 2FA password if you have one.
4. The session file lands at `sessions/user_<uid>_<label>.session` on the host
   thanks to the bind mount.

Repeat step 2–4 for as many Telegram accounts as you want — the jobs runner
will use the slot you pick when launching a parse run.

## 8. Run a parse job

1. Make sure `channels.txt` has at least one channel (edit it from
   **Настройки → Каналы**).
2. Open **Задачи → Создать**, pick your authorised TG slot, choose mode
   `parse` (optionally narrow to a single channel), submit.
3. Click the job row to follow live logs over SSE.

After the first successful parse the dashboard's «Парсер — статистика» block
populates, and the **Сообщения** page becomes browsable.

## 9. Updating to a new release

```bash
git pull
docker compose build
docker compose up -d
```

State you care about (`sessions/`, `data/parser.db`, the panel's own
`panel-state` volume, your edited `config.json` / `channels.txt`) survives
rebuilds because it lives outside the image.

## 10. Putting a reverse proxy in front

Recommended for any internet-facing deployment so you get HTTPS and a hostname
nicer than `:8000`. Minimal Caddyfile example:

```
panel.example.com {
    reverse_proxy 127.0.0.1:8000
}
```

Then run `caddy reload` and point your domain at the VPS — Caddy will fetch a
Let's Encrypt cert automatically.

## Troubleshooting

| Symptom | Fix |
| --- | --- |
| `PANEL_JWT_SECRET is required` on `up` | You forgot to populate `.env` from `.env.example`. |
| `/login` 404 | The frontend wasn't built into the image — rerun `docker compose build` (the cache is fine). |
| `data/parser.db not found` on `/messages` | Run a `parse` job first; the parser creates the DB on first write. |
| Telegram auth gives `FloodWait` | Telegram is throttling you — wait the suggested seconds and retry. |
| Container restarts on boot | `docker compose logs parser-panel` will show the trace; usually a missing `.env` value. |

## Why a separate `requirements.runtime.txt`?

`requirements.txt` in the repo root pins to a few package versions that don't
exist on PyPI yet (`pandas==3.0.2`, `cryptography==47.0.0`,
`requests==2.33.1`). The Docker image installs `requirements.runtime.txt`
instead, which uses currently-released, compatible versions. When upstream
catches up, the two files can be reconciled; until then keep them in sync
manually.
