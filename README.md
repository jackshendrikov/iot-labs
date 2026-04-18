# UrbanPulse IoT

Цей репозиторій містить реалізацію багатокомпонентної IoT-платформи міського моніторингу, яка еволюціонувала від сценарію контролю стану дорожнього покриття до універсальної системи збору, обробки та збереження різнорідної сенсорної телеметрії:

- **Lab 1 — Agent**: емулює роботу датчиків (акселерометра, GPS та температурного датчика) шляхом читання даних з CSV‑файлів, агрегації записів та відправлення їх у брокер MQTT.
- **Lab 2 — Store API**: FastAPI‑сервіс для зберігання оброблених даних у PostgreSQL із WebSocket‑підпискою для UI‑клієнтів.
- **Lab 3 — Hub**: сервіс накопичення та пакетної обробки оброблених даних перед збереженням у БД через Store API. Отримує дані через MQTT, накопичує в Redis-буфері, відправляє пакетами на Store API.
- **Lab 4 — Edge Data Logic**: сервіс первинної обробки даних агента — підписується на `agent_data_topic`, класифікує стан дорожнього покриття за даними акселерометра та публікує `ProcessedAgentData` у `processed_agent_data_topic`.
- **Lab 5 — Map UI**: веб‑інтерфейс для візуалізації маршруту та стану дорожнього покриття на інтерактивній карті. Завантажує історичні дані через `GET /processed_agent_data/` та отримує нові точки у реальному часі через WebSocket `/ws`. Маршрут забарвлюється сегментами відповідно до `road_state`; графіки акселерометра відображають осі Z (відхилення від baseline) та X/Y.
- **Lab 6 — Universal Sensor Structure**: універсальна розширювана структура даних для нових типів сенсорних об'єктів (паркомісця, світлофори, сенсори якості повітря, лічильники електроенергії). Побудована на дискримінованій спілці Pydantic-payload-ів та єдиній таблиці PostgreSQL з JSONB для типоспецифічних полів. Включає генератор синтетичних даних, що відтворює патерни відкритих датасетів (SFpark, EEA AQ, smart-metering).

Проєкт побудований з використанням `pydantic` v2 для опису моделей, `pydantic-settings` для конфігурації, `SQLAlchemy 2.0 async` + `asyncpg` для роботи з БД, `FastAPI` для API, `redis.asyncio` + `httpx` для Hub, `paho-mqtt` для Edge, `Leaflet.js` + `Chart.js` для Map UI, `pre-commit` з набором лінтерів, та підтримує запуск як локально, так і в Docker.

## 📁 Структура проєкту

```
iot-labs/
├── data/                        # Тестові CSV‑файли з даними
│   ├── accelerometer.csv        # Дані акселерометра
│   ├── gps.csv                  # GPS-координати
│   └── temperature.csv
├── src/                         # Вихідний код системи
│   ├── core/                    # Спільне ядро: конфіг та логер
│   │   ├── config.py            # Налаштування (MQTT, PostgreSQL, Redis, Store, Hub, Edge) з .env та змінних оточення
│   │   └── logger.py            # Кольоровий логер із відкладеною ініціалізацією
│   ├── models/                  # Pydantic‑моделі предметної області
│   │   ├── accelerometer.py
│   │   ├── gps.py
│   │   ├── temperature_sensor.py
│   │   ├── aggregated_data.py
│   │   ├── processed_agent_data.py
│   │   ├── geo_location.py      # Lab 6: WGS-84 геоточка
│   │   ├── sensor_type.py       # Lab 6: StrEnum типів сенсорів
│   │   ├── sensor_reading.py    # Lab 6: SensorReading + SensorMetadata + ...InDB
│   │   └── payloads/            # Lab 6: типоспецифічні payload-и (discriminated union)
│   │       ├── car_park.py
│   │       ├── traffic_light.py
│   │       ├── air_quality.py
│   │       └── energy_meter.py
│   ├── db/                      # Шар бази даних
│   │   ├── base.py              # SQLAlchemy async engine, session factory, Base, get_db_session
│   │   └── orm_models.py        # ORM‑модель ProcessedAgentDataORM
│   ├── repository/              # Шар доступу до даних (Repository pattern)
│   │   └── processed_agent_data.py
│   ├── api/                     # FastAPI застосунок
│   │   ├── app.py               # Фабрика застосунку, lifespan, монтування StaticFiles /ui
│   │   ├── router.py            # Агрегатор роутерів
│   │   ├── dependencies.py      # FastAPI Depends: сесія БД
│   │   ├── ws_manager.py        # ConnectionManager для WebSocket
│   │   └── routes/              # Маршрути, розбиті за відповідальністю
│   │       ├── processed_agent_data.py  # CRUDL ендпоінти + WS broadcast при POST
│   │       ├── health.py        # /health із перевіркою БД (SELECT 1)
│   │       └── websocket.py     # /ws WebSocket ендпоінт
│   ├── agent/                   # Lab 1 — логіка агента
│   │   ├── file_datasource.py   # Читання CSV: циклічний (LOOP_READING=true) та кінцевий режими
│   │   └── main.py              # Точка входу агента: підключення до MQTT та публікація даних
│   ├── store/                   # Lab 2 — точка входу Store API
│   │   └── main.py              # Запуск uvicorn
│   ├── hub/                     # Lab 3 — Hub сервіс
│   │   ├── main.py              # Точка входу Hub: запуск HubService
│   │   ├── service.py           # HubService: MQTT → asyncio.Queue → Redis backlog → Store API
│   │   └── gateway.py           # StoreApiGateway: async HTTP-адаптер до Store API (httpx)
│   ├── edge/                    # Lab 4 — Edge Data Logic
│   │   ├── main.py              # Точка входу Edge
│   │   ├── processor.py         # process_agent_data(): класифікація RoadState за акселерометром
│   │   └── adapters.py          # AgentGateway, HubGateway, AgentMqttAdapter, HubMqttAdapter
│   ├── ui/                      # Lab 5 — Map UI (статичні файли, роздаються Store API)
│   │   ├── index.html           # Розмітка: topbar, карта Leaflet, sidebar з KPI та логом
│   │   ├── style.css            # Темна дизайн-система (CartoDB Dark Matter, CSS custom properties)
│   │   └── app.js               # Логіка: REST-завантаження історії, WS live-stream, Chart.js графіки
│   └── synthetic/               # Lab 6 — Генератор синтетичних показань нових сенсорів
│       ├── generator.py         # generate_readings / write_csv_files / read_csv_file
│       └── main.py              # CLI: CSV у data/ + опційний --seed-db у PostgreSQL
├── docker/
│   ├── Dockerfile.agent         # Образ агента
│   ├── Dockerfile.store         # Образ Store API
│   ├── Dockerfile.hub           # Образ Hub
│   ├── Dockerfile.edge          # Образ Edge
│   ├── docker-compose.yaml      # Unified: agent + mqtt + postgres + pgadmin + store + redis + hub + edge
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
   LOOP_READING=true
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

   Агент почне читати дані з CSV‑файлів пакетами (`batch_size` записів), серіалізувати кожен запис у JSON та відправляти у зазначений MQTT‑топік. За замовчуванням увімкнено циклічний режим (`LOOP_READING=true`); для одноразового проходу по файлах встановіть `LOOP_READING=false` — агент зупиниться після досягнення кінця CSV.

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
        "timestamp": "2026-03-21T17:00:00Z"
      }
    }
    ```

    Після накопичення `HUB_BATCH_SIZE` повідомлень (або через `HUB_FLUSH_INTERVAL_SECONDS` секунд) дані з'являться у PostgreSQL (перевірити у pgAdmin або через `GET /processed_agent_data/`).

### Lab 4 — Запуск Edge Data Logic

Edge підписується на `agent_data_topic`, класифікує стан дорожнього покриття за даними акселерометра та публікує результат у `processed_agent_data_topic` для Hub.

16. **Переконатися, що запущені MQTT-брокер та Hub** (кроки вище).

17. **Запустити Edge**:

    ```bash
    just run-edge
    ```

18. **Перевірити** у MQTT Explorer — після запуску обидва топіки мають бути активними:
    - `agent_data_topic` — сирі дані від Agent
    - `processed_agent_data_topic` — класифіковані дані з `road_state` від Edge

### Lab 5 — Перегляд Map UI

Map UI роздається безпосередньо Store API як статичний сайт (FastAPI `StaticFiles`), тому окремого сервісу не потрібно.

19. **Переконатися, що Store API запущено** (крок 9 або `just docker-up`).

20. **Відкрити у браузері**:

    ```
    http://localhost:8000/ui/
    ```

    Сторінка завантажить усі збережені точки через `GET /processed_agent_data/` та підключиться до WebSocket `ws://localhost:8000/ws` для отримання нових точок у реальному часі.

21. **Що відображається**:
    - **Карта** (CartoDB Dark Matter) — маршрут забарвлений сегментами: <span style="color:#3fb950">■</span> `GOOD` / <span style="color:#d29922">■</span> `WARNING` / <span style="color:#f85149">■</span> `BAD`; пульсуючий маркер — поточна позиція автомобіля.
    - **KPI** — лічильники Good / Warning / Bad з пропорційними індикаторами.
    - **Графік Z** — відхилення осі Z від baseline (16 500) з анотаційними лініями порогів Warning/Bad.
    - **Графік X/Y** — бічне прискорення в реальному часі.
    - **Лог подій** — остання 80 точок із координатами, значеннями акселерометра та часом.

    > **Примітка щодо LOOP_READING**: для більш показової демонстрації маршруту рекомендується запускати агента з `LOOP_READING=false` — у такому разі кожна GPS-точка відображається рівно один раз, без повторень координат.

### Lab 6 — Universal Sensor Structure

Lab 6 розширює систему універсальною структурою для довільних сенсорних об'єктів. Замість окремих таблиць під кожен новий тип використовується **індексований envelope + JSONB payload**: нові сенсори додаються лише описом Pydantic-моделі, без міграції БД.

#### Структура даних

```
SensorReading
├── metadata: SensorMetadata
│   ├── sensor_id: str
│   ├── sensor_type: SensorType       # car_park | traffic_light | air_quality | energy_meter
│   ├── location: GeoLocation         # latitude, longitude (WGS-84)
│   └── timestamp: datetime
└── payload: SensorPayload            # discriminated union за полем `kind`
    ├── CarParkPayload                # total_spots, occupied_spots, avg_stay_minutes, occupancy_rate (computed)
    ├── TrafficLightPayload           # state, cycle_seconds, queue_length, pedestrian_request
    ├── AirQualityPayload             # pm2_5, pm10, no2, o3, temperature_c, humidity_percent, pressure_hpa
    └── EnergyMeterPayload            # power_kw, voltage_v, current_a, cumulative_kwh, power_factor
```

Таблиця `sensor_readings` (див. `docker/db/structure.sql`) зберігає метадані колонками (з індексами на `sensor_id`, `sensor_type`, `timestamp` та GIN-індексом на `payload`), що дає швидкий пошук без втрати типоспецифічної семантики. Під SQLite (тести) JSONB автоматично заміщується на стандартний `JSON`.

#### Додавання нового типу сенсора

1. Створити `src/models/payloads/<new_type>.py` з полем `kind: Literal["<new_type>"]`.
2. Додати клас у `SensorPayload = Annotated[Union[..., NewPayload], Field(discriminator="kind")]` у `src/models/payloads/__init__.py`.
3. Додати значення у `SensorType` StrEnum.

Міграція БД **не потрібна** — JSONB приймає будь-яку форму.

#### Синтетичні дані та open-dataset-походження

Генератор `src/synthetic/generator.py` відтворює патерни реальних відкритих датасетів:

| Тип сенсора      | Open-dataset натхнення                          | Патерни, що моделюються                                 |
|------------------|-------------------------------------------------|----------------------------------------------------------|
| `car_park`       | SFMTA SFpark                                    | Синусоїда зайнятості з піком о 13:00, сталий `total_spots` |
| `traffic_light`  | Kyiv Open Data (мапа світлофорів)               | Цикли 60–120 с, 4-фазовий обхід R→G→Y→R, пішохідні запити |
| `air_quality`    | EEA AQ e-reporting, SaveEcoBot                  | Нормальний розподіл PM2.5/PM10/NO₂/O₃, T, RH, P          |
| `energy_meter`   | Industrial smart-metering telemetry             | Монотонно зростаючий `cumulative_kwh`, PF 0.85–0.99      |

Запуск:

```bash
# лише CSV у data/
just generate-sensors

# CSV + вставка у PostgreSQL (потрібен Store API + БД up)
just seed-sensors
```

Після `just generate-sensors` у `data/` з'являться:

- `data/car_parks.csv` — 5 паркінгів × 24 години
- `data/traffic_lights.csv` — 8 світлофорів × 20 зрізів
- `data/air_quality.csv` — 4 станції × 24 години
- `data/energy_meters.csv` — 3 лічильники × 24 зрізи

CSV-формат (`sensor_id, sensor_type, latitude, longitude, timestamp, payload`), де `payload` — JSON-рядок. Функція `read_csv_file()` відновлює повноцінний `SensorReading` (перевірено round-trip-тестами).

#### REST API

Маршрути змонтовані у Store API (Lab 2) поруч із `/processed_agent_data/`:

| Метод   | URL                                    | Опис                                           |
|---------|----------------------------------------|------------------------------------------------|
| POST    | `/sensor_readings/`                    | Пакетне збереження показань                    |
| GET     | `/sensor_readings/`                    | Список з фільтрами `sensor_type`, `sensor_id`, `limit` |
| GET     | `/sensor_readings/{id}`                | Отримання одного запису                        |
| DELETE  | `/sensor_readings/{id}`                | Видалення запису                               |

Приклад тіла POST (пакет із двох типів сенсорів):

```json
[
  {
    "metadata": {
      "sensor_id": "car_park-001",
      "sensor_type": "car_park",
      "location": {"latitude": 50.45, "longitude": 30.52},
      "timestamp": "2026-04-17T10:00:00Z"
    },
    "payload": {
      "kind": "car_park",
      "total_spots": 100,
      "occupied_spots": 42,
      "avg_stay_minutes": 65.0
    }
  },
  {
    "metadata": {
      "sensor_id": "tl-005",
      "sensor_type": "traffic_light",
      "location": {"latitude": 50.44, "longitude": 30.51},
      "timestamp": "2026-04-17T10:01:00Z"
    },
    "payload": {
      "kind": "traffic_light",
      "state": "red",
      "cycle_seconds": 90,
      "queue_length": 4,
      "pedestrian_request": false
    }
  }
]
```

#### Тести

- `tests/unit/test_sensor_readings.py` — 15 тестів: enum-и, валідація полів, дискримінатор `kind`.
- `tests/integration/test_sensor_readings_api.py` — 10 тестів через `httpx.AsyncClient` + in-memory SQLite: CRUDL, фільтри, round-trip JSON payload.

```bash
just test   # усі 108 тестів (83 попередніх + 25 Lab 6)
```

## 🐳 Запуск у Docker

Проєкт включає єдиний `docker-compose.yaml`, що запускає всі сервіси одночасно:

```bash
just docker-up
```

Після запуску доступні:

| Сервіс | URL |
|---|---|
| Store API / Swagger | [http://localhost:8000/docs](http://localhost:8000/docs) |
| Map UI | [http://localhost:8000/ui/](http://localhost:8000/ui/) |
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
- `just run-store` — запускає Store API локально (`uvicorn src.api.app:app`). Map UI доступний на `/ui/`.
- `just run-hub` — запускає Hub локально (`python -m src.hub.main`).
- `just run-edge` — запускає Edge локально (`python -m src.edge.main`).
- `just generate-sensors` — генерує синтетичні CSV у `data/` для нових типів сенсорів (Lab 6).
- `just seed-sensors` — генерує та одразу записує показання у PostgreSQL (`sensor_readings`).
- `just test` — запускає модульні тести за допомогою `pytest`.
- `just lint` — перевіряє код за допомогою `ruff`.
- `just format` — форматування коду (`ruff format`).
- `just typecheck` — статична перевірка типів (`mypy`).
- `just docker-up` — збирає та запускає всі сервіси в Docker.
- `just docker-down` — зупиняє контейнери та видаляє volumes.
- `just precommit` — запускає всі pre‑commit hooks.
