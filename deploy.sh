#!/usr/bin/env bash
set -euo pipefail

cd /app/bidpilot/repo
git pull --ff-only origin master

cd /app/bidpilot
docker compose up -d --build
