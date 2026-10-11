#!/usr/bin/env bash
# traffic mock 冒烟验证(态势大屏端点,Issue #52;验收可复跑)。
# harness 八端点冒烟已随 2026-10-11 架构裁定移除;新接口面定稿后按新面重写本脚本。
# 用法:dev server 运行中(默认 mock 模式)执行 bash scripts/verify-mock.sh
#   BASE=http://localhost:5173 bash scripts/verify-mock.sh
set -u
BASE="${BASE:-http://localhost:5173}"
fail=0
say() { printf '%s\n' "$*"; }
ck() { # ck <名称> <实际> <期望子串>
  if [ "$2" != "${2/$3/}" ] || [ -z "$3" ]; then say "PASS  $1"; else say "FAIL  $1 (got: $2)"; fail=1; fi
}
code() { curl -s -m 5 -o /dev/null -w '%{http_code}' "$@"; }

say "== [1] GET /api/traffic/segments 快照 =="
S=$(curl -s -m 5 "$BASE/api/traffic/segments")
ck segments-shape "$S" '"segments"'
ck segments-sim "$S" '"is_simulated":true'
ck segments-ts "$S" '"ts"'
say "路段数: $(printf '%s' "$S" | grep -o '"segment_id"' | wc -l)"

say "== [2] GET /api/traffic/segments/SEG-001 详情 =="
D=$(curl -s -m 5 "$BASE/api/traffic/segments/SEG-001")
ck segment-id "$D" '"segment_id":"SEG-001"'
ck segment-level "$D" '"level"'

say "== [3] GET /api/traffic/segments/SEG-9999 → 404 =="
ck segment-404 "$(code "$BASE/api/traffic/segments/SEG-9999")" '404'

say "== [4] GET /api/traffic/vehicles =="
V=$(curl -s -m 5 "$BASE/api/traffic/vehicles")
ck vehicles-shape "$V" '"vehicles"'
ck vehicles-sim "$V" '"is_simulated":true'

say "== [5] POST /api/traffic/route/recommend =="
R=$(curl -s -m 5 -X POST "$BASE/api/traffic/route/recommend" -H 'Content-Type: application/json' \
  -d '{"session_id":"vu-verify","location":{"segment_id":"SEG-001","offset_m":100}}')
ck recommend-arrival "$R" '"arrival_route"'
ck recommend-reservation "$R" '"reservation"'

say "== [6] GET /api/traffic/stream(SSE 首帧) =="
SS=$(curl -s -m 5 -N --max-time 3 "$BASE/api/traffic/stream" | head -c 600)
ck stream-event "$SS" 'traffic_snapshot'

say "== [7] 表外端点 → 404 =="
ck unknown "$(code "$BASE/api/foo")" '404'

say ""
if [ "$fail" = "0" ]; then say "ALL PASS"; else say "HAS FAILURES"; fi
exit "$fail"
