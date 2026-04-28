# Parser Web Panel — Frontend

SvelteKit 5 (runes) SPA для административной панели AllInclusiveParser.

## Стек

- SvelteKit 5 (runes mode) + TypeScript
- TailwindCSS 4 (через `@tailwindcss/vite`)
- `@sveltejs/adapter-static` (собирается в статику, раздаётся либо любым nginx-ом,
  либо FastAPI через `PANEL_FRONTEND_DIR`)

## Быстрый старт (dev)

```bash
cd webpanel/frontend
npm install
npm run dev
# → http://localhost:5173
```

По умолчанию Vite проксирует `/api` → `http://localhost:8000` (см. `vite.config.ts`).
Переопределить можно через env `VITE_API_PROXY_TARGET=http://host:port npm run dev`.

## Продакшн сборка

```bash
npm run build
# → build/ (index.html + ассеты)
```

Запустить FastAPI бэкенд c `PANEL_FRONTEND_DIR=/path/to/webpanel/frontend/build` —
он раздаст SPA из того же процесса. Тогда API и UI живут на одном origin и
никакой CORS не нужен.

## Проверки

```bash
npm run check    # svelte-check + tsc
npm run build    # vite build
```
