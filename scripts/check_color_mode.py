"""hubflow 颜色模式 4 档门禁（8 项，Issue IKRK8B）。改完前端跑一遍，全绿才算完。

为什么要这个门禁：颜色模式从 2 档（congestion / flow）扩成 4 档
（congestion / flow / custom / gray）以后，最容易回退的三件事是——
  1. 类型/白名单只改了 type 没改 parse，或把 4 值写成了 5 处各一份；
  2. 「路线默认不出」被一次「方便调试」的 loadRouteOptions() 复活，
     或者 mock 模式又偷偷把站点包骨架路线喂回来（前后端口径不一致）；
  3. 压灰（#C9CDD4，本档不表示路况）被写成了「无流量数据」灰（#8B8B8B，数据不可用）。
本脚本用静态断言把这三点钉住，不跑浏览器、不依赖构建产物。

用法：python scripts/check_color_mode.py
退出码 0 = 全绿，1 = 有失败项。
"""
import os
import re
import sys

# 相对仓库定位，不写死本机绝对路径（换机器 / 换盘符都能跑）——与 scripts/frontend_gate.py 同款写法
ROOT = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "work", "frontend")
VUE = os.path.join(ROOT, "ui-vue", "src")
FLOW = os.path.join(VUE, "shared", "flow.ts")
DASH = os.path.join(VUE, "views", "dashboard", "DashboardView.vue")
MOCK = os.path.join(VUE, "mock", "traffic.ts")
README = os.path.join(ROOT, "README.md")

FOUR = ["'congestion'", "'flow'", "'custom'", "'gray'"]
# 四档的用户可见档名（口径唯一来源是 flow.ts 的 COLOR_MODE_META）
FOUR_NAMES = ["决策拥堵版", "纯车流量版", "自定义路线版", "灰底版"]


def rel(p):
    return os.path.relpath(p, ROOT).replace("\\", "/")


def read(p):
    if not os.path.exists(p):
        return None
    return open(p, encoding="utf-8").read()


def strip_comments(src):
    """去掉 // 与 /* */ 注释，只留真正的代码与字符串（同 frontend_gate.py 的规则）。

    必须去注释：我们在注释里大段记录「为什么不再自动出路线」「mock 为什么不注入骨架」，
    按原文查会把说明文字当成代码，门禁就变成假红。
    """
    out = []
    i = 0
    n = len(src)
    while i < n:
        c = src[i]
        if c == "/" and i + 1 < n and src[i + 1] == "/":
            while i < n and src[i] != "\n":
                i += 1
        elif c == "/" and i + 1 < n and src[i + 1] == "*":
            i += 2
            while i + 1 < n and not (src[i] == "*" and src[i + 1] == "/"):
                if src[i] == "\n":
                    out.append("\n")  # 块注释里的换行要保留，后面的行号才不错位
                i += 1
            i += 2
        elif c in "'\"`":
            q = c
            out.append(c)
            i += 1
            while i < n:
                out.append(src[i])
                if src[i] == "\\":
                    i += 1
                    if i < n:
                        out.append(src[i])
                elif src[i] == q:
                    i += 1
                    break
                i += 1
        else:
            out.append(c)
            i += 1
    return "".join(out)


def line_of(src, pattern):
    m = re.search(pattern, src, re.M)
    if not m:
        return None
    return src.count("\n", 0, m.start()) + 1


def has_all(hay, needles):
    return [x for x in needles if x not in hay]


# ── 1/8 类型 4 值 ───────────────────────────────────────────────────────────
def check_type(flow, _dash, _mock, _readme, _mockraw):
    bad = []
    m = re.search(r"export type ColorMode\s*=\s*([^\n]+)", flow)
    if not m:
        return ["shared/flow.ts 找不到 `export type ColorMode = ...`"]
    body = m.group(1)
    missing = has_all(body, FOUR)
    if missing:
        bad.append(f"ColorMode 类型缺值：{', '.join(missing)}（当前：{body.strip()}）")
    m2 = re.search(r"export const COLOR_MODES[^\n]*=\s*\[([^\]]*)\]", flow)
    if not m2:
        bad.append("shared/flow.ts 找不到 COLOR_MODES 常量（档位顺序的唯一来源）")
    else:
        got = re.findall(r"'([a-z]+)'", m2.group(1))
        if got != ["congestion", "flow", "custom", "gray"]:
            bad.append(f"COLOR_MODES 顺序/内容不对：{got}（应为 congestion, flow, custom, gray）")
    return bad


# ── 2/8 parse 白名单 4 值 + 静默回落 congestion ──────────────────────────────
def check_parse(flow, _dash, _mock, _readme, _mockraw):
    bad = []
    m = re.search(r"export function parseColorMode\([^)]*\)[^{]*\{(.*?)\n\}", flow, re.S)
    if not m:
        return ["shared/flow.ts 找不到 `export function parseColorMode(...)`"]
    body = m.group(1)
    if "COLOR_MODES" not in body:
        bad.append("parseColorMode 没有用 COLOR_MODES 白名单（别自己再写一份 4 值数组）")
    if not re.search(r"export const DEFAULT_COLOR_MODE[^\n]*=\s*'congestion'", flow):
        bad.append("DEFAULT_COLOR_MODE 不是 'congestion'（默认档必须是决策拥堵版）")
    if not re.search(r"parseColorMode\(value\)\s*\?\?\s*DEFAULT_COLOR_MODE", flow):
        bad.append("resolveColorMode 没有「坏值/旧值静默回落 DEFAULT_COLOR_MODE」的 `?? DEFAULT_COLOR_MODE`")
    if not re.search(r"export function resolveColorMode", flow):
        bad.append("shared/flow.ts 缺 resolveColorMode（解析+回落的唯一入口）")
    return bad


# ── 3/8 档位 UI 4 个按钮 + 选中态 + aria-pressed ─────────────────────────────
def check_buttons(flow, dash, _mock, _readme, _mockraw):
    bad = []
    if not re.search(r'v-for="m in COLOR_MODES"', dash):
        bad.append("DashboardView.vue 档位按钮不是 `v-for=\"m in COLOR_MODES\"`（模板里另写数组就会漂）")
    if not re.search(r':aria-pressed="colorMode === m"', dash):
        bad.append("档位按钮缺 `:aria-pressed=\"colorMode === m\"`（可点但读屏不可读）")
    if "cm-note" not in dash:
        bad.append("档位切换条缺 `.cm-note`（每档「表示什么/不表示什么」一句话）")
    missing = has_all(flow, FOUR_NAMES)
    if missing:
        bad.append(f"flow.ts 的档名缺：{', '.join(missing)}（COLOR_MODE_META.name 必须是这 4 个）")
    return bad


# ── 4/8 默认档 = congestion（类型、storage 初值、按钮顺序都对齐） ────────────
def check_default(flow, dash, _mock, _readme, _mockraw):
    bad = []
    if "DEFAULT_COLOR_MODE" not in dash:
        bad.append("DashboardView.vue 没有引用 DEFAULT_COLOR_MODE（初值写死 'flow'/'custom' 就会偏档）")
    ln = line_of(dash, r"const colorMode = ref<\s*ColorMode\s*>\(\s*initialColorMode")
    if ln is None and not re.search(r"initialColorMode", dash):
        bad.append("DashboardView.vue 找不到颜色模式的初始值（应当来自 initialColorMode）")
    if re.search(r"const colorMode = ref<\s*ColorMode\s*>\('(flow|custom|gray)'\)", dash):
        bad.append("颜色模式初值被写死成非默认档（必须是 DEFAULT_COLOR_MODE / congestion）")
    if not re.search(r"export const DEFAULT_COLOR_MODE[^\n]*=\s*'congestion'", flow):
        bad.append("DEFAULT_COLOR_MODE 不是 'congestion'")
    return bad


# ── 5/8 压灰判据里有 customActive 条件，且压灰灰 ≠ 数据不可用灰 ──────────────
def check_dim(flow, dash, _mock, _readme, _mockraw):
    bad = []
    m = re.search(r"export const MODE_DIM_GRAY\s*=\s*'(#[0-9A-Fa-f]{6})'", flow)
    if not m:
        bad.append("flow.ts 缺 MODE_DIM_GRAY（本档不表示路况的压灰）")
    elif m.group(1).upper() != "#C9CDD4":
        bad.append(f"MODE_DIM_GRAY = {m.group(1)}，应为 #C9CDD4（#8B8B8B 是「数据不可用」，别混）")
    if not re.search(r"const customActive = computed<boolean>\(\(\) =>[^\n]*'custom'[^\n]*customRouteEnabled", dash):
        bad.append("DashboardView.vue 的 customActive 不是 `colorMode==='custom' && customRouteEnabled`（联动唯一判据）")
    if not re.search(r"const isMuted\s*=", dash) or "MODE_DIM_GRAY" not in dash:
        bad.append("DashboardView.vue 压灰分支（isMuted / MODE_DIM_GRAY）缺失：non-①② 档没有压灰口径")
    if "本档不表示路况" not in flow:
        bad.append("flow.ts 缺 MODE_NO_TRAFFIC_NOTE 文案「本档不表示路况」（③④ 档面板必须标出来）")
    return bad


# ── 6/8 路线默认不出：只有 customActive 才取数 / 才画 ───────────────────────
def check_route_default(flow, dash, _mock, _readme, _mockraw):
    bad = []
    # 取数入口必须在 customActive 闸内：`if (customActive.value) void loadRouteOptions()`
    gated = re.findall(r"if \(customActive\.value\) void loadRouteOptions\(\)", dash)
    if not gated:
        bad.append("DashboardView.vue 没有 `if (customActive.value) void loadRouteOptions()` 闸（进站/切站必须按需取）")
    # 无条件的裸调用只允许出现在 setCustomRouteEnabled(true) 分支里（用户主动开第三档），
    # 出现在 onMounted / 切站 watch 里就等于「进站默认又画线」
    span = re.search(r"function setCustomRouteEnabled\([\s\S]*?\n\}", dash)
    lo, hi = (span.start(), span.end()) if span else (-1, -1)
    for m in re.finditer(r"^[ \t]*void loadRouteOptions\(\)[ \t]*$", dash, re.M):
        if not (lo <= m.start() < hi):
            ln = dash.count("\n", 0, m.start()) + 1
            bad.append(
                f"DashboardView.vue:{ln} 存在无条件的 `void loadRouteOptions()`"
                "（只允许在 setCustomRouteEnabled(true) 里，否则路线会默认又画出来）"
            )
    # 进站/切站（onMounted 与车站 watch）里不许再碰路线取数
    mounted = re.search(r"onMounted\(\s*(?:async\s*)?\(\s*\)\s*=>\s*\{([\s\S]*?)\n\}\)", dash)
    if mounted:
        # 门内（`if (customActive.value) void loadRouteOptions()`）允许；门外一律算失败
        body = mounted.group(1).replace("if (customActive.value) void loadRouteOptions()", "")
        for fn in ("loadRouteOptions", "loadRecommend"):
            if fn in body:
                bad.append(f"onMounted 里仍在无条件调 {fn}()（进站应当一条路线都不取）")
    else:
        bad.append("DashboardView.vue 找不到 onMounted(...) 主体，无法断言「进站不取路线」")
    if not re.search(r"const mapRoutes[\s\S]{0,400}?if \(!customActive\.value\) return \[\]", dash):
        bad.append("mapRoutes 没有 `if (!customActive.value) return []`（非自定义档必须传空 routes）")
    if not re.search(r"const mapRouteSteps[\s\S]{0,400}?if \(!customActive\.value\) return \[\]", dash):
        bad.append("mapRouteSteps 没有 `if (!customActive.value) return []`（非自定义档箭头必须空）")
    return bad


# ── 7/8 mock 不再注入站点包骨架路线 ────────────────────────────────────────
def check_mock(_flow, _dash, mock, _readme, _mockraw):
    bad = []
    if mock is None:
        return ["src/mock/traffic.ts 不存在（mock 收口无处校验）"]
    m = re.search(r"(function buildRecommend\(\)[\s\S]*?\n\})", mock, re.S)
    if not m:
        return ["src/mock/traffic.ts 找不到 buildRecommend()"]
    body = m.group(1)
    if not re.search(r"arrival_route:\s*\{[^}]*segments:\s*\[\s*\]", body):
        bad.append("mock buildRecommend 的 arrival_route.segments 不是空数组（又在造假路线）")
    if not re.search(r"alternatives:\s*\[\s*\]", body):
        bad.append("mock buildRecommend 的 alternatives 不是空数组（备选路线又在造假）")
    if not re.search(r"departure_route:\s*\{[^}]*segments:\s*\[\s*\]", body):
        bad.append("mock buildRecommend 的 departure_route.segments 不是空数组")
    # 站点包常量只允许拼请求体 location，不许喂路线
    if re.search(r"\.recommend\.(arrival|departure|alternatives|pickup)", body) or re.search(
        r"RECOMMEND\.(arrival|departure|alternatives)", body
    ):
        bad.append("mock buildRecommend 仍在读站点包的路线常量（只允许读 location_*）")
    return bad


# ── 8/8 README 4 档章节 ────────────────────────────────────────────────────
def check_docs(_flow, _dash, _mock, readme, _mockraw):
    bad = []
    if readme is None:
        return ["work/frontend/README.md 不存在"]
    if "18.6" not in readme or "4 档" not in readme:
        bad.append("README 缺「颜色模式 4 档」小节（18.6）")
    for v in ["`congestion`", "`flow`", "`custom`", "`gray`"]:
        if v not in readme:
            bad.append(f"README 没写颜色模式取值 {v}")
    for c in ["#C9CDD4", "#8B8B8B"]:
        if c not in readme:
            bad.append(f"README 没写两条灰的区别：{c}")
    if "?color=gray" not in readme:
        bad.append("README 没写 `?color=gray` 深链示例")
    return bad


GATES = [
    ("1/8 类型 4 值", check_type),
    ("2/8 parse 白名单 + 回落", check_parse),
    ("3/8 档位 UI 4 键", check_buttons),
    ("4/8 默认档 congestion", check_default),
    ("5/8 压灰口径 customActive", check_dim),
    ("6/8 路线默认不出", check_route_default),
    ("7/8 mock 不注入骨架路线", check_mock),
    ("8/8 README 4 档", check_docs),
]


def main():
    # Windows 控制台默认 cp936，中文断言信息会乱码；一律按 UTF-8 输出
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass
    flow_raw = read(FLOW)
    dash_raw = read(DASH)
    mock_raw = read(MOCK)
    readme = read(README)
    if flow_raw is None or dash_raw is None:
        print("找不到共享前端源文件（flow.ts / DashboardView.vue）—— ROOT 路径配置错误，门禁未生效（假绿）")
        return 1
    # 注释一律剔掉再断言：注释里写着「不再自动出路线」这种话，按原文查会假红
    flow, dash, mock = strip_comments(flow_raw), strip_comments(dash_raw), strip_comments(mock_raw or "")
    print(f"扫描 {rel(FLOW)} / {rel(DASH)} / {rel(MOCK)} / {rel(README)}\n")
    total = 0
    for name, fn in GATES:
        bad = fn(flow, dash, mock, readme, mock_raw)
        mark = "PASS" if not bad else "FAIL"
        desc = {
            "1/8 类型 4 值": "ColorMode = congestion|flow|custom|gray，COLOR_MODES 定序",
            "2/8 parse 白名单 + 回落": "parseColorMode 走 COLOR_MODES，坏值静默回落 congestion",
            "3/8 档位 UI 4 键": "4 个档位按钮 + aria-pressed + 每档一句话",
            "4/8 默认档 congestion": "默认档 = 决策拥堵版（清 localStorage 回①）",
            "5/8 压灰口径 customActive": "压灰 #C9CDD4 ≠ 数据不可用 #8B8B8B，判据 customActive",
            "6/8 路线默认不出": "只有自定义路线档才按需取数/画线，其余档 routes 为空",
            "7/8 mock 不注入骨架路线": "mock buildRecommend 不再回站点包写死的路线",
            "8/8 README 4 档": "README 18.6 写清 4 档 / 两条灰 / 深链",
        }[name]
        print(f"[{mark}] {name} —— {desc}")
        for b in bad:
            print(f"         · {b}")
        total += len(bad)
    print()
    if total == 0:
        n = str(len(GATES))
        print(f"颜色模式门禁 {n}/{n} 全绿")
        return 0
    print(f"门禁失败项：{total}")
    return 1


if __name__ == "__main__":
    sys.exit(main())
