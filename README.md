# Кондитерская — Backend (FastAPI)

Веб-система управления заказами кондитерской. Реализация backend по проектной документации v1.0.

## Стек
- Python 3.12, FastAPI, SQLAlchemy 2.0 (async), Alembic
- PostgreSQL 16
- Argon2id (argon2-cffi), JWT (python-jose)
- Pytest + httpx для тестов

## Быстрый старт (Docker Compose)

```bash
cp .env.example .env
# отредактируйте .env (JWT_SECRET, POSTGRES_PASSWORD)
docker compose up -d --build
docker compose exec backend alembic upgrade head
docker compose exec backend python -m app.cli create-admin --name "Админ" --email admin@example.com --password "SuperSecret123"
```

API: http://localhost:8000/api/v1
Документация: http://localhost:8000/docs
Health: http://localhost:8000/health/live и /health/ready

## Локальный запуск без Docker

```
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
# поднимите PostgreSQL и укажите DATABASE_URL
alembic upgrade head
python -m app.cli create-admin --name "Админ" --email admin@example.com --password "SuperSecret123"
uvicorn app.main:app --reload
```

## Тесты

```
docker compose exec backend pytest -v
# или локально (нужна отдельная тестовая БД):
pytest -v
```

## Структура

```
backend/
├── app/
│   ├── api/            # HTTP-роутеры (v1)
│   ├── core/           # конфиг, безопасность, ошибки, зависимости
│   ├── db/             # сессия, база моделей
│   ├── models/         # SQLAlchemy-модели
│   ├── schemas/        # Pydantic-схемы
│   ├── services/       # бизнес-логика
│   ├── cli.py          # служебные команды
│   └── main.py         # точка входа
├── migrations/         # Alembic
├── tests/
├── Dockerfile
├── docker-compose.yml
├── requirements.txt
└── .env.example
```

## Ключевые бизнес-правила

- **BR-02**: цена единицы = ROUND_HALF_UP(вес_г/1000 × (база + доплата), 2); строка = цена × кол-во.
- **BR-03**: дата самовывоза ≥ (локальная дата Europe/Moscow) + 2 дня.
- **BR-04**: NEW → CONFIRMED → IN_PRODUCTION → READY → COMPLETED; отмена: клиент (только NEW), сотрудник/админ (до COMPLETED/CANCELLED) с причиной.
- **BR-06**: снимки названий/цен в `order_items`; каталог деактивируется, не удаляется.
- **BR-08**: `expected_total` обязателен; при расхождении — 409 PRICE_CHANGED.
- **BR-09**: `Idempotency-Key` + хеш нормализованного тела; повтор → 200 с тем же заказом.
- **BR-10**: оптимистичная блокировка через `version`; конфликт → 409 VERSION_CONFLICT.

## Переменные окружения

| Переменная ↕▾ | Назначение ↕▾ |
|---|---|
| −`DATABASE_URL` | postgresql+asyncpg://user:pass@host:5432/db |
| −`JWT_SECRET` | случайная строка ≥ 32 байт |
| −`JWT_EXPIRE_MINUTES` | по умолчанию 30 |
| −`APP_TIMEZONE` | Europe/Moscow |
| −`PICKUP_ADDRESS` | адрес единственной точки |
| −`PICKUP_HOURS` | часы работы (текст) |
| −`ALLOWED_ORIGINS` | список origin через запятую |
| −`LOGIN_RATE_LIMIT` | попыток/мин на IP (по умолчанию 10) |
⚙

## Ошибки API

Единый формат:

```
{"error":{"code":"INVALID_TRANSITION","message":"...","details":{},"request_id":"..."}}
```

## Лицензия

Учебный проект.

</BDS:create_file>
<BDS:create_file fileName="backend/requirements.txt">

```text
fastapi==0.115.6
uvicorn[standard]==0.34.0
sqlalchemy[asyncio]==2.0.36
asyncpg==0.30.0
alembic==1.14.0
pydantic==2.10.4
pydantic-settings==2.7.0
python-jose[cryptography]==3.3.0
argon2-cffi==23.1.0
python-multipart==0.0.20
email-validator==2.2.0
slowapi==0.1.9
httpx==0.28.1
pytest==8.3.4
pytest-asyncio==0.25.0
pytest-cov==6.0.0

