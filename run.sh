#!/usr/bin/env bash
set -euo pipefail

echo "[1/2] Fetching data..."
python fetch_data.py

echo "[2/2] Starting app..."
python app.py
