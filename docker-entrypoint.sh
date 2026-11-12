#!/bin/sh
set -e

echo "[KinetiQ Demo] Waiting for MySQL service to become ready..."
while ! python -c "
import os, sys, pymysql
host = os.getenv('DB_HOST', 'db')
port = int(os.getenv('DB_PORT', '3306'))
user = os.getenv('DB_USER', 'kinetiq_app')
pwd = os.getenv('DB_PASSWORD', 'kinetiq_demo_pwd')
db = os.getenv('DB_NAME', 'crm_saas_db')
try:
    conn = pymysql.connect(host=host, port=port, user=user, password=pwd, database=db, connect_timeout=3)
    conn.close()
    sys.exit(0)
except Exception:
    sys.exit(1)
"; do
    sleep 2
done

echo "[KinetiQ Demo] MySQL is ready! Applying database migrations..."
python manage.py migrate --noinput

echo "[KinetiQ Demo] Seeding demo environment with test businesses, users, deals, and invoices..."
python manage.py seed_demo

echo "[KinetiQ Demo] Starting KinetiQ Application Server on port 8000..."
exec python manage.py runserver 0.0.0.0:8000

