# CPU Load Generator — host venv setup

Генерирует синтетические метрики CPU и отправляет их в **Telegraf**
по HTTP (InfluxDB line protocol) на `localhost:8186`.

## Требования

- Python 3.10+
- Запущенный стек (`docker compose up -d`)

## Установка venv (один раз)

```bash
cd data_generator

python3 -m venv venv
source venv/bin/activate          # Linux / macOS
# venv\Scripts\activate           # Windows

pip install -r requirements.txt   # зависимостей нет, но хорошая практика
```

## Запуск

```bash
# Активировать окружение (если ещё не активировано)
source venv/bin/activate

# Запустить с настройками по умолчанию (5 сек между батчами, бесконечно)
python cpu_generator.py

# Быстрый всплеск — 300 батчей каждую секунду
python cpu_generator.py --interval 1 --runs 300

# Ограничить объём данных
python cpu_generator.py --max-mb 50

# Своя цель, свои хосты
python cpu_generator.py \
    --url http://localhost:8186/telegraf \
    --hosts srv-01,srv-02,srv-03 \
    --cores 4 \
    --interval 2

# Несколько окон терминала одновременно — данные суммируются в InfluxDB
```

## Аргументы

| Аргумент     | По умолчанию                          | Описание                              |
|--------------|---------------------------------------|---------------------------------------|
| `--url`      | `http://localhost:8186/telegraf`      | URL Telegraf HTTP listener            |
| `--interval` | `5`                                   | Секунд между батчами                  |
| `--runs`     | `0` (∞)                               | Кол-во батчей; 0 = бесконечно         |
| `--hosts`    | `web-01,web-02,db-01,cache-01`        | Имена хостов через запятую            |
| `--cores`    | `8`                                   | Ядер CPU на хост                      |
| `--max-mb`   | `0` (без лимита)                      | Остановить после N МБ; 0 = без лимита |

## Что генерируется

Каждый батч — строки line protocol вида:

```
cpu_load,host=web-01,core=cpu0 usage_percent=67.3,user=42.1,system=8.2,iowait=3.1,idle=32.7 1700000000000000000
```

Данные поступают в цепочку:

```
venv script → localhost:8186 → Telegraf → InfluxDB:8086 → Grafana
```

## Grafana — как увидеть данные

1. Открыть `http://localhost:3000`
2. **Explore** → datasource **InfluxDB**
3. Запрос:
   ```influxql
   SELECT mean("usage_percent")
   FROM "cpu_load"
   WHERE $timeFilter
   GROUP BY time($__interval), "host"
   ```
4. Или в **Dashboard → Add panel** — выбрать measurement `cpu_load`.

## Остановка

`Ctrl+C` — скрипт выведет итоговую статистику и завершится чисто.