#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""hubflow 文档与契约门禁（CI 检查名 `ci`）。

用法：
    python scripts/doc_gate.py            # 在仓库根运行
    python scripts/doc_gate.py --root .   # 指定仓库根

它检查的是"机器能判、人却常漏"的七组事（口径见 docs/开发规范.md 第 2、5、11、13 节
与 docs/填表报告.md 第四节）：

  1. 编码与换行  受管文本文件是 UTF-8 且**不带 BOM**；一律 LF（`.bat` / `.cmd` 除外）
  2. 大文件与禁入类型  视频 / 权重 / 数据集 / 交付物 / `.env` 一律不进仓库；单文件 > 2 MiB 报错
  3. 相对链接    Markdown 里的相对链接必须能在仓库里找到目标（**围栏代码块里的链接不算**）
  4. JSON       受管 JSON 必须可解析；`docs/数据契约.md` 里的 json 围栏同样要能解析
                （围栏写法 ```` ```json ```` / ```` ```JSON ```` / `~~~json ```` 都认）
  5. 密钥扫描   常见密钥前缀 + `XXX_KEY=真值` + JSON 里的 `"xxx_key": "真值"`
  6. 契约字段   `stations/*.json` 与 `work/<目录>/samples/*.json` 的键名一律 `snake_case`
                （按 `_` 分段：每段全小写，或**单个大写字母**当单位符号，见开发规范第 2 节 `L_q_m`）
  7. 填表报告   `docs/填表报告.md` 的台账行格式合法（七列 / `结果` 枚举 / 日期格式）；
                **本次提交改动的每个 `stations/*.json` 都要有一行覆盖它**，且覆盖行不能写着
                "还没转"（`未重跑` / `待转`）—— 业务数据只从表格进，产物动一次就要留一次出处。
                「占位」= 产物在场但还没走到表格那一棒（结构骨架 / 运行产物 / 基线），算自洽但打 [注意]

**受管文本**指上表用到的这些扩展名与文件名（含 `.sh` / `.ps1` / `.bat` / `.ts` / `.vue` / `.ets` 等代码类，
以及 `.gitignore` / `.gitattributes` / `.env.example` / `CODEOWNERS`）；其余二进制或未列出的类型不看。

设计原则（与 CI 一致）：
  * **只读**，不修改任何文件；
  * **零依赖**，只用 Python 标准库（一期不引入需要联网的库）；
  * 失败必须能定位到**文件与行号**，不打印"检查失败"这种无法行动的信息；
  * **本地与 CI 看同一份内容**：已跟踪文件读 **git 索引里的 blob**（= CI checkout 后拿到的字节），
    未跟踪但没被忽略的新文件读工作区 —— 否则会出现"本地绿、CI 红"（新文件还没 `git add` 时）；
  * **不许空转**：检查目标数为 0 时，必检项直接判失败，非必检项打印"跳过"而**不算通过**。

退出码：0 = 全部通过；1 = 有失败项。

> ⚠️ 边界（写在明处）：密钥扫描只覆盖**常见形态**，它是"提醒"，**不是保险箱**——红线仍然是
> "不提交任何真实密钥"（docs/开发规范.md 第 13 节）。拿不准就把值放进 `.env`，仓库里只留变量名。
"""

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
from pathlib import Path

# ---------------------------------------------------------------- 常量

#: 受管文本文件的扩展名 / 文件名（其余文件不查编码、换行与密钥）。
#: 代码类扩展名也在这里 —— 密钥扫描与编码检查对它们同样适用。
TEXT_SUFFIXES = {
    ".md", ".py", ".json", ".yml", ".yaml", ".toml", ".txt", ".cfg", ".ini", ".csv",
    # 代码 / 脚本（一期尚无，二期与上游拷入的都会命中）
    ".sh", ".ps1", ".bat", ".cmd",
    ".ts", ".tsx", ".js", ".jsx", ".mjs", ".cjs", ".vue", ".ets",
    ".html", ".css", ".scss", ".sql",
}
TEXT_NAMES = {".gitignore", ".gitattributes", ".env.example", "CODEOWNERS"}

#: 允许 CRLF 的文件（Windows 批处理必须 CRLF 才能稳定执行；与 .gitattributes 一致）
CRLF_ALLOWED_SUFFIXES = {".bat", ".cmd"}

#: 绝对不许进仓库的扩展名（对应 docs/协作规范.md 第 8 节）
FORBIDDEN_SUFFIXES = {
    ".mp4", ".mov", ".avi", ".mkv", ".flv",      # 视频
    ".pt", ".pth", ".ckpt", ".onnx", ".safetensors", ".h5", ".pb",  # 模型权重
    ".zip", ".7z", ".rar", ".tar", ".gz",        # 打包产物 / 数据集
    ".xlsx", ".xls", ".docx", ".pdf",            # 交付物不入库，放共享盘
}
FORBIDDEN_NAMES = {".env"}

#: 单文件体积上限（字节）。超了说明它本来就不该进仓库
MAX_FILE_BYTES = 2 * 1024 * 1024

#: 常见密钥前缀（命中即失败）。占位符不算
SECRET_PATTERNS = [
    (re.compile(r"\bsk-[A-Za-z0-9]{16,}"), "OpenAI 风格密钥 sk-…"),
    (re.compile(r"\b(ghp|gho|ghs|ghu)_[A-Za-z0-9]{20,}"), "GitHub token"),
    (re.compile(r"\bgithub_pat_[A-Za-z0-9_]{20,}"), "GitHub PAT"),
    (re.compile(r"\bAKIA[0-9A-Z]{16}\b"), "AWS Access Key"),
    (re.compile(r"\bLTAI[0-9A-Za-z]{12,}\b"), "阿里云 AccessKey"),
]
#: `XXX_KEY=真值` 形态（.env / 代码 / 文档里的赋值）
ENV_ASSIGN = re.compile(
    r"^[ \t>|*\-]*(?:export[ \t]+)?([A-Z][A-Z0-9_]*(?:KEY|TOKEN|SECRET|PASSWORD|PASSWD))"
    r"[ \t]*[:=][ \t]*[\"']?([^\"'\s#]{16,})"
)
#: JSON 形态：`"amap_web_key": "真值"`（放在 stations/*.json 里的正是这类）
JSON_ASSIGN = re.compile(
    r"[\"']([A-Za-z0-9_]*(?:key|token|secret|password)[A-Za-z0-9_]*)[\"']\s*:\s*[\"']([^\"']{16,})[\"']",
    re.I,
)
PLACEHOLDER_HINTS = ("your", "xxx", "todo", "changeme", "placeholder", "<", "${", "example", "占位")

#: Markdown 链接：](target) 或 ](<target with spaces>) 或 ](target "title")
MD_LINK = re.compile(r"\]\(\s*(?:<([^>]*)>|([^)\s]*))(?:\s+[\"'][^\"']*[\"'])?\s*\)")
#: 围栏代码块（``` / ~~~，带 info string）。用于：① 拆出 JSON 块；② 扫链接前把围栏内容挖空，
#: 免得把示例代码里的 `[x](路径)` 当成真链接误报。
MD_FENCE = re.compile(r"(?ims)^[ \t]*(?P<fence>`{3,}|~{3,})[ \t]*(?P<info>[^\r\n]*)\r?\n.*?^[ \t]*(?P=fence)[ \t]*$")
#: 围栏里的 JSON / JSONC（大小写不敏感 —— ```JSON 也得算）
MD_JSON_FENCE = re.compile(
    r"(?ims)^[ \t]*(?P<fence>`{3,}|~{3,})[ \t]*jsonc?[ \t]*\r?\n(?P<body>.*?)^[ \t]*(?P=fence)[ \t]*$"
)

#: 键名必须是 snake_case（对应 docs/开发规范.md 第 2 节）。
#: 该节把「小写下划线」和「单位进后缀」并列为规则，正例栏里就有 `L_q_m`、`T_d_min`
#: ——所以**单个大写字母是合法的单位符号**（L = 长度、T = 时间），不能按"全小写"一刀切。
#: 按 `_` 分段校验：每段要么全小写（可带数字），要么是**单个**大写字母。
#: 这样 `L_q_m` / `L_seg_m` / `T_d_min` / `v_kmh` / `is_simulated` 通过，
#: 而 `segmentId` / `SegmentID` / `Speed` 这些真正的驼峰 / 帕斯卡命名仍被拦下。
SNAKE_CASE = re.compile(r"^(?:[a-z][a-z0-9]*|[A-Z])(?:_(?:[a-z][a-z0-9]*|[A-Z]))*$")
#: 需要逐键检查的契约文件（相对仓库根）
CONTRACT_GLOBS = ("stations/*.json", "work/*/samples/*.json")

#: 这些文件里的 ```json 代码块**必须**是严格 JSON（契约示例就是下游的镜子）。
#: 其余文档里的 ```json 允许是"片段"或带 `//` 注释的示意（例如手册里摘一段字段），不做严格解析。
JSON_FENCE_STRICT_FILES = {"docs/数据契约.md"}

#: 填表报告台账（第 7 组检查）。口径见 docs/填表报告.md 第四节。
FILL_REPORT = "docs/填表报告.md"
#: 台账章节的标题（解析起点：只认这一节里的表格，前面的"一行示例"不算台账）
FILL_LEDGER_HEADING = "填表报告台账"
#: `结果` 只许这五种取值（"过没过"的正式判定归池·Q 的 T7，报告只如实登记）
FILL_RESULTS = ("已转", "已核对", "占位", "未重跑", "待转")
#: 「占位」：产物在场，但还没走到表格那一棒（结构骨架 / 直接运行产物 / 基线登记）。
#: 它和 `已转` / `已核对` 有明确分工：后者说"有表格出处"，前者说"还没有，别当数据用"。
#: 所以覆盖行取它算「自洽」，但**单独打 [注意]**——详见 docs/填表报告.md 第 3.1 节。
FILL_RESULT_PLACEHOLDER = "占位"
#: 这两种取值不硬拦，但会打印 [注意] 点名（需要人在 PR 里说明为什么）
FILL_RESULTS_NOTICE = ("未重跑", "待转")
#: 台账里代表"这一版产物**有表格出处**"的取值（覆盖行取这两种之一时不需要额外说明）
FILL_RESULTS_OK = ("已转", "已核对")
#: 台账列数（表 / 提交者 / 表版本 / 产物 / 依据 / 结果 / 日期）
FILL_COLUMNS = 7
#: 表格转换脚本产物（改了这些就必须在台账里留一行）
PRODUCT_GLOB = "stations/*.json"
#: CI 传进来的"本次改动清单"：文件路径（换行分隔的相对路径）优先，其次是内联内容。
#: 两者都没给时回退到本地 git。详见 Repo.changed_files。
CHANGED_FILE_ENV = "DOC_GATE_CHANGED_FILE"
CHANGED_ENV = "DOC_GATE_CHANGED"

#: 回退枚举（没有 git 时）跳过的目录名
SKIP_DIRS = {".git", "node_modules", "__pycache__", ".venv", "out", "dist", ".pytest_cache"}


class Failure:
    """一条失败项：文件 + 行号（可空）+ 原因。"""

    def __init__(self, path: str, message: str, line: int | None = None) -> None:
        self.path = path
        self.message = message
        self.line = line

    def __str__(self) -> str:
        where = f"{self.path}:{self.line}" if self.line else self.path
        return f"  {where}  {self.message}"


class Check:
    """一次检查的结果：失败项 + 检查了多少个目标（0 个目标不许当通过）+ 不算失败的提醒。"""

    def __init__(self, failures: list[Failure], scanned: int, notes: list[str] | None = None) -> None:
        self.failures = failures
        self.scanned = scanned
        self.notes = notes or []


# ---------------------------------------------------------------- 仓库读取


class Repo:
    """文件清单 + 内容读取。

    已跟踪文件的内容**优先从 git 索引读**（`git show :<path>`）：那正是 CI checkout 后拿到的字节，
    这样本地与 CI 的结论一致（工作区的 CRLF、未 `git add` 的新文件都不会再造成分歧）。
    索引里没有的（新文件）读工作区。
    """

    def __init__(self, root: Path) -> None:
        self.root = root
        self._content: dict[str, bytes | None] = {}
        self.files: list[Path] = []
        self.tracked: set[str] = set()
        self._collect()

    def _git(self, *args: str) -> bytes | None:
        try:
            return subprocess.run(
                ["git", "-C", str(self.root), *args],
                capture_output=True, check=True, text=False,
            ).stdout
        except (OSError, subprocess.CalledProcessError):
            return None

    def _collect(self) -> None:
        # 已跟踪 + 未跟踪但没被忽略的新文件（后者是"马上会被提交"的东西，CI 也会看到）
        cached = self._git("ls-files", "-z", "--cached")
        others = self._git("ls-files", "-z", "--others", "--exclude-standard")
        if cached is not None:
            cached_names = [n for n in cached.decode("utf-8", "surrogateescape").split("\0") if n]
            other_names = (
                [n for n in others.decode("utf-8", "surrogateescape").split("\0") if n]
                if others is not None else []
            )
            self.tracked = set(cached_names)
            self.files = [self.root / n for n in cached_names + other_names]
            if self.files:
                return

        # 没有 git（或空仓库）时回退为遍历：只按相对路径判断要跳过的目录，
        # 否则仓库路径里带 dist / out 这类名字时整棵树会被误跳过。
        for path in self.root.rglob("*"):
            rel_parts = path.relative_to(self.root).parts
            if any(part in SKIP_DIRS for part in rel_parts):
                continue
            if path.is_file():
                self.files.append(path)

    def read(self, path: Path) -> bytes | None:
        """读文件内容：已跟踪 → 索引 blob；否则 → 工作区。"""
        rel = path.relative_to(self.root).as_posix()
        if rel in self._content:
            return self._content[rel]

        data: bytes | None = None
        if rel in self.tracked:
            data = self._git("show", f":{rel}")
        if data is None:
            try:
                data = path.read_bytes()
            except OSError:
                data = None
        self._content[rel] = data
        return data

    def exists(self, target: Path) -> bool:
        """链接目标是否存在：工作区里有，或（已删但仍在索引里的）跟踪文件。"""
        if target.exists():
            return True
        try:
            rel = target.relative_to(self.root).as_posix()
        except ValueError:
            return False
        return rel in self.tracked

    def changed_files(self) -> set[str] | None:
        """本次提交改动的文件（相对路径）。

        CI 优先读 `DOC_GATE_CHANGED_FILE`（改动清单文件，PR 相对 base），其次内联的
        `DOC_GATE_CHANGED`；两者都**设置了**（哪怕为空串）就以它为准 —— 空串的含义是
        "本次确实没改任何文件"，与"没设置"（不知道改了什么）是两回事。
        本地回退到 git：`diff HEAD`（已暂存 + 未暂存）加上未跟踪的新文件。
        都拿不到时返回 None —— 调用方按"未知"处理，不能把"不知道改了什么"当成"什么都没改"。
        """
        if CHANGED_FILE_ENV in os.environ:
            try:
                raw = Path(os.environ[CHANGED_FILE_ENV]).read_text(encoding="utf-8")
            except OSError:
                return None
            return {line.strip() for line in raw.splitlines() if line.strip()}
        if CHANGED_ENV in os.environ:
            return {line.strip() for line in os.environ[CHANGED_ENV].splitlines() if line.strip()}

        diff = self._git("diff", "--name-only", "HEAD")
        if diff is None:
            return None
        names = {n for n in diff.decode("utf-8", "surrogateescape").splitlines() if n}
        others = self._git("ls-files", "-z", "--others", "--exclude-standard")
        if others is not None:
            names |= {n for n in others.decode("utf-8", "surrogateescape").split("\0") if n}
        return names

    def last_commit_date(self, rel: str) -> str | None:
        """某个文件最近一次改动的日期（YYYY-MM-DD，取**作者日期**）；查不到返回 None。

        取作者日期（`%as`）而不是提交日期（`%cs`）：变基与压缩合并会重写提交日期，
        但**作者日期会被保留** —— 否则正常的一次 rebase 就会让台账日期与产物"对不上"。
        """
        out = self._git("log", "-1", "--format=%as", "--", rel)
        if out is None:
            return None
        text = out.decode("utf-8", "replace").strip()
        return text or None


def is_text_file(path: Path) -> bool:
    return path.suffix.lower() in TEXT_SUFFIXES or path.name in TEXT_NAMES


# ---------------------------------------------------------------- 各项检查


def check_forbidden(repo: Repo) -> Check:
    """2/7 不该进仓库的文件与超大文件。"""
    failures: list[Failure] = []
    for path in repo.files:
        rel = path.relative_to(repo.root).as_posix()
        if path.name in FORBIDDEN_NAMES or path.suffix.lower() in FORBIDDEN_SUFFIXES:
            failures.append(Failure(rel, "这类文件不许进仓库（放共享盘，路径写进 README）"))
            continue
        data = repo.read(path)
        if data is not None and len(data) > MAX_FILE_BYTES:
            failures.append(
                Failure(rel, f"{len(data) / 1048576:.1f} MiB 超过 {MAX_FILE_BYTES // 1048576} MiB 上限")
            )
    return Check(failures, len(repo.files))


def check_encoding_and_eol(repo: Repo) -> Check:
    """1/7 编码（UTF-8 无 BOM）与换行（LF）。"""
    failures: list[Failure] = []
    scanned = 0
    for path in repo.files:
        if not is_text_file(path):
            continue
        scanned += 1
        rel = path.relative_to(repo.root).as_posix()
        data = repo.read(path)
        if data is None:
            continue
        if data.startswith(b"\xef\xbb\xbf"):
            failures.append(Failure(rel, "带 UTF-8 BOM —— 用 Python 写文件（encoding='utf-8'，不要用 Set-Content -Encoding utf8）"))
        try:
            text = data.decode("utf-8")
        except UnicodeDecodeError as exc:
            failures.append(Failure(rel, f"不是合法 UTF-8（第 {exc.start} 字节起）"))
            continue
        if path.suffix.lower() not in CRLF_ALLOWED_SUFFIXES and "\r\n" in text:
            first = text[: text.index("\r\n")].count("\n") + 1
            failures.append(Failure(rel, "含 CRLF 换行 —— 本仓库统一 LF（.gitattributes 已强制）", first))
    return Check(failures, scanned)


def blank_out_fences(text: str) -> str:
    """把围栏代码块的内容挖空（保留换行数，行号不变）—— 代码示例里的链接不算链接。"""
    return MD_FENCE.sub(lambda m: "\n" * m.group(0).count("\n"), text)


def check_markdown_links(repo: Repo) -> Check:
    """3/7 Markdown 相对链接可解析（围栏代码块内的链接不算）。"""
    failures: list[Failure] = []
    scanned = 0
    for path in repo.files:
        if path.suffix.lower() != ".md":
            continue
        scanned += 1
        rel = path.relative_to(repo.root).as_posix()
        data = repo.read(path)
        if data is None:
            continue
        text = blank_out_fences(data.decode("utf-8", "replace"))
        for lineno, line in enumerate(text.splitlines(), 1):
            for match in MD_LINK.finditer(line):
                target = (match.group(1) or match.group(2) or "").strip()
                if not target or target.startswith(("http://", "https://", "mailto:", "tel:", "#", "data:")):
                    continue
                target = target.split("#", 1)[0]
                if not target:
                    continue
                candidate = (path.parent / target.replace("%20", " ")).resolve()
                if not repo.exists(candidate):
                    failures.append(Failure(rel, f"链接指向的文件不存在：{target}", lineno))
    return Check(failures, scanned)


def check_json(repo: Repo) -> Check:
    """4/7 受管 JSON + 数据契约里的 ```json 代码块可解析。"""
    failures: list[Failure] = []
    scanned = 0
    for path in repo.files:
        if path.suffix.lower() != ".json":
            continue
        scanned += 1
        rel = path.relative_to(repo.root).as_posix()
        data = repo.read(path)
        if data is None:
            continue
        try:
            json.loads(data.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            failures.append(Failure(rel, f"JSON 解析失败：{exc}"))

    for rel in sorted(JSON_FENCE_STRICT_FILES):
        path = repo.root / rel
        data = repo.read(path)
        if data is None:
            continue
        text = data.decode("utf-8", "replace")
        matches = list(MD_JSON_FENCE.finditer(text))
        scanned += len(matches)
        for index, match in enumerate(matches, 1):
            block = match.group("body")
            try:
                json.loads(block)
            except json.JSONDecodeError as exc:
                line = text[: match.start("body")].count("\n") + 1 + exc.lineno - 1
                failures.append(Failure(rel, f"第 {index} 个 json 代码块不可解析：{exc.msg}", line))
    return Check(failures, scanned)


def check_secrets(repo: Repo) -> Check:
    """5/7 常见密钥形态（含 `.env.example`：它最容易误贴真 Key）。"""
    failures: list[Failure] = []
    scanned = 0
    for path in repo.files:
        if not is_text_file(path):
            continue
        scanned += 1
        rel = path.relative_to(repo.root).as_posix()
        data = repo.read(path)
        if data is None:
            continue
        text = data.decode("utf-8", "replace")
        for lineno, line in enumerate(text.splitlines(), 1):
            for pattern, label in SECRET_PATTERNS:
                if pattern.search(line):
                    failures.append(Failure(rel, f"疑似真实密钥（{label}）", lineno))
            for regex, fmt in ((ENV_ASSIGN, "{0}"), (JSON_ASSIGN, "\"{0}\"")):
                match = regex.search(line) if regex is JSON_ASSIGN else regex.match(line)
                if match and not any(hint in match.group(2).lower() for hint in PLACEHOLDER_HINTS):
                    failures.append(Failure(rel, f"疑似把真实值写进了 {fmt.format(match.group(1))}", lineno))
    return Check(failures, scanned)


def check_contract_keys(repo: Repo) -> Check:
    """6/7 契约文件的键名必须是 snake_case（对应 docs/开发规范.md 第 2 节）。"""
    failures: list[Failure] = []
    scanned = 0
    for path in repo.files:
        rel = path.relative_to(repo.root).as_posix()
        if not any(path.match(glob) for glob in CONTRACT_GLOBS):
            continue
        scanned += 1
        data = repo.read(path)
        if data is None:
            continue
        try:
            payload = json.loads(data.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError):
            continue  # 解析失败已由 check_json 报过
        for key, where in iter_keys(payload):
            if not SNAKE_CASE.match(key):
                failures.append(Failure(rel, f"字段名不是 snake_case：{key}（位置 {where}）"))
    return Check(failures, scanned)


def iter_keys(node, where: str = "$"):
    """递归产出 (键, 位置)。"""
    if isinstance(node, dict):
        for key, value in node.items():
            yield str(key), where
            yield from iter_keys(value, f"{where}.{key}")
    elif isinstance(node, list):
        for index, value in enumerate(node):
            yield from iter_keys(value, f"{where}[{index}]")


def parse_fill_ledger(text: str) -> tuple[list[dict], list[Failure]]:
    """解析 `docs/填表报告.md` 的台账表格。

    返回 (行列表, 格式失败项)。只解析 `## …填表报告台账` 之后第一个表格 —— 本文件前面的
    "一行示例"与列说明不在台账里，不能混进来。
    """
    lines = text.splitlines()
    start = None
    for index, line in enumerate(lines):
        if line.startswith("## ") and FILL_LEDGER_HEADING in line:
            start = index + 1
            break
    if start is None:
        return [], [Failure(FILL_REPORT, f"找不到台账章节（`## …{FILL_LEDGER_HEADING}`）—— 第 7 组检查无法判")]

    rows: list[dict] = []
    failures: list[Failure] = []
    header_seen = False
    for offset, line in enumerate(lines[start:], start + 1):
        stripped = line.strip()
        if not stripped.startswith("|"):
            if header_seen and rows:
                break          # 表格结束
            if header_seen:
                continue       # 表头与表体之间的分隔行
            continue           # 还没到表格
        cells = [c.strip() for c in stripped.strip("|").split("|")]
        if all(set(c) <= set("-: ") and c for c in cells):
            header_seen = True
            continue           # `|---|---|` 分隔行
        if not header_seen:
            header_seen = True
            continue           # 表头行
        if len(cells) != FILL_COLUMNS:
            failures.append(
                Failure(FILL_REPORT, f"台账行应为 {FILL_COLUMNS} 列（表/提交者/表版本/产物/依据/结果/日期），实为 {len(cells)} 列", offset)
            )
            continue
        rows.append({
            "line": offset,
            "table": cells[0],
            "author": cells[1],
            "version": cells[2],
            "products": cells[3],
            "basis": cells[4],
            "result": cells[5],
            "date": cells[6],
        })

    if not rows:
        failures.append(Failure(FILL_REPORT, "台账里一行都没有 —— 至少要有基线行，否则第 7 组检查无法判"))
        return [], failures

    for row in rows:
        lineno = row["line"]
        if row["result"] not in FILL_RESULTS:
            failures.append(
                Failure(FILL_REPORT, f"`结果` 只能是 {' / '.join(FILL_RESULTS)} 之一，实为「{row['result']}」", lineno)
            )
        if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", row["date"]):
            failures.append(Failure(FILL_REPORT, f"`日期` 必须是 YYYY-MM-DD，实为「{row['date']}」", lineno))
        for key, label in (("table", "表"), ("author", "提交者"), ("version", "表版本"),
                           ("products", "产物"), ("basis", "依据")):
            if not row[key]:
                failures.append(Failure(FILL_REPORT, f"`{label}` 不能为空", lineno))
    return rows, failures


def products_in(cell: str) -> set[str]:
    """从台账的「产物」列里抠出 `stations/*.json` 路径（反引号包裹或裸路径都认）。"""
    return set(re.findall(r"(stations/[A-Za-z0-9_./-]+\.json)", cell))


def check_fill_report(repo: Repo) -> Check:
    """7/7 填表报告台账：行格式 + 本次改动的产物都被覆盖 + 覆盖行的 `结果` 与产物在场状态自洽。

    日期对账只打 [注意]：变基 / 压缩合并会重写提交日期，硬拦会误伤正常流程。
    """
    failures: list[Failure] = []
    notes: list[str] = []

    data = repo.read(repo.root / FILL_REPORT)
    if data is None:
        return Check(
            [Failure(FILL_REPORT, "文件不存在 —— 业务数据只从表格进，产物动一次就要留一次出处（见 docs/表格模板说明.md 第 1 节）")],
            0,
        )
    rows, format_failures = parse_fill_ledger(data.decode("utf-8", "replace"))
    failures.extend(format_failures)

    # 仓库里当前在场的产物（含已跟踪 + 未跟踪新文件），以及它们在台账里被谁覆盖
    present = sorted(
        rel for rel in (p.relative_to(repo.root).as_posix() for p in repo.files)
        if Path(rel).match(PRODUCT_GLOB)
    )
    scanned = len(rows) + len(present)

    covered: dict[str, list[dict]] = {}
    for row in rows:
        for product in products_in(row["products"]):
            covered.setdefault(product, []).append(row)
        if not products_in(row["products"]):
            continue
        if row["result"] in FILL_RESULTS_NOTICE:
            notes.append(
                f"{FILL_REPORT}:{row['line']}  `结果` 是「{row['result']}」（{row['table']} → {row['products']}）"
                "—— 需要有人在 PR 里说明为什么，不能就这样算了"
            )
        elif row["result"] == FILL_RESULT_PLACEHOLDER:
            notes.append(
                f"{FILL_REPORT}:{row['line']}  `结果` 是「{FILL_RESULT_PLACEHOLDER}」（{row['table']} → {row['products']}）"
                "—— 登记的是「还没有表格出处」的产物（结构骨架 / 运行产物 / 基线）；"
                "它只说明**在场**，**不代表数据可用**，不要拿它当「已转」的证据"
            )

    changed = repo.changed_files()
    if changed is None:
        notes.append(
            f"拿不到本次改动清单（没有 {CHANGED_FILE_ENV} / {CHANGED_ENV}，且 git 不可用）"
            "—— 只校验了台账格式，没查产物覆盖"
        )
    else:
        for product in sorted(p for p in changed if Path(p).match(PRODUCT_GLOB)):
            if product not in present:
                # 删产物也必须有出处：台账里要有一行点名这个文件（`产物` 列写它即可）。
                if product in covered:
                    notes.append(
                        f"{FILL_REPORT}:{covered[product][0]['line']}  本次提交删除了产物 {product}"
                        "，台账里已有点名它的行 —— 确认那一行说清了为什么删（复核留痕）"
                    )
                else:
                    failures.append(
                        Failure(FILL_REPORT, f"本次提交删除了产物 {product}，台账里要有对应的一行说清处置（当前没有）")
                    )
            elif product not in covered:
                failures.append(
                    Failure(FILL_REPORT, f"本次提交改了 {product}，但台账里没有覆盖它的行 —— 补一行说清「哪张表第几版 → 这个产物」")
                )

    # 新鲜度：覆盖某产物的最新一行，日期要与该产物最近一次改动的提交同一天。
    # 只打 [注意] 不判失败 —— 变基 / 压缩合并会重写提交日期，硬拦会误伤正常流程；
    # 但"覆盖行是旧的"必须看得见，否则老行会把新改动吞掉。
    for product in present:
        entries = covered.get(product)
        if not entries or product not in (changed or set()):
            continue  # 本次没动它：不追溯历史，只保证"动的时候有行、日期对得上"
        latest = max(entries, key=lambda r: (r["date"], r["line"]))
        if latest["result"] not in FILL_RESULTS_OK and latest["result"] != FILL_RESULT_PLACEHOLDER:
            failures.append(
                Failure(FILL_REPORT, f"{product} 的覆盖行 `结果` 是「{latest['result']}」—— 产物在场就必须是 已转 / 已核对 / 占位", latest["line"])
            )
        product_date = repo.last_commit_date(product)
        if product_date and product_date != latest["date"]:
            notes.append(
                f"{FILL_REPORT}:{latest['line']}  {product} 最近一次改动是 {product_date}，覆盖行日期是 {latest['date']}"
                f" —— 两者应当是同一天：把覆盖行日期改成 {product_date}（变基 / 压缩合并会让两者天然不同天，那时可忽略）"
            )
    return Check(failures, scanned, notes)


#: (标题, 检查函数, 是否必检——目标数为 0 时是否算失败)
CHECKS = [
    ("1/7 编码与换行（UTF-8 无 BOM / LF）", check_encoding_and_eol, True),
    ("2/7 大文件与禁入类型", check_forbidden, True),
    ("3/7 Markdown 相对链接", check_markdown_links, True),
    ("4/7 JSON 可解析（含数据契约示例）", check_json, True),
    ("5/7 密钥扫描", check_secrets, True),
    ("6/7 契约字段命名（snake_case）", check_contract_keys, False),
    # 第 7 组不是"没有目标就不判"的检查：本文件不存在、或台账为空，都在函数里直接判失败。
    ("7/7 填表报告台账（格式 / 产物覆盖 / 结果语义）", check_fill_report, True),
]


def main() -> int:
    parser = argparse.ArgumentParser(description="hubflow 文档与契约门禁")
    parser.add_argument("--root", default=".", help="仓库根目录（默认当前目录）")
    args = parser.parse_args()

    root = Path(args.root).resolve()
    repo = Repo(root)
    print(f"门禁根目录：{root}")
    print(f"受管文件：{len(repo.files)} 个（已跟踪 {len(repo.tracked)} 个，内容取自 git 索引）\n")

    total: list[Failure] = []
    if not repo.files:
        total.append(Failure(str(root), "一个受管文件都没找到 —— 门禁拒绝在空集合上判通过（检查 --root 是否指对了仓库根）"))
        print("[失败] 0/7 文件清单为空")
    else:
        for title, check, mandatory in CHECKS:
            result = check(repo)
            total.extend(result.failures)
            if result.failures:
                print(f"[失败] {title}（检查 {result.scanned} 个目标，{len(result.failures)} 条问题）")
                for item in result.failures:
                    print(item)
            elif result.scanned == 0 and mandatory:
                message = "没有任何可检查的目标（0 个）—— 不许当成通过"
                total.append(Failure(str(root), f"{title}：{message}"))
                print(f"[失败] {title}：{message}")
            elif result.scanned == 0:
                print(f"[跳过] {title}：当前没有这类文件（不计入通过）")
            else:
                print(f"[通过] {title}（检查 {result.scanned} 个目标）")
            for note in result.notes:
                print(f"[注意] {note}")

    print()
    if total:
        print(f"门禁未通过：共 {len(total)} 条问题。逐条修完再 push（口径见 docs/协作规范.md 第 4 节）。")
        return 1
    print("门禁全部通过。")
    return 0


if __name__ == "__main__":
    sys.exit(main())
