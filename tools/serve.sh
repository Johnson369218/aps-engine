#!/bin/bash
# 参考试点 APS 引擎服务 启/停/状态（默认 127.0.0.1:8077，仅本机/内网）
# 用法: tools/serve.sh start|stop|status|restart [port]
cd "$(dirname "$0")/.."        # 到 aps-engine/
PORT="${2:-8077}"
PID_FILE="output/.aps-server.pid"
LOG="output/aps-server.log"
PY=".venv/bin/python"

start() {
  if [ -f "$PID_FILE" ] && kill -0 "$(cat "$PID_FILE")" 2>/dev/null; then
    echo "已在运行 (pid $(cat "$PID_FILE"), port $PORT)"; return 0
  fi
  nohup "$PY" -m uvicorn aps-engine.server.app:app --host 127.0.0.1 --port "$PORT" \
    > "$LOG" 2>&1 &
  echo $! > "$PID_FILE"
  echo "已启动 (pid $(cat "$PID_FILE"), port $PORT) | 日志 $LOG"
}
stop() {
  if [ -f "$PID_FILE" ] && kill -0 "$(cat "$PID_FILE")" 2>/dev/null; then
    kill "$(cat "$PID_FILE")" && rm -f "$PID_FILE" && echo "已停止"
  else
    echo "未在运行"; rm -f "$PID_FILE"
  fi
}
status() {
  if [ -f "$PID_FILE" ] && kill -0 "$(cat "$PID_FILE")" 2>/dev/null; then
    echo "运行中 (pid $(cat "$PID_FILE"), port $PORT)"; curl -s "http://127.0.0.1:$PORT/api/health" || true
  else
    echo "未运行"
  fi
}
case "${1:-status}" in
  start) start;; stop) stop;; restart) stop; sleep 1; start;;
  status) status;; *) echo "用法: $0 start|stop|status|restart [port]";;
esac
