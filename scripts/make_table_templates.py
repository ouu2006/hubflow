#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""生成 T1~T8 表格模板实体（`.xlsx`），并校验列名与 docs/表格模板说明.md 逐列一致。

用法：
    python scripts/make_table_templates.py --out <共享盘目录>      # 生成 8 份模板
    python scripts/make_table_templates.py --check                 # 只校验列名（不需要 openpyxl）
    python scripts/make_table_templates.py --out <目录> --date 20261013 --version v1

口径（见 docs/表格模板说明.md、Issue #43）：
  * **列名逐字照抄** `docs/表格模板说明.md` —— 改列名 = 改转换脚本的输入契约，要走开发规范第 7 节；
  * 每张表**一行样例数据**（照抄文档的示例值，拿不到官方值就带【待核实】/【待标定】）；
  * **第 1 张 sheet 是数据表**（**表头在第 4 行、从 B 列起，数据从第 5 行开始**），**第 2 张 sheet 是「填写说明」**
    （列名 / 必填 / 说明 / 示例值 / 取值一览 + 填表纪律）——**转换脚本只读第 1 张**（口径："单 sheet"）。
    ⚠️ 这个版式（sheet 名不定、表头行号与列偏移固定）**已写进 docs/表格模板说明.md 第 12 节与 docs/开发规范.md 第 7 节**——
    两边必须一起改，否则 #41 的转换脚本会读错表头；
  * 枚举列带**下拉选项**（数据验证），填表人不用猜取值；表头单元格另挂**批注**（鼠标悬停可见同一份说明）；
  * **每列一行"说明"** 挂在表头单元格的批注里，同时在「填写说明」sheet 里列全；
  * `.xlsx` **不进仓库**（`doc_gate.py` 第 2 组拦）——本脚本**拒绝把产物写进仓库**，只往共享盘写。

⚠️ 本脚本是**列名的唯一机器可读副本**：`--check` 会拿它与 `docs/表格模板说明.md` 对表，
不一致就报错退出（Issue #43 步骤 5 的"与转换脚本对表"以此为准）。
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

# ---------------------------------------------------------------- 列定义（唯一副本）

#: 每张表：文件名前缀 / 表名 / 放置目录（相对共享盘根）/ 谁填 / 转成什么 / 列定义
#: 列定义 = (列名, 必填标记, 说明, 样例值, 下拉选项或 None)
TABLES = [
    {
        "code": "T1",
        "file": "T1_点位表",
        "title": "T1 点位表",
        "dir": "01_站点包表格",
        "filler": "池·S",
        "output": "stations/points.json",
        "columns": [
            ("point_id", "必填", "点位编号，前缀表类型：DROP- 落客 / PICK- 上客 / WAIT- 候客 / DET- 检测断面 / JCT- 路口", "DROP-03", None),
            ("name", "必填", "中文名（管理端要显示）", "站前落客区 A", None),
            ("type", "必填", "五选一", "dropoff", ["dropoff", "pickup", "waiting", "detector", "junction"]),
            ("lon", "必填", "经度（默认 WGS-84；与底图不一致时标【待核实】）", 112.5861, None),
            ("lat", "必填", "纬度（默认 WGS-84；与底图不一致时标【待核实】）", 23.0735, None),
            ("segment_id", "必填", "落在哪条路段，必须能在 T2 里找到", "SEG-004", None),
            ("offset_m", "必填", "距该路段起点的米数", 85, None),
            ("direction", "必填", "朝向", "上行", ["上行", "下行"]),
            ("capacity_vph", "条件必填", "只给落客点 / 上客点 / 候客区填：服务能力（辆/小时），一期为估算值", "180【待标定】", None),
            ("role", "必填", "点位角色：boundary = 围栏外 → 站前的上游边界断面（唯一允许数据同化回灌）；internal = 站前内部路段（一个都不许回灌）", "boundary", ["boundary", "internal"]),
            ("sumo_edge_id", "必填", "该点位 / 断面对应的 SUMO edge id（stations/sumo/*.net.xml 里的边编号）。calibrator 就挂在这条边上，映射错了就灌到别的路上", "E-012", None),
            ("detector_role", "条件必填", "只给 detector 填：一期 = 虚拟检测器；二期 = 摄像头", "一期虚拟检测器", ["一期虚拟检测器", "二期摄像头"]),
            ("source", "必填", "来源", "公开地图 + 现场照片", ["现场照片", "公开地图", "估算", "官方资料"]),
            ("verified", "必填", "核实状态", "待核实", ["已核实", "待核实"]),
            ("filler", "必填", "填表人（写系列 + 人名）", "池·S", None),
            ("date", "必填", "填表日期 YYYY-MM-DD", "2026-10-13", None),
        ],
    },
    {
        "code": "T2",
        "file": "T2_路段属性核对表",
        "title": "T2 路段属性核对表",
        "dir": "01_站点包表格",
        "filler": "池·S",
        "output": "补录进 stations/network.json",
        "columns": [
            ("segment_id", "必填", "路段编号，与开发B 给的路段清单一致", "SEG-004", None),
            ("from_node", "必填", "起点节点编号（OSM / netconvert 产出）", "N-012", None),
            ("to_node", "必填", "终点节点编号（OSM / netconvert 产出）", "N-018", None),
            ("length_m", "必填", "路段长度（米）", 380, None),
            ("lanes", "必填", "车道数", 3, None),
            ("speed_limit_kmh", "必填", "限速（km/h）", 40, None),
            ("c_vph", "必填", "通行能力（辆/小时）；拿不到官方值就估算并标【待标定】", "1288【待标定】", None),
            ("oneway", "必填", "单双向", "是", ["是", "否"]),
            ("底图核对", "必填", "只有三种取值：一致 / 不一致 / 待核实，没有空白格（TC-15 的判定口径）", "不一致", ["一致", "不一致", "待核实"]),
            ("差异原因", "条件必填", "填「不一致」时必须写；填「一致」可空。写人话（如「底图两车道、实地三车道」）", "高德底图此处两车道，实地三车道", None),
            ("verified", "必填", "核实状态", "待核实", ["已核实", "待核实"]),
            ("filler", "必填", "填表人（写系列 + 人名）", "池·S", None),
            ("date", "必填", "填表日期 YYYY-MM-DD", "2026-10-13", None),
        ],
    },
    {
        "code": "T3",
        "file": "T3_列车时刻表",
        "title": "T3 列车时刻表",
        "dir": "01_站点包表格",
        "filler": "池·S",
        "output": "stations/demand.json",
        "columns": [
            ("train_no", "必填", "车次", "G1234", None),
            ("direction", "必填", "到达 / 出发（两向都要录，只录到达会让「接客」需求对不上）", "到达", ["到达", "出发"]),
            ("time", "必填", "计划时刻 HH:MM", "17:42", None),
            ("delay_min", "选填", "典型晚点分钟数（一期手填）", "5【待核实】", None),
            ("platform", "选填", "站台号", 3, None),
            ("pax_est", "必填", "预计下车 / 上车人数", "320【待核实】", None),
            ("vehicle_est", "必填", "预计接 / 送车辆数", "110【待核实】", None),
            ("source", "必填", "来源（不许把估算值写成官方值）", "12306 公开时刻表", ["12306 公开时刻表", "车站公告", "估算"]),
            ("verified", "必填", "核实状态", "待核实", ["已核实", "待核实"]),
            ("note", "选填", "备注（临客、节假日加开）", "周末加开", None),
            ("filler", "必填", "填表人（写系列 + 人名）", "池·S", None),
            ("date", "必填", "填表日期 YYYY-MM-DD", "2026-10-13", None),
        ],
    },
    {
        "code": "T4",
        "file": "T4_需求比例表",
        "title": "T4 需求比例表",
        "dir": "01_站点包表格",
        "filler": "池·S",
        "output": "stations/demand.json",
        "columns": [
            ("time_window", "必填", "时段", "17:00–19:00", None),
            ("day_type", "必填", "日类型", "工作日", ["工作日", "周末", "节假日", "春运"]),
            ("demand_multiplier", "必填", "需求倍率（基准时段 = 1.0，相对值不是绝对值）", "1.8【待标定】", None),
            ("od_pair", "必填", "OD 对编号（与 T1 / T2 的节点一致）", "OD-01", None),
            ("share_D1", "必填", "D1 送客占比；share_D1 + share_D2 + share_D3 每行加总 = 100%", "45%", None),
            ("share_D2", "必填", "D2 接客占比（同上，加总 = 100%）", "30%", None),
            ("share_D3", "必填", "D3 往返占比（同上，加总 = 100%）", "25%", None),
            ("share_S1", "必填", "S1 门口即停即走占比；share_S1 + share_S2 加总 = 100%", "60%", None),
            ("share_S2", "必填", "S2 路边或停车场占比（同上，加总 = 100%）", "40%", None),
            ("share_private", "必填", "私家车占比；share_private + share_taxi + share_online + share_bus 加总 = 100%", "55%", None),
            ("share_taxi", "必填", "出租车占比（同上，加总 = 100%）", "20%", None),
            ("share_online", "必填", "网约车占比（同上，加总 = 100%）", "22%", None),
            ("share_bus", "必填", "大巴占比（同上，加总 = 100%）", "3%", None),
            ("app_penetration", "必填", "App 渗透率（F14），小数", "0.3【建议值】", None),
            ("filler", "必填", "填表人（写系列 + 人名）", "池·S", None),
            ("date", "必填", "填表日期 YYYY-MM-DD", "2026-10-13", None),
        ],
    },
    {
        "code": "T5",
        "file": "T5_因素表",
        "title": "T5 因素表",
        "dir": "01_站点包表格",
        "filler": "池·P",
        "output": "stations/factors.json",
        "columns": [
            ("factor_id", "必填", "F01~F14", "F01", None),
            ("name", "必填", "因素名（与总纲第 6 节一致）", "大雨", None),
            ("target", "必填", "改什么：c 通行能力 / v_f 畅通速度 / demand 需求 / lanes 车道数 / confidence 置信度", "c", ["c", "v_f", "demand", "lanes", "confidence"]),
            ("multiplier", "必填", "乘数（改容量 / 速度 / 需求用）；封路类写 0 或另加说明", 0.75, None),
            ("start", "条件必填", "生效时间窗起点（ISO 时间或 HH:MM）；常驻因素写「全天 / 全年」", "2026-10-12T17:00+08:00", None),
            ("until", "条件必填", "生效时间窗终点（ISO 时间或 HH:MM）；常驻因素写「全天 / 全年」", "2026-10-12T20:00+08:00", None),
            ("scope", "必填", "作用范围：全网 / 指定路段（写 segment_id 列表，必须能在 T2 里找到）/ 指定点位", "SEG-003,SEG-004", None),
            ("source_1", "必填", "一期来源", "手填", ["手填", "孪生模拟", "场景注入"]),
            ("source_2", "必填", "二期来源", "气象数据接口", ["气象接口", "摄像头", "停车场接口", "交警通告", "仍手填"]),
            ("notes", "选填", "备注（如「合成后不低于原值 40%【待标定】」）", "合成后不低于原值 40%【待标定】", None),
            ("filler", "必填", "填表人（写系列 + 人名）", "池·P", None),
            ("date", "必填", "填表日期 YYYY-MM-DD", "2026-10-13", None),
        ],
    },
    {
        "code": "T6",
        "file": "T6_场景剧本表",
        "title": "T6 场景剧本表",
        "dir": "01_站点包表格",
        "filler": "池·S",
        "output": "stations/scenarios.json",
        "columns": [
            ("scenario_id", "必填", "S1~S4", "S2", ["S1", "S2", "S3", "S4"]),
            ("name", "必填", "场景名", "列车集中到达峰值", None),
            ("goal", "必填", "这个场景要证明什么（一句话）", "同一输入下三种策略同屏对比", None),
            ("switches", "必填", "开关项：推荐开 / 关、协同策略开 / 关、多因素开 / 关、数据同化开 / 关", "协同推荐 = 开；时段预约 = 开；数据同化 = 开", None),
            ("assimilation", "必填", "数据同化设置：enabled（开 / 关）+ edges（只许写 T1 里 role = boundary 的断面映射出来的 SUMO edge id，写了 internal 视为配置错误）+ period_s（60）+ gate（confidence_min = 0.6【待标定】、data_age_max_s = 120）", "enabled = true；edges = E-012；period_s = 60；gate = 0.6 / 120 s", None),
            ("inject_events", "必填", "注入事件：factor_id + 生效时刻 + 强度（factor_id 必须是 T5 里登记过的，不许现编）", "F03 列车到达 17:40 放量 ×2；F01 大雨 17:00 起", None),
            ("seed", "必填", "随机种子（必须写——没有它同一场景两遍跑不出同一个数，M1-1 直接不过）", 20261012, None),
            ("sim_start", "必填", "仿真起始时刻", "16:30", None),
            ("duration_min", "必填", "演示时长（分钟）", 120, None),
            ("runs", "必填", "跑几遍、每遍是什么（对照设置）。场景二必须写全三遍：①不推荐 ②「此刻最快」 ③协同推荐", "3 遍：①不推荐 ②「此刻最快」 ③协同推荐", None),
            ("key_judgement", "必填", "对应的验收编号（照抄，不许改写）", "TC-14、TC-17", None),
            ("presenter", "必填", "演示时谁讲、讲哪句话", "池·P", None),
            ("filler", "必填", "填表人（写系列 + 人名）", "池·S", None),
            ("date", "必填", "填表日期 YYYY-MM-DD", "2026-10-13", None),
        ],
    },
    {
        "code": "T7",
        "file": "T7_测试检查表",
        "title": "T7 测试检查表",
        "dir": "02_测试与验收",
        "filler": "池·Q",
        "output": "验收记录（不进仓库）",
        "columns": [
            ("case_id", "必填", "TC-01~TC-20 / M1-1~M1-10", "TC-17", None),
            ("text", "必填", "判定原文，照抄手册第 17.1 节，不许改写", "③中先进入车辆的到达时间因后车进入而增加 ≤ 30 s【待标定】；不新增橙 / 红路段；全网总行程时间低于②", None),
            ("how", "必填", "怎么操作（跑哪条命令、点哪个页面）", "跑场景二三次对比，看效果对比报表", None),
            ("expect", "必填", "看到什么算过", "三项同时成立", None),
            ("inputs", "必填", "需要什么输入文件 / 版本", "scenarios.json v3、两遍 segments.json 快照", None),
            ("result", "必填", "过 / 不过 / 阻塞（没有「基本过」）", "过", ["过", "不过", "阻塞"]),
            ("evidence", "必填", "录屏 / 截图文件名（带日期与用例号）", "TC17_20261020.mp4", None),
            ("defect_id", "条件必填", "不过时填缺陷编号", "D-012", None),
            ("tester", "必填", "测试人（池·Q；开发不得认领 Q）", "池·Q", None),
            ("date", "必填", "测试日期 YYYY-MM-DD", "2026-10-13", None),
        ],
    },
    {
        "code": "T8",
        "file": "T8_数据来源清单",
        "title": "T8 数据来源清单",
        "dir": "04_数据来源与合规",
        "filler": "池·P + 队长复核",
        "output": "对外物料核查（不进仓库）",
        "columns": [
            ("item", "必填", "数值 / 图表 / 截图的名字", "场景二对比图表", None),
            ("where", "必填", "出现在哪（页 / 图 / 表 / 物料文件名）", "PPT 第 9 页", None),
            ("value", "必填", "具体数值或范围", "全网总行程时间 −12%【待标定】", None),
            ("source", "必填", "数字孪生模拟 / 手填表格（写 T 编号）/ 公开数据（写出处）/ 估算", "数字孪生模拟", ["数字孪生模拟", "手填表格", "公开数据", "估算"]),
            ("is_simulated", "必填", "是 / 否（一期全部为「是」）", "是", ["是", "否"]),
            ("badge_ok", "必填", "物料角标是否齐全（角标文字统一为「演示数据（模拟）· 双数据源（视频链路 + 孪生链路）」）", "是", ["是", "否"]),
            ("path", "必填", "数据文件路径（共享盘或仓库）", "out/segments_场景二_③.json", None),
            ("checker", "必填", "核查人（池·P）+ 队长复核", "池·P", None),
            ("date", "必填", "核查日期 YYYY-MM-DD", "2026-10-13", None),
        ],
    },
]

#: 表尾提示（写在样例行下面，转换脚本按"表头 + 数据行"读，不会碰到它）
FOOTER_NOTES = [
    "填表纪律：① 文件名带日期与版本（如 T5_因素表_20261012_v3.xlsx），每天按日期留一版、永不覆盖；",
    "② 拿不到官方数据就标【待核实】/【待标定】，不许留空白、不许编一个数当真值；",
    "③ 列名不许自己改——要加列 / 改列名先在站会上说，由结构 owner 更新 docs/表格模板说明.md 后统一换模板；",
    "④ 谁填谁签字（filler / date 每行都要有）；⑤ 不许写真实个人信息（车牌 / 人脸 / 个人轨迹一律不填）；",
    "⑥ stations/ 下的 JSON 不许手改——那是转换脚本的产物，要改就改表、升版本号、重跑脚本。",
]

#: 表头批注里统一带的四行头（谁填 / 转成什么 / 放在哪 / 口径出处）
HEADER_NOTE_TAIL = [
    "口径出处：docs/表格模板说明.md",
    "必填列留空 → 转换脚本报错退出并指出行号（不许静默补空）",
]

DOC_PATH = "docs/表格模板说明.md"
#: 设计规范版式（与 spreadsheets 设计系统一致：A 列留白、1~3 行标题区、第 4 行表头、第 5 行起数据）
MARGIN_COL = "A"
HEADER_ROW = 4
DATA_START_ROW = 5
TITLE_ROW = 2
MAX_COL_WIDTH = 30
MIN_COL_WIDTH = 10


def layout_contract() -> dict:
    """模板实体的**版式契约**——转换脚本（Issue #41）按这个读，别按印象猜。

    口径同步写在 `docs/表格模板说明.md` 第 12 节与 `docs/开发规范.md` 第 7 节；
    **改这里必须同时改那两处**，否则转换脚本会读错表头。
    """
    return {
        "data_sheet": "第 1 张 sheet（索引 0；名字形如 `<T编号> <表名>`，脚本按索引取，不要按名字找）",
        "guide_sheet": "第 2 张 sheet「填写说明」（**转换脚本不读**）",
        "header_row": HEADER_ROW,
        "first_data_column": 2,
        "first_data_column_letter": "B",
        "data_start_row": DATA_START_ROW,
        "data_end_row": "读到空行为止（样例行在第 5 行，填表人从第 5 行起覆盖）",
        "column_names": f"第 {HEADER_ROW} 行 B 列起，逐字等于 {DOC_PATH} 的列定义",
    }


# ---------------------------------------------------------------- 列名校验


def doc_column_lists(doc_text: str) -> dict[str, list[str]]:
    """从 docs/表格模板说明.md 抽出每张表的列名列表（按文档出现顺序）。"""
    result: dict[str, list[str]] = {}
    for section in re.split(r"\n## ", doc_text):
        head = section.split("\n", 1)[0]
        match = re.match(r"^[一二三四五六七八九十]+、(T\d)\s", head)
        if not match:
            continue
        names: list[str] = []
        for line in section.split("\n"):
            if not line.startswith("|"):
                continue
            cells = [c.strip() for c in line.strip("|").split("|")]
            if len(cells) < 4 or cells[0] in ("列名", "") or set(cells[0]) <= set("-: "):
                continue
            # 单元格里是 `` `lon` / `lat` `` 这种写法：按反引号拆出每个列名
            found = re.findall(r"`([^`]+)`", cells[0])
            if found:
                names.extend(found)
            elif cells[0].startswith("**") and cells[0].endswith("**"):
                names.append(cells[0].strip("*"))   # T2 的 底图核对 / 差异原因 没有代码名
        result[match.group(1)] = names
    return result


def check_against_doc(repo_root: Path) -> list[str]:
    """列名与 docs/表格模板说明.md 逐列比对；返回问题列表（空 = 一致）。"""
    doc_file = repo_root / DOC_PATH
    if not doc_file.exists():
        return [f"{DOC_PATH} 不存在 —— 列名的权威出处找不到，无法对表"]
    expected = doc_column_lists(doc_file.read_text(encoding="utf-8"))
    problems: list[str] = []
    for table in TABLES:
        code = table["code"]
        if code not in expected:
            problems.append(f"{code}：{DOC_PATH} 里找不到这张表的列定义")
            continue
        want = expected[code]
        got = [col[0] for col in table["columns"]]
        if want != got:
            only_doc = [n for n in want if n not in got]
            only_script = [n for n in got if n not in want]
            detail = []
            if only_doc:
                detail.append(f"文档有而脚本没有：{only_doc}")
            if only_script:
                detail.append(f"脚本有而文档没有：{only_script}")
            if not detail:                       # 集合相同但顺序不同
                detail.append(f"顺序不一致：文档 {want}，脚本 {got}")
            problems.append(f"{code}：列名对不上（{'；'.join(detail)}）")
    return problems


# ---------------------------------------------------------------- 生成 .xlsx


def _display_width(text: object) -> float:
    """估算单元格显示宽度：CJK 记 2 个字符宽，其余记 1。"""
    import unicodedata

    return sum(2 if unicodedata.east_asian_width(ch) in "WF" else 1 for ch in str(text))


def _sample_row_height(columns: list[tuple]) -> float:
    """按"最长的一列要折几行"估样例行行高——长文本（如 T6 的 assimilation）不裁切。"""
    widest = 0.0
    for name, _required, _note, sample, _choices in columns:
        col_chars = max(min(max(_display_width(name) + 2, MIN_COL_WIDTH), MAX_COL_WIDTH), MIN_COL_WIDTH)
        lines = max(1, int(_display_width(sample) / col_chars) + 1)
        widest = max(widest, lines)
    return max(22.0, 15.0 * widest + 6.0)


def build_workbook(table: dict, out_dir: Path, date_tag: str, version: str) -> Path:
    """生成一张表的模板实体，返回落盘路径。

    第 1 张 sheet 是数据表（**转换脚本只读这一张**：表头第 4 行、样例第 5 行，其后不放任何说明文字）；
    第 2 张 sheet 是「填写说明」（列定义 + 取值一览 + 填表纪律），给人看，脚本不读。
    """
    try:
        from openpyxl import Workbook
        from openpyxl.comments import Comment
        from openpyxl.styles import Alignment, Font, PatternFill
        from openpyxl.utils import get_column_letter
        from openpyxl.worksheet.datavalidation import DataValidation
        from openpyxl.worksheet.properties import PageSetupProperties
    except ImportError:                          # pragma: no cover - 环境缺依赖时的提示
        raise SystemExit(
            "缺少 openpyxl —— 生成模板实体需要它：python -m pip install openpyxl\n"
            "（列名校验不需要依赖，可直接跑 --check）"
        )

    # 版式令牌（与 docs/表格模板说明.md 无关，纯样式；沿用设计系统的三色纪律）
    primary = "1B2A4A"
    neutral_900, neutral_600, neutral_200 = "37352F", "8C8A84", "E9E9E8"
    neutral_100 = "F7F7F5"
    body = Font(name="微软雅黑", size=11, color=neutral_900)
    caption = Font(name="微软雅黑", size=9, color=neutral_600)
    wrap = Alignment(horizontal="left", vertical="top", wrap_text=True)

    columns = table["columns"]
    last_col = len(columns) + 1                   # B 列起
    wb = Workbook()

    # ---------- sheet 1：数据表（脚本读的那张） ----------
    ws = wb.active
    ws.title = f"{table['code']} {table['file'].split('_', 1)[1]}"

    # 画布：A 列留白、1~3 行标题区、第 4 行表头
    ws.sheet_view.showGridLines = False
    ws.column_dimensions[MARGIN_COL].width = 3
    ws.row_dimensions[1].height = 15
    ws.row_dimensions[TITLE_ROW].height = 32
    ws.row_dimensions[3].height = 30
    ws.merge_cells(start_row=TITLE_ROW, start_column=2, end_row=TITLE_ROW, end_column=last_col)
    title_cell = ws.cell(row=TITLE_ROW, column=2, value=f"{table['title']}（模板 {version} · 生成日 {date_tag}）")
    title_cell.font = Font(name="微软雅黑", size=16, color=primary)
    title_cell.alignment = Alignment(horizontal="left", vertical="center")

    # 副标题：谁填 / 转成什么 / 第 5 行是样例（填表人一眼知道这表干什么用）
    ws.merge_cells(start_row=3, start_column=2, end_row=3, end_column=last_col)
    sub = ws.cell(
        row=3, column=2,
        value=(f"谁填：{table['filler']}　→　转成：{table['output']}　"
               f"（列名口径见 {DOC_PATH}；填表前先看第 2 张 sheet「填写说明」）\n"
               "第 5 行是样例（带【待核实】/【待标定】的都不算真值）——填表时从第 5 行起覆盖，不要留样例"),
    )
    sub.font = caption
    sub.alignment = Alignment(horizontal="left", vertical="center", wrap_text=True)

    # 表头（挂批注：鼠标悬停可见该列的必填性与说明）
    for offset, (name, required, note, _sample, _choices) in enumerate(columns):
        cell = ws.cell(row=HEADER_ROW, column=offset + 2, value=name)
        cell.fill = PatternFill("solid", fgColor=primary)
        cell.font = Font(name="微软雅黑", size=11, color="FFFFFF")
        cell.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)
        cell.comment = Comment("\n".join([f"【{required}】{note}", *HEADER_NOTE_TAIL]), "表格模板")
        cell.comment.width, cell.comment.height = 340, 150
    ws.row_dimensions[HEADER_ROW].height = 30

    # 样例行（照抄文档示例值；一眼看得出是样例）
    for offset, (_name, _required, _note, sample, _choices) in enumerate(columns):
        cell = ws.cell(row=DATA_START_ROW, column=offset + 2, value=sample)
        cell.fill = PatternFill("solid", fgColor=neutral_100)
        cell.font = body
        cell.alignment = Alignment(horizontal="left", vertical="center", wrap_text=True)
    # 样例行里长文本（如 T6 的 assimilation）会折行——按最长一列估行高，避免被裁切
    ws.row_dimensions[DATA_START_ROW].height = _sample_row_height(columns)

    # 枚举列下拉（填表人不用猜取值）
    for offset, (_name, _required, _note, _sample, choices) in enumerate(columns):
        if not choices:
            continue
        letter = get_column_letter(offset + 2)
        validator = DataValidation(
            type="list", formula1='"' + ",".join(choices) + '"', allow_blank=True, showDropDown=False
        )
        # ⚠️ openpyxl 的 showErrorMessage 默认 False：不显式打开，error/errorTitle 就是死配置
        validator.showErrorMessage = True
        validator.error = "只能从下拉里选（口径见列批注与 docs/表格模板说明.md）"
        validator.errorTitle = "取值越界"
        ws.add_data_validation(validator)
        validator.add(f"{letter}{DATA_START_ROW}:{letter}500")

    # 列宽：按表头与样例里较宽的那个算，长说明靠批注与「填写说明」sheet 承载
    for offset, (name, _required, _note, sample, _choices) in enumerate(columns):
        letter = get_column_letter(offset + 2)
        width = max(_display_width(name) + 2, min(_display_width(sample) + 2, MAX_COL_WIDTH), MIN_COL_WIDTH)
        ws.column_dimensions[letter].width = min(width, MAX_COL_WIDTH)

    ws.freeze_panes = f"B{DATA_START_ROW}"
    ws.auto_filter.ref = f"B{HEADER_ROW}:{get_column_letter(last_col)}{DATA_START_ROW}"
    ws.page_setup.orientation = "landscape"
    ws.page_setup.fitToWidth = 1
    ws.page_setup.fitToHeight = 0
    ws.print_title_rows = f"{HEADER_ROW}:{HEADER_ROW}"      # 续页也带表头

    # ---------- sheet 2：填写说明（给人看，脚本不读） ----------
    guide = wb.create_sheet("填写说明")
    guide.sheet_view.showGridLines = False
    guide.column_dimensions[MARGIN_COL].width = 3
    guide.column_dimensions["B"].width = 16      # 列名
    guide.column_dimensions["C"].width = 9       # 必填
    guide.column_dimensions["D"].width = 52      # 说明
    guide.column_dimensions["E"].width = 26      # 示例值
    guide.column_dimensions["F"].width = 26      # 取值一览

    guide.merge_cells("B2:F2")
    head = guide.cell(row=2, column=2, value=f"{table['title']} · 填写说明")
    head.font = Font(name="微软雅黑", size=16, color=primary)
    head.alignment = Alignment(horizontal="left", vertical="center")
    guide.row_dimensions[2].height = 32

    guide.merge_cells("B3:F3")
    intro = guide.cell(
        row=3, column=2,
        value=(f"谁填：{table['filler']}　→　转成：{table['output']}　"
               f"（列名与判定口径的唯一出处：{DOC_PATH}）"),
    )
    intro.font = caption
    guide.row_dimensions[3].height = 22

    headers = ("列名", "必填", "说明", "示例值", "取值一览")
    for offset, text in enumerate(headers):
        cell = guide.cell(row=4, column=2 + offset, value=text)
        cell.fill = PatternFill("solid", fgColor=primary)
        cell.font = Font(name="微软雅黑", size=11, color="FFFFFF")
        cell.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)
    guide.row_dimensions[4].height = 26

    for index, (name, required, note, sample, choices) in enumerate(columns):
        row = 5 + index
        values = (name, required, note, str(sample), " / ".join(choices) if choices else "自由填写")
        for offset, value in enumerate(values):
            cell = guide.cell(row=row, column=2 + offset, value=value)
            cell.font = body if offset == 0 else caption
            cell.alignment = wrap
            if index % 2:
                cell.fill = PatternFill("solid", fgColor=neutral_100)
        # 行高按"说明"列要折几行算（52 字符宽），保证长说明不被裁切
        guide.row_dimensions[row].height = max(20.0, 14.0 * (int(_display_width(note) / 46) + 1))

    note_row = 5 + len(columns) + 1
    guide.merge_cells(start_row=note_row, start_column=2, end_row=note_row, end_column=6)
    lead = guide.cell(row=note_row, column=2, value="填表纪律（九张表通用，口径见 docs/表格模板说明.md 第二节）")
    lead.font = Font(name="微软雅黑", size=11, color=primary)
    for index, line in enumerate(FOOTER_NOTES):
        row = note_row + 1 + index
        guide.merge_cells(start_row=row, start_column=2, end_row=row, end_column=6)
        cell = guide.cell(row=row, column=2, value=line)
        cell.font = caption
        cell.alignment = Alignment(horizontal="left", vertical="top", wrap_text=True)
        guide.row_dimensions[row].height = max(16.0, 14.0 * (int(_display_width(line) / 125) + 1))

    # 打印：两张 sheet 都按一页宽铺开，续页重复表头（数据表）
    guide.page_setup.orientation = "portrait"
    guide.page_setup.fitToWidth = 1
    guide.page_setup.fitToHeight = 0
    for sheet, title_rows in ((ws, f"{HEADER_ROW}:{HEADER_ROW}"), (guide, "4:4")):
        sheet.page_setup.orientation = sheet is ws and "landscape" or "portrait"
        sheet.page_setup.fitToWidth = 1
        sheet.page_setup.fitToHeight = 0
        sheet.sheet_properties.pageSetUpPr = PageSetupProperties(fitToPage=True)
        sheet.print_title_rows = title_rows

    wb.properties.creator = "hubflow 表格模板（scripts/make_table_templates.py）"
    out_dir.mkdir(parents=True, exist_ok=True)
    target = out_dir / f"{table['file']}_{date_tag}_{version}.xlsx"
    wb.save(target)
    return target


def ensure_outside_repo(repo_root: Path, out_dir: Path) -> None:
    """`.xlsx` 不许进仓库（doc_gate 第 2 组）——产物目录必须在仓库之外。"""
    resolved = out_dir.resolve()
    try:
        resolved.relative_to(repo_root.resolve())
    except ValueError:
        return
    raise SystemExit(
        f"拒绝写入仓库内目录：{resolved}\n"
        f"`.xlsx` 是禁入类型（doc_gate 第 2 组），模板实体只能落在共享盘。"
    )


def main() -> int:
    parser = argparse.ArgumentParser(description="生成 T1~T8 表格模板实体并校验列名")
    parser.add_argument("--out", help="共享盘上的目标目录（必须在仓库之外）")
    parser.add_argument("--date", default="20261013", help="文件名里的日期 YYYYMMDD（默认今天由调用方给）")
    parser.add_argument("--version", default="v1", help="版本号（默认 v1）")
    parser.add_argument("--check", action="store_true", help="只校验列名与 docs/表格模板说明.md 一致")
    parser.add_argument("--root", default=".", help="仓库根目录（默认当前目录）")
    args = parser.parse_args()

    repo_root = Path(args.root).resolve()
    problems = check_against_doc(repo_root)
    if problems:
        print(f"[失败] 列名与 {DOC_PATH} 对不上（{len(problems)} 条）：")
        for item in problems:
            print(f"  {item}")
        print("\n以 docs/表格模板说明.md 为准：改本脚本的列定义，不要改文档去迁就脚本。")
        return 1
    total = sum(len(t["columns"]) for t in TABLES)
    print(f"[通过] 列名校验：{len(TABLES)} 张表 / {total} 列，与 {DOC_PATH} 逐列一致")

    if args.check:
        return 0
    if not args.out:
        parser.error("没有 --out（也没有 --check）：要么给共享盘目录生成实体，要么只校验列名")

    out_dir = Path(args.out)
    ensure_outside_repo(repo_root, out_dir)
    for table in TABLES:
        path = build_workbook(table, out_dir / table["dir"], args.date, args.version)
        print(f"  生成 {path}  （{len(table['columns'])} 列，{path.stat().st_size} 字节）")
    print(f"\n共 {len(TABLES)} 份模板实体已落到：{out_dir.resolve()}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
