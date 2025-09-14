#!/bin/bash -e

if [ $EUID != 0 ]; then
    echo 'Script must be run as root.'
    exit 1
fi

PROJECT_ROOT=$(CDPATH='' cd -- "$(dirname -- "$(realpath "$0")")/.." && pwd)

SYSD_DIR='/etc/systemd/system'
UNITS=("status-report.service" "status-report.timer")

for unit in "${UNITS[@]}"; do
    (set -x; cp "$PROJECT_ROOT/basic-report/$unit" "$SYSD_DIR/$unit")
done;

conf_dir="$SYSD_DIR/${UNITS[0]}.d"
conf_file="${UNITS[0]}.conf"
set -x
mkdir -p "$conf_dir"
cp "$PROJECT_ROOT/basic-report/$conf_file" "$conf_dir/$conf_file"
systemctl daemon-reload
systemctl enable --now "${UNITS[1]}"
