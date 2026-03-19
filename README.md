# Агент моніторингу стану дорожнього покриття

Цей репозиторій містить реалізацію трьох модулів системи моніторингу стану дорожнього покриття:

- **Lab 1 — Agent**: емулює роботу датчиків (акселерометра, GPS та температурного датчика) шляхом читання даних з CSV‑файлів, агрегації записів та відправлення їх у брокер MQTT.
- **Lab 2 — Store API**: FastAPI‑сервіс для зберігання оброблених даних у PostgreSQL із WebSocket‑підпискою для UI‑клієнтів.
- **Lab 3 — Hub**: сервіс накопичення та пакетної обробки оброблених даних перед збереженням у БД через Store API. Отримує дані через MQTT, накопичує в Redis-буфері, відправляє пакетами на Store API.

Проєкт побудований з використанням `pydantic` v2 для опису моделей, `pydantic-settings` для конфігурації, `SQLAlchemy 2.0 async` + `asyncpg` для роботи з БД, `FastAPI` для API, `redis.asyncio` + `httpx` для Hub, `pre-commit` з набором лінтерів, та підтримує запуск як локально, так і в Docker.

## 📁 Структура проєкту

```
iot-labs/
├── data/                        # Тестові CSV‑файли з даними
├── src/                         # Вихідний код системи
│   ├── core/                    # Спільне ядро: конфіг та логер
│   │   ├── config.py            # Налаштування (MQTT, PostgreSQL, Redis, Store, Hub) з .env та змінних оточення
│   │   └── logger.py            # Кольоровий логер із відкладеною ініціалізацією
│   ├── models/                  # Pydantic‑моделі предметної області
│   │   ├── accelerometer.py
│   │   ├── gps.py
│   │   ├── temperature_sensor.py
│   │   ├── aggregated_data.py
│   │   └── processed_agent_data.py
│   ├── db/                      # Шар бази даних
│   │   ├── base.py              # SQLAlchemy async engine, session factory, Base, get_db_session
│   │   └── orm_models.py        # ORM‑модель ProcessedAgentDataORM
│   ├── repository/              # Шар доступу до даних (Repository pattern)
│   │   └── processed_agent_data.py
│   ├── api/                     # FastAPI застосунок
│   │   ├── app.py               # Фабрика застосунку та lifespan
│   │   ├── router.py            # Агрегатор роутерів
│   │   ├── dependencies.py      # FastAPI Depends: сесія БД
│   │   ├── ws_manager.py        # ConnectionManager для WebSocket
│   │   └── routes/              # Маршрути, розбиті за відповідальністю
│   │       ├── processed_agent_data.py  # CRUDL ендпоінти
│   │       ├── health.py        # /health із перевіркою БД (SELECT 1)
│   │       └── websocket.py     # /ws/ WebSocket ендпоінт
│   ├── agent/                   # Lab 1 — логіка агента
│   │   ├── file_datasource.py   # Читання CSV з циклічним та пакетним режимами
│   │   └── main.py              # Точка входу агента: підключення до MQTT та публікація даних
│   ├── store/                   # Lab 2 — точка входу Store API
│   │   └── main.py              # Запуск uvicorn
│   └── hub/                     # Lab 3 — Hub сервіс
│       ├── main.py              # Точка входу Hub: запуск HubService
│       ├── service.py           # HubService: MQTT → asyncio.Queue → Redis backlog → Store API
│       └── gateway.py           # StoreApiGateway: async HTTP-адаптер до Store API (httpx)
├── docker/
│   ├── Dockerfile.agent         # Образ агента
│   ├── Dockerfile.store         # Образ Store API
│   ├── Dockerfile.hub           # Образ Hub
│   ├── docker-compose.yaml      # Unified: agent + mqtt + postgres + pgadmin + store + redis + hub
│   ├── mosquitto/               # Конфігурація брокера Mosquitto
│   └── db/
│       └── structure.sql        # Ініціалізація таблиці processed_agent_data
├── tests/                       # Тести
│   ├── unit/
│   └── integration/
├── .pre-commit-config.yaml      # Налаштування pre‑commit: ruff, mypy, isort, pyupgrade
├── Justfile                     # Набір команд для спрощення встановлення, запуску і тестування
├── pyproject.toml               # Конфігурація проєкту та інструментів
└── README.md                    # Цей файл
```

## ⚙️ Попередні вимоги

- Python ≥3.13 (проєкт розроблявся та перевірявся на Python 3.13)  
- [uv](https://github.com/astral-sh/uv) — швидкий менеджер залежностей (встановити через `pip install uv`)  
- `just` — легкий таск‑раннер для керування скриптами
- `Docker` та `docker-compose` для контейнеризації (опційно)  
- `pre-commit` для запуску лінтерів (рекомендовано)

## 🚀 Запуск локально

1. **Клонувати репозиторій** та перейти у директорію.

2. **Встановити `uv` та `just`**, якщо вони ще не встановлені:

   ```bash
   pip install uv
   choco install just
   ```

3. **Встановити залежності**:

   ```bash
   just install
   ```

4. **(Опційно) налаштувати змінні оточення**. Значення за замовчуванням визначені у `src/core/config.py`.
   Можна створити файл `.env` у корені та перевизначити потрібні параметри, наприклад:

   ```env
   # Agent / MQTT
   MQTT_BROKER_HOST=localhost
   MQTT_BROKER_PORT=1883
   MQTT_TOPIC=agent_data_topic
   DELAY=0.1
   BATCH_SIZE=5
   ACCELEROMETER_FILE=data/accelerometer.csv
   GPS_FILE=data/gps.csv
   TEMPERATURE_FILE=data/temperature.csv

   # Store / PostgreSQL
   POSTGRES_HOST=localhost
   POSTGRES_PORT=5432
   POSTGRES_USER=user
   POSTGRES_PASSWORD=pass
   POSTGRES_DB=road_vision
   STORE_PORT=8000

   # Hub / Redis (Lab 3)
   REDIS_HOST=localhost
   REDIS_PORT=6379
   REDIS_DB=0
   HUB_BATCH_SIZE=10
   HUB_FLUSH_INTERVAL_SECONDS=30
   HUB_MQTT_TOPIC=processed_agent_data_topic

   LOG_LEVEL=INFO
   ```

### Lab 1 — Запуск агента

5. **Запустити брокер MQTT**, наприклад за допомогою `mosquitto`:

   ```bash
   mosquitto -c docker/mosquitto/config/mosquitto.conf
   ```

   Або використати офіційний контейнер:

   ```bash
   docker run -it --rm -p 1883:1883 eclipse-mosquitto
   ```

6. **Запустити агента**:

   ```bash
   just run-agent
   ```

   Агент почне циклічно читати дані з CSV‑файлів пакетами (`batch_size` записів), серіалізувати кожен запис у JSON та відправляти у зазначений MQTT‑топік.

7. **Перевірити результати** можна у [MQTT Explorer](https://mqtt-explorer.com/), підписавшись на ваш топік.

### Lab 2 — Запуск Store API

8. **Запустити PostgreSQL**:

   ```bash
   docker run --rm -e POSTGRES_USER=user -e POSTGRES_PASSWORD=pass -e POSTGRES_DB=road_vision -p 5432:5432 postgres:18-alpine
   ```

9. **Запустити Store API**:

   ```bash
   just run-store
   ```

10. **Перевірити Swagger**: [http://127.0.0.1:8000/docs](http://127.0.0.1:8000/docs)

11. **Виконати тести**:

    ```bash
    just test
    ```

### Lab 3 — Запуск Hub

Hub накопичує дані від агента через MQTT-топік `processed_agent_data_topic`, зберігає їх у Redis-буфері та відправляє пакетами (`hub_batch_size` записів) на Store API. Додатково реалізовано **periodичний flush** — якщо батч не набирається за `hub_flush_interval_seconds` секунд, Hub відправляє неповний буфер. При недоступності Store API записи зберігаються у Redis-backlog і повторно відправляються при наступному flush.

12. **Запустити Redis**:

    ```bash
    docker run --rm -p 6379:6379 redis:7-alpine
    ```

13. **Переконатися, що Store API запущено** (кроки 8–9 вище), оскільки Hub відправляє дані саме туди.

14. **Запустити Hub**:

    ```bash
    just run-hub
    ```

    Hub підключиться до MQTT-брокера, підпишеться на топік `HUB_MQTT_TOPIC` та почне накопичувати повідомлення.

15. **Перевірити** роботу в MQTT Explorer — надіслати тестове повідомлення у топік `processed_agent_data_topic`:

    ```json
    {
      "road_state": "good",
      "agent_data": {
        "accelerometer": {"x": 0.1, "y": 0.2, "z": 9.8},
        "gps": {"latitude": 50.45, "longitude": 30.52},
        "timestamp": "2026-03-19T17:00:00Z"
      }
    }
    ```

    Після накопичення `HUB_BATCH_SIZE` повідомлень (або через `HUB_FLUSH_INTERVAL_SECONDS` секунд) дані з'являться у PostgreSQL (перевірити у pgAdmin або через `GET /processed_agent_data/`).

## 🐳 Запуск у Docker

Проєкт включає єдиний `docker-compose.yaml`, що запускає всі сервіси одночасно:

```bash
just docker-up
```

Після запуску доступні:

| Сервіс | URL |
|---|---|
| Store API / Swagger | [http://localhost:8000/docs](http://localhost:8000/docs) |
| Health check | [http://localhost:8000/health](http://localhost:8000/health) |
| pgAdmin | [http://localhost:5050](http://localhost:5050) |
| MQTT broker | localhost:1883 |
| Redis | localhost:6379 |

Для зупинки та видалення volumes:

```bash
just docker-down
```

## 🧹 Налаштування pre‑commit

Для дотримання стилю коду та типів у репозиторії налаштовано `pre-commit`. Він запускає:

- **Ruff** — лінтер та форматер коду.
- **Isort** — сортування імпортів.
- **Mypy** — статичну перевірку типів.
- **Pyupgrade** — автоматичне оновлення синтаксису до сучасних стандартів.

Щоб увімкнути hooks на своєму локальному середовищі:

```bash
pip install pre-commit
pre-commit install
```

Після цього при кожному коміті будуть автоматично виконуватись лінтери.
Для ручного запуску можна використати:

```bash
pre-commit run --all-files
```

## 🛠️ Justfile

У корені проєкту розташований `Justfile` — набір корисних команд:

- `just install` — встановлює усі залежності (включно з dev‑залежностями) через `uv`.
- `just run-agent` — запускає агент локально (`python -m src.agent.main`).
- `just run-store` — запускає Store API локально (`uvicorn src.api.app:app`).
- `just run-hub` — запускає Hub локально (`python -m src.hub.main`).
- `just test` — запускає модульні тести за допомогою `pytest`.
- `just lint` — перевіряє код за допомогою `ruff`.
- `just format` — форматування коду (`ruff format`).
- `just typecheck` — статична перевірка типів (`mypy`).
- `just docker-up` — збирає та запускає всі сервіси в Docker.
- `just docker-down` — зупиняє контейнери та видаляє volumes.
- `just precommit` — запускає всі pre‑commit hooks.
