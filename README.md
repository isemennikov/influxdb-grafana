# InfluxDB 1.x + Grafana — Docker Compose Stack

## Структура файлов

```
.
├── docker-compose.yml
├── .env                          ← секреты (не коммитить в git!)
├── .gitignore
├── influxdb/
│   ├── influxdb.conf             ← конфиг InfluxDB
│   └── init-retention.sh         ← устанавливает политику хранения 60 дней
└── grafana/
    └── provisioning/
        ├── datasources/
        │   └── influxdb.yml      ← автоматическое подключение InfluxDB
        └── dashboards/
            └── dashboard.yml     ← провайдер дашбордов
```

## Быстрый старт

### 1. Заполните секреты

Откройте `.env` и замените все значения `change_me_*` на реальные:

```bash
nano .env
```

### 2. Запустите стек

```bash
docker compose up -d
```

### 3. Проверьте статус

```bash
docker compose ps
docker compose logs -f
```

## Порты

| Сервис   | Хост | Назначение                        |
|----------|------|-----------------------------------|
| InfluxDB | 8086 | HTTP API — принимает метрики извне |
| Grafana  | 3000 | Web UI — доступен по http://       |

## Хранение данных

| Сервис   | Volume         | Ретеншн                                  |
|----------|----------------|------------------------------------------|
| InfluxDB | influxdb_data  | 60 дней (политика `60d_policy`)          |
| Grafana  | grafana_data   | Datasource сам ограничен теми же 60 днями |

## Примеры записи данных в InfluxDB

```bash
# Line Protocol через curl
curl -i -XPOST "http://localhost:8086/write?db=metrics" \
  -u "admin:your_password" \
  --data-binary 'cpu_load,host=server01 value=0.64 1609459200000000000'

# Через Telegraf (telegraf.conf)
[[outputs.influxdb]]
  urls = ["http://localhost:8086"]
  database = "metrics"
  username = "admin"
  password = "your_password"
```

## Grafana

Откройте в браузере: **http://your-server-ip:3000**

Логин и пароль берутся из `.env` → `GF_SECURITY_ADMIN_USER` / `GF_SECURITY_ADMIN_PASSWORD`.

Datasource `InfluxDB` уже добавлен автоматически через provisioning.

## Управление

```bash
# Остановить
docker compose down

# Остановить и удалить данные (внимание — удалит volumes!)
docker compose down -v

# Обновить образы
docker compose pull && docker compose up -d
```

## Безопасность

- `.env` добавлен в `.gitignore` — не попадёт в репозиторий.
- Пароли передаются через переменные окружения, не зашиты в `docker-compose.yml`.
- InfluxDB использует аутентификацию — анонимная запись отключена.
- Grafana подключается к InfluxDB через read-only пользователя (`grafana_reader`).
- Сервисы общаются по изолированной внутренней сети `monitoring`.