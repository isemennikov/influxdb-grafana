#!/bin/bash
# This script runs once on first startup to configure the database
# and set a 60-day retention policy.
set -e

# Wait for InfluxDB to be ready
until influx -host localhost -port 8086 \
      -username "${INFLUXDB_ADMIN_USER}" \
      -password "${INFLUXDB_ADMIN_PASSWORD}" \
      -execute "SHOW DATABASES" > /dev/null 2>&1; do
  echo "Waiting for InfluxDB to be ready..."
  sleep 2
done

echo "InfluxDB is ready. Applying 60-day retention policy..."

# Set the DEFAULT retention policy on the metrics database to 60 days
influx -host localhost -port 8086 \
  -username "${INFLUXDB_ADMIN_USER}" \
  -password "${INFLUXDB_ADMIN_PASSWORD}" \
  -database "${INFLUXDB_DB}" \
  -execute "CREATE RETENTION POLICY \"60d_policy\" ON \"${INFLUXDB_DB}\" DURATION 60d REPLICATION 1 DEFAULT"

# Drop the default autogen policy (infinite retention)
influx -host localhost -port 8086 \
  -username "${INFLUXDB_ADMIN_USER}" \
  -password "${INFLUXDB_ADMIN_PASSWORD}" \
  -database "${INFLUXDB_DB}" \
  -execute "DROP RETENTION POLICY \"autogen\" ON \"${INFLUXDB_DB}\"" || true

if [ -n "${INFLUXDB_READ_USER:-}" ] && [ -n "${INFLUXDB_READ_USER_PASSWORD:-}" ]; then
  echo "Creating read-only InfluxDB user '${INFLUXDB_READ_USER}'..."
  influx -host localhost -port 8086 \
    -username "${INFLUXDB_ADMIN_USER}" \
    -password "${INFLUXDB_ADMIN_PASSWORD}" \
    -execute "CREATE USER \"${INFLUXDB_READ_USER}\" WITH PASSWORD '${INFLUXDB_READ_USER_PASSWORD}'" || true
  influx -host localhost -port 8086 \
    -username "${INFLUXDB_ADMIN_USER}" \
    -password "${INFLUXDB_ADMIN_PASSWORD}" \
    -database "${INFLUXDB_DB}" \
    -execute "GRANT READ ON \"${INFLUXDB_DB}\" TO \"${INFLUXDB_READ_USER}\""
fi

echo "Retention policy applied: 60 days on database '${INFLUXDB_DB}'."