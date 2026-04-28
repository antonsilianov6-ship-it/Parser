# Parser Web Panel — Backend

FastAPI-бэкенд административной панели для `AllInclusiveParser`. Ничего в исходном коде парсера
не меняет: выступает обёрткой — хранит пользователей панели, управляет Telegram-сессиями, запускает
`main.py` / `automation.py` подпроцессами (в следующих PR) и стримит логи.

## Стек

- FastAPI + Uvicorn
- SQLModel (SQLite) — пользователи панели и Telegram-аккаунты
- bcrypt + PyJWT — аутентификация
- pytest + httpx — тесты

## Быстрый старт (dev)

```bash
cd webpanel/backend
python -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"

# Инициализация БД и создание первого пользователя
export PANEL_JWT_SECRET="change-me"
python -m scripts.bootstrap_admin --username admin --password 'change-me-too'

# Запуск
uvicorn app.main:app --reload --port 8000
```

Документация API: http://localhost:8000/docs

## Конфигурация (env)

| Переменная | По умолчанию | Назначение |
|---|---|---|
| `PANEL_JWT_SECRET` | — (обязательно) | Секрет для подписи JWT (HS256) |
| `PANEL_JWT_ACCESS_TTL_MINUTES` | `60` | Время жизни access-токена |
| `PANEL_DB_PATH` | `./panel.db` | Путь к SQLite БД панели |
| `PANEL_ALLOW_REGISTRATION` | `false` | Разрешить `POST /api/users` без аутентификации |
| `PANEL_CORS_ORIGINS` | `http://localhost:5173` | CSV список разрешённых origin для CORS |

## Структура

```
webpanel/backend/
├── app/
│   ├── main.py            # FastAPI app, CORS, роутеры
│   ├── config.py          # pydantic-settings
│   ├── db.py              # SQLModel engine + get_session
│   ├── security.py        # bcrypt + JWT
│   ├── deps.py            # get_current_user
│   ├── models/
│   │   ├── user.py
│   │   └── telegram_account.py
│   ├── schemas/           # Pydantic модели запроса/ответа
│   └── routers/
│       ├── health.py
│       ├── auth.py
│       ├── users.py
│       └── telegram_accounts.py
├── scripts/
│   └── bootstrap_admin.py
└── tests/
```

## Тесты

```bash
pytest
```

## Замечания по multi-session

В этой PR только модель данных: у каждого `User` есть список `TelegramAccount` (owner_id,
`session_path`, `is_shared`). Эндпоинты `/api/telegram/accounts` пока делают CRUD на уровне метаданных
(без реальной Telethon-авторизации). Полноценный send-code/sign-in флоу и патч парсера
(`PARSER_SESSION_PATH`) — следующим PR.
