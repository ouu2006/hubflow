"""hubflow 前端自查门禁（7 项）。改完代码跑一遍，全绿才算完。

用法：python scripts/frontend_gate.py
退出码 0 = 全绿，1 = 有失败项。
"""
import os
import re
import sys

ROOT = r"C:\dev\hubflow\work\frontend\harmony"
ETS = os.path.join(ROOT, "entry", "src", "main", "ets")

# 口径红线：页面用户可见文案不得出现这三个词（「请服从现场指挥」是手册固定措辞，例外）
FORBIDDEN = ["实测", "实时", "现场"]


def rel(p):
    return os.path.relpath(p, ETS).replace("\\", "/")


def walk_ets():
    out = []
    for base, _dirs, files in os.walk(ETS):
        for f in files:
            if f.endswith(".ets") or f.endswith(".ts"):
                out.append(os.path.join(base, f))
    return out


def read(p):
    return open(p, encoding="utf-8").read()


def strip_comments(src):
    """去掉 // 与 /* */ 注释，只留真正的代码与字符串。

    【为什么必须去注释再查】
    违禁词红线的对象是**用户可见文案**（Text() 里的字符串），
    不是注释。我们自己在注释里写「实测：点四个开关无反应」这种踩坑记录，
    是给人看的，如果按原文查会误报几十条，门禁就废了。
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
                i += 1
            i += 2
        else:
            out.append(c)
            i += 1
    return "".join(out)


def gate_crlf(files):
    bad = [rel(p) for p in files if b"\r\n" in open(p, "rb").read()]
    return bad, ["CRLF 行尾（门禁要求 LF）"]


def gate_unused_import(files):
    bad = []
    for p in files:
        src = read(p)
        body = re.sub(r"^import .*?$", "", src, flags=re.M | re.S)
        for m in re.finditer(r"^import\s+(?:type\s+)?\{([^}]*)\}\s+from", src, flags=re.M):
            for name in m.group(1).split(","):
                n = name.strip().split(" as ")[-1].strip()
                if not n:
                    continue
                if not re.search(r"\b" + re.escape(n) + r"\b", body):
                    bad.append(f"{rel(p)} 未使用的 import: {n}")
    return bad, ["未使用的 import（会被 ArkTS 告警，评审也会挑）"]


def gate_forbidden(files):
    bad = []
    for p in files:
        # 关键：先剥注释，只在剩下的代码里找违禁词（即用户可见的字符串字面量）
        src = strip_comments(read(p))
        for w in FORBIDDEN:
            for m in re.finditer(w, src):
                line = src[:m.start()].count("\n") + 1
                ctx = src.splitlines()[line - 1].strip()
                if "请服从现场指挥" in ctx:
                    continue
                bad.append(f"{rel(p)}:{line} 违禁词「{w}」-> {ctx[:70]}")
    return bad, ["用户可见文案出现违禁词"]


def gate_scheme(files):
    """真实地图档的入口必须还在（可插拔架构不能被改掉）"""
    bad = []
    p = os.path.join(ETS, "components", "RoadNetMap.ets")
    src = read(p)
    if "function createRenderer(): MapRenderer" not in src:
        bad.append("RoadNetMap.ets 的 createRenderer() 不见了 —— 地图档位切换点被删")
    if "implements MapRenderer" not in read(os.path.join(ETS, "common", "SelfDrawRenderer.ets")):
        bad.append("SelfDrawRenderer 不再实现 MapRenderer —— 可插拔架构断了")
    return bad, ["地图可插拔架构（MapRenderer 接口 + createRenderer 切换点）"]


def gate_realkey(files):
    bad = []
    p = os.path.join(ETS, "common", "RealNet.ets")
    if not os.path.exists(p):
        bad.append("common/RealNet.ets 不见了 —— 真实路网数据丢了")
        return bad, ["真实路网数据文件"]
    src = read(p)
    for name in ["REAL_ROAD_NETWORK", "realRoutePts", "realDeparturePts", "REAL_MANEUVER_MARKS"]:
        if name not in src:
            bad.append(f"RealNet.ets 缺少导出 {name}")
    return bad, ["真实路网数据完整性"]


def gate_forcetype(files):
    """带状态的 Canvas 必须走双节点切换，且切换条件必须每次都翻转"""
    bad = []
    p = os.path.join(ETS, "components", "RoadNetMap.ets")
    src = strip_comments(read(p))
    # 【踩过的坑，务必保留这条检查】
    # 第一版条件写成 `pickedPathId !== ''` —— 初值就是 'P-2'，恒为 true，
    # 两个分支永远走同一支，节点从不重建 → 地图永远停在旧画面。
    # 正确写法是靠「代号奇偶」翻转：每次状态变化自增，奇偶必变。
    if "this.repaintEpoch % 2 === 1" not in src:
        bad.append("RoadNetMap 的双 Canvas 条件没有用 repaintEpoch 奇偶 —— 地图不会重画")
    if "repaintEpoch" not in read(p):
        bad.append("RoadNetMap 没有 repaintEpoch 入参 —— 无法感知状态变化")
    store = strip_comments(read(os.path.join(ETS, "common", "DemoStore.ets")))
    if "routeEpoch" not in store or "bumpEpoch" not in store:
        bad.append("DemoStore 没有 routeEpoch / bumpEpoch —— 重绘代号无处产生")
    # 三个页面都要把 epoch 传下去，漏一个页面地图就不重画
    for page in ("RecommendPage.ets", "DropoffPage.ets", "DeparturePage.ets"):
        ps = read(os.path.join(ETS, "pages", page))
        if "repaintEpoch: this.store.routeEpoch" not in ps:
            bad.append(f"pages/{page} 没传 repaintEpoch —— 该页地图不会重画")
    return bad, ["Canvas 强制重画条件"]


def gate_maneuver_limit(files):
    """继续按钮的上限不能写死（真实路网有 12 个转向）"""
    bad = []
    p = os.path.join(ETS, "common", "DemoStore.ets")
    # 同样先剥注释：注释里写「初版写死 < 2」是解释，不是代码
    src = strip_comments(read(p))
    if re.search(r"maneuverIndex\s*<\s*2\b", src):
        bad.append("DemoStore.advanceManeuver 仍写死上限 2 —— 真实路网有 12 个转向")
    if "maneuverTotal()" not in src:
        bad.append("DemoStore 没有 maneuverTotal() —— 转向上限无处可算")
    return bad, ["转向推进上限"]


def gate_epoch_bump(files):
    """四个会改地图外观的 setter 都必须 bumpEpoch()

    【为什么要有这道门禁 —— 本轮踩到的真 bug】
    Canvas 的 onReady 只在节点挂载时跑一次，靠 routeEpoch 奇偶翻转强制重建节点。
    只要某个 setter 忘了 bumpEpoch()，它的开关就**只改文字不改地图**：
    图例是 @Prop 绑定，父组件重渲染就立刻变「畅通(灰)」；
    而地图仍画旧画面。实测 setColorBlind 漏了 bumpEpoch，
    开去色校验后图例已灰、地图里的路线还是绿橙。
    与「点变道地图不动」是同一个根因，所以四个 setter 一律要 bump。
    """
    bad = []
    p = os.path.join(ETS, "common", "DemoStore.ets")
    src = strip_comments(read(p))
    for setter in ("setEmergency", "setUnavailable", "setDegraded", "setColorBlind"):
        m = re.search(r"\n  " + setter + r"\([^)]*\)[^{]*\{", src)
        if not m:
            bad.append(f"DemoStore 找不到 {setter}()")
            continue
        nxt = re.search(r"\n  \w+\([^)]*\)[^{]*\{", src[m.end():])
        body = src[m.end():m.end() + (nxt.start() if nxt else len(src))]
        if "bumpEpoch()" not in body:
            bad.append(
                f"DemoStore.{setter}() 没有 bumpEpoch() —— "
                f"该开关只改文字不重画地图（Canvas onReady 不重跑）"
            )
    return bad, ["改地图外观的 setter 必须 bumpEpoch"]


def gate_emergency_keep(files):
    """应急/降级只能「加提示条」，绝不能整块吃掉下面的正文

    【为什么要有这道门禁 —— 本轮用户明确纠正过的错】
    用户原话：「应急态的时候离站这个页面下面的字怎么全没了？给我恢复啊，
      下面依旧有字啊，我只是让你应急态的时候上面多一个弹框，并没有让你删任何的东西」
    我把正文包进了 `if (!this.store.emergency)`，
    应急一亮整页只剩一条红条 —— 卡片、路段、图例全没了。
    正确做法是：应急 = 顶部加红条 + 下面红色大框，**正文一字不减**。

    所以这里检查三件事：
      ① 页面正文不能被 `!store.emergency` / `!store.degraded` 之类的条件包住
      ② 应急态必须渲染红色大框 EmergencyCard（与导航页一致）
      ③ 离站/落客页的底部操作条不能有「继续」键（这两页没有转向条，按了没反应）
    """
    bad = []
    for page in ("DropoffPage", "DeparturePage", "RecommendPage"):
        p = os.path.join(ETS, "pages", page + ".ets")
        if not os.path.exists(p):
            bad.append(f"找不到页面 {page}.ets")
            continue
        src = strip_comments(read(p))
        # ① 不得用否定条件把正文整块包起来
        for pat, why in (
            (r"if\s*\(\s*!\s*this\.store\.emergency\s*\)",
             "用 if (!emergency) 包正文 —— 应急一亮正文全没了"),
            (r"if\s*\(\s*!\s*this\.store\.degraded\s*\)",
             "用 if (!degraded) 包正文 —— 降级一亮正文全没了"),
        ):
            if re.search(pat, src):
                bad.append(f"{page}: {why}")
    # ② 三页都必须渲染红色大框
    for page in ("DropoffPage", "DeparturePage"):
        p = os.path.join(ETS, "pages", page + ".ets")
        src = strip_comments(read(p))
        if "EmergencyCard()" not in src:
            bad.append(
                f"{page}: 应急态没有渲染红色大框 EmergencyCard() —— "
                f"用户要求「下面原本有个红色大框，不要删掉」"
            )
    # ③ 落客/离站的底部操作条不许有「继续」键
    for comp in ("DropoffActionRow", "DepartureActionRow"):
        p = os.path.join(ETS, "components", "NavBar.ets")
        src = strip_comments(read(p))
        m = re.search(r"export struct " + comp + r"\b", src)
        if not m:
            bad.append(f"NavBar.ets 找不到 {comp}")
            continue
        nxt = re.search(r"\nexport struct ", src[m.end():])
        body = src[m.end():m.end() + (nxt.start() if nxt else len(src))]
        if "advanceManeuver" in body:
            bad.append(
                f"{comp}: 有「继续」键（advanceManeuver）—— "
                f"这两页顶部没有转向条，按了没有任何变化"
            )
    return bad, ["应急态只叠加提示条，不删正文"]


def gate_dist_not_hardcoded(files):
    """导航条的「剩余距离 / X 米后」必须实时算，不能写字面量

    【为什么要有这道门禁 —— 用户提问引出的真bug】
    用户原话：「它上面这个黑色的弹窗有个小字多少多少米后……难道不应该是我越点继续，
      它的米越少嘛」「下面这个白色的剩余多少多少千米，那也要跟着变啊」
    两个真问题：
      ① `Text(... : '剩余 1.8 km')` 是**字面量**，点多少下都不变
      ② `REAL_ROUTE_TOTAL_M` 写 8612，而转向点最大只到 5043
         → 「总长-已走」在末段算出 3569m，比出发点还远
    这里检查：不得出现写死的 km 字面量，且总长必须与 arrive 转向点同源。
    """
    bad = []
    p = os.path.join(ETS, "components", "NavBar.ets")
    src = strip_comments(read(p))
    # ① 不得有写死的剩余距离文案
    if re.search(r"'剩余\s*[\d.]+\s*(km|m)'", src):
        bad.append("NavBar 出现写死的剩余距离字面量（应实时算）")
    if "remainDistText()" not in src:
        bad.append("NavBar 没有 remainDistText() —— 剩余距离无处可算")
    if "distToNextTurn()" not in src:
        bad.append("NavBar 没有 distToNextTurn() —— 「X 米后」写的是已走里程而非前方距离")
    # ② 路线总长必须 >= 最后一个转向点里程
    p2 = os.path.join(ETS, "common", "RealNet.ets")
    src2 = read(p2)
    m = re.search(r"REAL_ROUTE_TOTAL_M:\s*number\s*=\s*(\d+)", src2)
    ds = [int(x) for x in re.findall(r"\{\s*d:\s*(\d+)\s*,\s*type:", src2)]
    if not m:
        bad.append("RealNet 找不到 REAL_ROUTE_TOTAL_M")
    elif ds and int(m.group(1)) < max(ds):
        bad.append(
            f"REAL_ROUTE_TOTAL_M={m.group(1)} 小于最后一个转向点里程 {max(ds)} "
            f"→ 剩余距离会算出负值或倒退"
        )
    return bad, ["距离文案实时计算，不写死"]


def gate_car_moves(files):
    """车标（司机本人：蓝圈+白环+方向三角）随「继续」沿路线移动

    【为什么要有这道门禁 —— 用户需求】
    用户原话：「我想要让那个带有箭头一样的那个圆圈，也就是代表司机本人的那个圆圈，
      随着继续动起来，并不是停在原点的，我每按一下，它都在对应位置动到对应位置」
    又明确：「落客/离站页面没有继续这个按钮……它三角应该是不会动的呀，就在起点。
      只有导航这里才有继续这个按钮，它才需要动。」

    所以本门禁分两类页面检查：
      · 导航页（RecommendPage）：车标必须随「继续」移动。
        一期是「一点一动」（maneuverIndex → carPoint 插值）；
        现改为「一点自动移动到终点」（连续进度 driveRatio → pointAtRatio 插值）。
        两者都满足「车随继续沿路线移动」，门禁都要放行。
        → RoadNetMap 的车标必须来自按比例插值（carPoint 或 pointAtRatio(route.points, ...)），
          且必须接收连续进度 driveRatio；导航页必须把它传下去。
      · 落客/离站页（DropoffPage / DeparturePage）：不导航，车标必须钉在起点
        → 不传 store.driveRatio（否则会跟着导航页的行驶进度一起乱动，正是用户投诉的现象）。
    三个推进方法（advance/retreat/restart）都必须 bumpEpoch()，
    否则 Canvas 不重画，改了行驶进度也看不到车移动。
    """
    bad = []
    p = os.path.join(ETS, "components", "RoadNetMap.ets")
    src = strip_comments(read(p))
    if re.search(r"\bcar:\s*route\.start\b", src):
        bad.append("RoadNetMap: car 仍写死 route.start —— 车标不会随「继续」移动")
    # 车标位置必须来自「按比例插值」（carPoint 或 pointAtRatio(route.points, ...) 都算）
    if "carPoint(" not in src and "pointAtRatio(route.points" not in src:
        bad.append("RoadNetMap: 车标位置没有按比例插值（carPoint / pointAtRatio 都算）")
    if "driveRatio" not in src:
        bad.append("RoadNetMap: 没有 driveRatio 入参 —— 地图不知道车开到哪了（连续进度）")
    # 【为什么不再要求 maneuverIndex 入参】
    # 车标已改由 driveRatio 沿折线插值驱动（pointAtRatio），repaint() 不再读
    # maneuverIndex；该 prop 与三页传参已删除（留着会让人以为地图仍按转向序号定位车标）。
    # 若将来车标重新改回离散定位，需同步把这条规则加回来。
    # 导航页：车标随「继续」移动 → 必须传 store.driveRatio（新的连续进度驱动）
    pp = os.path.join(ETS, "pages", "RecommendPage.ets")
    s = strip_comments(read(pp))
    if "driveRatio: this.store.driveRatio" not in s:
        bad.append("RecommendPage: 没给 RoadNetMap 传 store.driveRatio —— 车标不会随「继续」移动")
    # 落客/离站页：没有「继续」按钮（不导航），车标必须钉在起点，
    # 且不能传 store.driveRatio（否则会跟着导航页的行驶进度一起动）
    for page in ("DropoffPage", "DeparturePage"):
        pp = os.path.join(ETS, "pages", page + ".ets")
        s = strip_comments(read(pp))
        # 不传 driveRatio 即为默认 0 → 车标钉在起点（落客/离站页不导航）
        if "driveRatio: this.store.driveRatio" in s:
            bad.append(f"{page}: 误传了 store.driveRatio —— 车标会跟着导航页进度乱动")
    # 三个推进方法都必须 bumpEpoch
    p2 = os.path.join(ETS, "common", "DemoStore.ets")
    s2 = strip_comments(read(p2))
    # 只校验实际存在的推进入口。
    # 初版这里还列了 retreatManeuver/restartManeuver，二者零调用且与
    # restartNav 重复（底部「重走」走的是 restartNav），已删除；
    # 门禁必须跟着改，否则规则本身在检查不存在的代码。
    # 初版列的 advanceManeuver/retreatManeuver/restartManeuver 全部零调用
    # （底部按钮走startCruise / restartNav），已删除；
    # 现在唯一需要 bumpEpoch 的是 restartNav（归零后车标要跳回起点）。
    for fn in ("restartNav",):
        # 不依赖缩进：任意行首空白 + 方法名
        m = re.search(r"\n[ \t]*" + fn + r"\([^)]*\)[^{]*\{", s2)
        if not m:
            bad.append(f"DemoStore 找不到 {fn}()")
            continue
        nxt = re.search(r"\n[ \t]*\w+\([^)]*\)[^{]*\{", s2[m.end():])
        body = s2[m.end():m.end() + (nxt.start() if nxt else len(s2))]
        if "bumpEpoch()" not in body:
            bad.append(
                f"DemoStore.{fn}() 没有 bumpEpoch() —— Canvas 不重画，车标不会动"
            )
    return bad, ["车标随「继续」沿路线移动"]


GATES = [
    ("1/11 CRLF 行尾", gate_crlf),
    ("2/11 未使用 import", gate_unused_import),
    ("3/11 违禁词", gate_forbidden),
    ("4/11 地图可插拔架构", gate_scheme),
    ("5/11 真实路网数据", gate_realkey),
    ("6/11 Canvas 重画条件", gate_forcetype),
    ("7/11 转向推进上限", gate_maneuver_limit),
    ("8/11 开关必须触发重画", gate_epoch_bump),
    ("9/11 应急态不得吃掉正文", gate_emergency_keep),
    ("10/11 距离文案不得写死", gate_dist_not_hardcoded),
    ("11/11 车标随继续移动", gate_car_moves),
]


def main():
    files = walk_ets()
    total = 0
    print(f"扫描 {len(files)} 个源文件\n")
    for name, fn in GATES:
        bad, desc = fn(files)
        mark = "PASS" if not bad else "FAIL"
        print(f"[{mark}] {name} —— {desc[0]}")
        for b in bad:
            print(f"         · {b}")
        total += len(bad)
    print()
    if total == 0:
        n = str(len(GATES))
        print(f"门禁 {n}/{n} 全绿")
        return 0
    print(f"门禁失败项：{total}")
    return 1


if __name__ == "__main__":
    sys.exit(main())
