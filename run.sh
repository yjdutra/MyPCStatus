#!/usr/bin/env bash
# Sobe o MyPCStatus a partir da pasta do projeto, sem depender do cwd.
cd "$(dirname "$(readlink -f "$0")")" || exit 1
exec python3 -m mypcstatus "$@"
