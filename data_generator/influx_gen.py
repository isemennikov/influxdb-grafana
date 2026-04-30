#!/usr/bin/env python3
"""
Генератор случайных данных CPU load в InfluxDB.
Данные берутся из .env файла, который лежит в корне проекта (на уровень выше скрипта).
"""

import requests
import random
import time
import sys
import argparse
import os
from pathlib import Path
from dotenv import load_dotenv

# Определяем корень проекта (там, где находится .env)
project_root = Path(__file__).parent.parent
env_path = project_root / '.env'
load_dotenv(dotenv_path=env_path)

# Конфигурация из переменных окружения
INFLUX_URL = os.getenv("INFLUXDB_URL", "http://localhost:8086")
DATABASE = os.getenv("INFLUXDB_DATABASE", "metrics")
USER = os.getenv("INFLUXDB_USER", "admin")
PASSWORD = os.getenv("INFLUXDB_ADMIN_PASSWORD")

def check_config():
    if not PASSWORD:
        print("Ошибка: переменная окружения INFLUXDB_PASSWORD не задана.", file=sys.stderr)
        print(f"Проверьте наличие файла {env_path} и наличие в нём INFLUXDB_PASSWORD=...", file=sys.stderr)
        sys.exit(1)

def generate_points(num_points: int, start_timestamp_ns: int = None, step_ms: int = 1000):
    if start_timestamp_ns is None:
        start_timestamp_ns = int(time.time() * 1e9)
    for i in range(num_points):
        value = random.uniform(0.0, 100.0)
        timestamp = start_timestamp_ns + i * step_ms * 1_000_000
        line = f"cpu_load,host=test value={value:.6f} {timestamp}"
        yield line

def write_points(points, batch_size=5000):
    auth = (USER, PASSWORD)
    write_url = f"{INFLUX_URL}/write?db={DATABASE}"
    session = requests.Session()
    session.auth = auth
    total_sent = 0
    batch = []
    for line in points:
        batch.append(line)
        if len(batch) >= batch_size:
            data = "\n".join(batch)
            resp = session.post(write_url, data=data)
            if resp.status_code != 204:
                print(f"Ошибка записи: {resp.status_code} - {resp.text}", file=sys.stderr)
                sys.exit(1)
            total_sent += len(batch)
            print(f"Отправлено {total_sent} точек...", end='\r')
            batch = []
    if batch:
        data = "\n".join(batch)
        resp = session.post(write_url, data=data)
        if resp.status_code != 204:
            print(f"Ошибка записи: {resp.status_code} - {resp.text}", file=sys.stderr)
            sys.exit(1)
        total_sent += len(batch)
        print(f"Отправлено {total_sent} точек...")
    return total_sent

def check_data(limit=5):
    auth = (USER, PASSWORD)
    query_url = f"{INFLUX_URL}/query"
    params = {
        'db': DATABASE,
        'q': f'SELECT value FROM cpu_load WHERE host=\'test\' LIMIT {limit}'
    }
    resp = requests.get(query_url, params=params, auth=auth)
    if resp.status_code != 200:
        print(f"Ошибка запроса: {resp.status_code} - {resp.text}", file=sys.stderr)
        return False
    data = resp.json()
    results = data.get('results', [])
    if not results:
        print("Нет результатов")
        return False
    series = results[0].get('series', [])
    if not series:
        print("Таблица пуста (нет данных)")
        return False
    print("\n--- Проверка данных ---")
    for row in series[0].get('values', []):
        print(f"timestamp: {row[0]}, value: {row[1]}")
    return True

def estimate_size(num_points):
    return num_points * 50

def main():
    parser = argparse.ArgumentParser(description="Генератор случайных данных для InfluxDB")
    parser.add_argument('--points', type=int, default=100000,
                        help='Количество генерируемых точек (по умолчанию 100 000, ~5 МБ)')
    parser.add_argument('--batch-size', type=int, default=5000,
                        help='Размер пачки для записи (по умолчанию 5000)')
    parser.add_argument('--step-ms', type=int, default=1000,
                        help='Шаг времени между точками в миллисекундах (по умолчанию 1000)')
    args = parser.parse_args()

    check_config()

    estimated_mb = estimate_size(args.points) / (1024 * 1024)
    print(f"Планируется сгенерировать {args.points} точек")
    print(f"Примерный объём данных: {estimated_mb:.2f} МБ")
    if estimated_mb > 100:
        print("Предупреждение: объём может превысить 100 МБ. Уменьшите количество точек.")
        response = input("Продолжить? (y/N): ")
        if response.lower() != 'y':
            sys.exit(0)

    print("Генерация и запись данных...")
    start_time = time.time()
    points = generate_points(args.points, step_ms=args.step_ms)
    total = write_points(points, batch_size=args.batch_size)
    elapsed = time.time() - start_time
    print(f"\nЗаписано {total} точек за {elapsed:.2f} сек")

    check_data(limit=5)

if __name__ == "__main__":
    main()