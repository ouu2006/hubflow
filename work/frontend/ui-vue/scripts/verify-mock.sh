#!/usr/bin/env bash
# mock 八端点冒烟验证(04 任务书 VU-1/VU-2;验收可复跑)。
# 用法:dev server 运行中(默认 mock 模式)执行 bash scripts/verify-mock.sh
#   BASE=http://localhost:5173 bash scripts/verify-mock.sh
# error 注入分支验证:VITE_MOCK_ERROR=1 重启 dev 后,加 ERROR_INJECT=1 复跑本脚本。
set -u
BASE="${BASE:-http://localhost:5173}"
ERROR_INJECT="${ERROR_INJECT:-0}"
fail=0
say() { printf '%s\n' "$*"; }
ck() { # ck <名称> <实际> <期望子串>
  if [ "$2" != "${2/$3/}" ] || [ -z "$3" ]; then say "PASS  $1"; else say "FAIL  $1 (got: $2)"; fail=1; fi
}

say "== [1] GET /api/health =="
H=$(curl -s -m 5 "$BASE/api/health")
ck health "$H" '"kernel"'
if [ "$ERROR_INJECT" = "1" ]; then ck health-down "$H" '"kernel":"down"'; else ck health-up "$H" '"kernel":"up"'; fi

say "== [2] POST /api/auth/login 空凭据 → 401 =="
ck login-empty "$(curl -s -m 5 -o /dev/null -w '%{http_code}' -X POST "$BASE/api/auth/login" -H 'Content-Type: application/json' -d '{}')" '401'

say "== [3] POST /api/auth/login 正常 =="
LOGIN=$(curl -s -m 5 -X POST "$BASE/api/auth/login" -H 'Content-Type: application/json' -d '{"user":"admin","password":"admin"}')
ck login "$LOGIN" '"token":"'
TOKEN=$(printf '%s' "$LOGIN" | sed -E 's/.*"token":"([^"]+)".*/\1/')
AUTH="Authorization: Bearer $TOKEN"

say "== [4] 受保护端点缺 token → 401 =="
ck noauth "$(curl -s -m 5 -o /dev/null -w '%{http_code}' "$BASE/api/kb/documents")" '401'

say "== [5] POST /api/sessions =="
SESS=$(curl -s -m 5 -X POST "$BASE/api/sessions" -H "$AUTH")
ck session "$SESS" '"session_id":"'
SID=$(printf '%s' "$SESS" | sed -E 's/.*"session_id":"([^"]+)".*/\1/')

say "== [6] POST /api/sessions/{id}/chat SSE 假流 =="
# 注意:中文请求体走 --data-binary @file(Windows 原生 curl 的 ANSI argv 会把命令行 UTF-8 转码为 GBK)
printf '{"text":"内核桥接协议的帧限制是多少"}' > "$TMP/vu-chat.json"
SSE=$(curl -s -m 30 -N -X POST "$BASE/api/sessions/$SID/chat" -H "$AUTH" -H 'Content-Type: application/json' --data-binary @"$TMP/vu-chat.json")
rm -f "$TMP/vu-chat.json"
say "事件分布: $(printf '%s' "$SSE" | grep -o '^event: [a-z]*' | sort | uniq -c | tr '\n' ' ')"
ck sse-delta "$SSE" 'event: delta'
if [ "$ERROR_INJECT" = "1" ]; then
  ck sse-error "$SSE" 'event: error'
else
  ck sse-usage "$SSE" 'event: usage'
  ck sse-finish "$SSE" 'event: finish'
fi
AID=$(printf '%s' "$SSE" | grep -o '"answer_id":"[^"]*"' | head -1 | sed -E 's/.*"answer_id":"([^"]+)".*/\1/')
say "answer_id: ${AID:-<无>}"
# 关键词回显断言:delta 字级分块会把词打断,须重组全部 text 增量后再匹配
ANSWER=$(printf '%s' "$SSE" | grep -o '"text":"[^"]*"' | sed -E 's/"text":"(.*)"/\1/' | tr -d '\n')
ck sse-kw-echo "$ANSWER" '内核桥接'

say "== [7] GET /api/kb/documents 种子 6 条 =="
DOCS=$(curl -s -m 5 "$BASE/api/kb/documents" -H "$AUTH")
ck docs-seed "$DOCS" 'doc-0001'
say "count: $(printf '%s' "$DOCS" | grep -o '"doc_id"' | wc -l)"

if [ "$ERROR_INJECT" = "1" ]; then
  # 注入模式下 upload/delete/trace 通道预期 500(上文已见 MOCK_INJECTED),正向断言仅正常态复跑
  say "== [8-11] 注入模式:upload/delete/trace 正向断言跳过(500 即预期)=="
else
say "== [8] POST /api/kb/documents 上传(小文件)+ 版本态收敛 =="
TMP="${TMPDIR:-/tmp}"
printf 'mock upload content for verify\n' > "$TMP/vu-upload.txt"
UP=$(curl -s -m 15 -X POST "$BASE/api/kb/documents" -H "$AUTH" -F "file=@$TMP/vu-upload.txt")
ck upload "$UP" '"doc_id":"'
ck upload-stored "$UP" '"stored_path":"'
DID=$(printf '%s' "$UP" | sed -E 's/.*"doc_id":"([^"]+)".*/\1/')
say "uploaded: $UP"
sleep 0.3
ST0=$(curl -s -m 5 "$BASE/api/kb/documents" -H "$AUTH" | grep -o "\"doc_id\":\"$DID\"[^}]*" | grep -o '"status":"[a-z]*"')
ck upload-processing "$ST0" '"status":"processing"'
sleep 3
ST1=$(curl -s -m 5 "$BASE/api/kb/documents" -H "$AUTH" | grep -o "\"doc_id\":\"$DID\"[^}]*" | grep -o '"status":"[a-z]*"')
ck upload-ready "$ST1" '"status":"ready"'

say "== [9] 同名重传 → 版本递增 =="
curl -s -m 15 -X POST "$BASE/api/kb/documents" -H "$AUTH" -F "file=@$TMP/vu-upload.txt" > /dev/null
sleep 3
VER=$(curl -s -m 5 "$BASE/api/kb/documents" -H "$AUTH" | grep -o '"name":"vu-upload.txt","version":[0-9]*' | tail -1)
ck upload-version-bump "$VER" '"version":2'

say "== [10] DELETE /api/kb/documents/{id} → 204;再删 → 404 =="
ck delete-204 "$(curl -s -m 5 -o /dev/null -w '%{http_code}' -X DELETE "$BASE/api/kb/documents/$DID" -H "$AUTH")" '204'
ck delete-404 "$(curl -s -m 5 -o /dev/null -w '%{http_code}' -X DELETE "$BASE/api/kb/documents/$DID" -H "$AUTH")" '404'

say "== [11] GET /api/answers/{id}/trace =="
if [ -n "${AID:-}" ]; then
  TR=$(curl -s -m 5 "$BASE/api/answers/$AID/trace" -H "$AUTH")
  ck trace-list "$TR" '"doc_id"'
  ck trace-snippet "$TR" '"snippet"'
  ck trace-score "$TR" '"score"'
  ck trace-source "$TR" '"source"'
  say "首条: $(printf '%s' "$TR" | grep -o '"snippet":"[^"]\{0,40\}' | head -1)"
else
  say "SKIP trace(无 answer_id)"
  fail=1
fi
fi

say "== [12] 冻结表外端点 → 404 =="
ck unknown "$(curl -s -m 5 "$BASE/api/foo" -H "$AUTH")" '冻结表外'

if [ "$ERROR_INJECT" != "1" ]; then
  say "== [13] >16MB 上传护栏 → 413 =="
  head -c 17825792 /dev/zero > "$TMP/vu-big.bin"
  ck oversize "$(curl -s -m 60 -o /dev/null -w '%{http_code}' -X POST "$BASE/api/kb/documents" -H "$AUTH" -F "file=@$TMP/vu-big.bin")" '413'
  rm -f "$TMP/vu-big.bin"
fi
rm -f "$TMP/vu-upload.txt"

say ""
if [ "$fail" = "0" ]; then say "ALL PASS (ERROR_INJECT=$ERROR_INJECT)"; else say "HAS FAILURES (ERROR_INJECT=$ERROR_INJECT)"; fi
exit "$fail"
