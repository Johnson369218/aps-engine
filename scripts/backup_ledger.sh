#!/bin/bash
# E4 台账备份：data/ledger/*.db → data/backup/，保留 7 份（滚动）。
set -euo pipefail
WS="${APS_WS:-/Users/johnsonbai/Desktop/生产调度}"
SRC="$WS/data/ledger"; DST="$WS/data/backup"
[ -d "$SRC" ] || { echo "无台账目录，跳过"; exit 0; }
mkdir -p "$DST"
STAMP=$(date +%Y%m%d-%H%M%S)
for db in "$SRC"/*.db; do
  [ -e "$db" ] || continue
  cp "$db" "$DST/$(basename "$db" .db).$STAMP.db"
done
# 保留 7 份（按文件名时间戳排序，删除更旧的）
ls -1t "$DST"/*.db 2>/dev/null | tail -n +8 | xargs -r rm -f
echo "备份完成 -> ${DST} (保留 7 份)"
