#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""hubflow 文档与契约门禁（CI 检查名 `ci`）。

用法：
    python scripts/doc_gate.py            # 在仓库根运行
    python scripts/doc_gate.py --root .   # 指定仓库根

它检查的是"机器能判、人却常漏"的六组事（口径见 docs/开发规范.md 第 2、5、11、13 节）：

  1. 编码与换行  受管文本文件是 UTF-8 且**不带 BOM**；一律 LF（`.bat` / `.cmd` 除外）
  2. 大文件与禁入类型  视频 / 权重 / 数据集 / 交付物 / `.env` 一律不进仓库；单文件 > 2 MiB 报错
  3. 相对链接    Markdown 里的相对链接必须能在仓库里找到目标（**围栏代码块里的链接不算**）
  4. JSON       受管 JSON 必须可解析；`docs/数据契约.md` 里的 json 围栏同样要能解析
                （围栏写法 ```` ```json ```` / ```` ```JSON ```` / `~~~json ```` 都认）
  5. 密钥扫描   常见密钥前缀 + `XXX_KEY=真值` + JSON 里的 `"xxx_key": "真值"`
  6. 契约字段   `stations/*.json` 与 `work/<目录>/samples/*.json` 的键名一律 `snake_case`

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

#: 键名必须是 snake_case（对应 docs/开发规范.md 第 2 节）
SNAKE_CASE = re.compile(r"^[a-z][a-z0-9_]*$")
#: 需要逐键检查的契约文件（相对仓库根）
CONTRACT_GLOBS = ("stations/*.json", "work/*/samples/*.json")

#: 这些文件里的 ```json 代码块**必须**是严格 JSON（契约示例就是下游的镜子）。
#: 其余文档里的 ```json 允许是"片段"或带 `//` 注释的示意（例如手册里摘一段字段），不做严格解析。
JSON_FENCE_STRICT_FILES = {"docs/数据契约.md"}

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
    """一次检查的结果：失败项 + 检查了多少个目标（0 个目标不许当通过）。"""

    def __init__(self, failures: list[Failure], scanned: int) -> None:
        self.failures = failures
        self.scanned = scanned


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


def is_text_file(path: Path) -> bool:
    return path.suffix.lower() in TEXT_SUFFIXES or path.name in TEXT_NAMES


# ---------------------------------------------------------------- 各项检查


def check_forbidden(repo: Repo) -> Check:
    """2/6 不该进仓库的文件与超大文件。"""
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
    """1/6 编码（UTF-8 无 BOM）与换行（LF）。"""
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
    """3/6 Markdown 相对链接可解析（围栏代码块内的链接不算）。"""
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
    """4/6 受管 JSON + 数据契约里的 ```json 代码块可解析。"""
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
    """5/6 常见密钥形态（含 `.env.example`：它最容易误贴真 Key）。"""
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
    """6/6 契约文件的键名必须是 snake_case（对应 docs/开发规范.md 第 2 节）。"""
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


#: (标题, 检查函数, 是否必检——目标数为 0 时是否算失败)
CHECKS = [
    ("1/6 编码与换行（UTF-8 无 BOM / LF）", check_encoding_and_eol, True),
    ("2/6 大文件与禁入类型", check_forbidden, True),
    ("3/6 Markdown 相对链接", check_markdown_links, True),
    ("4/6 JSON 可解析（含数据契约示例）", check_json, True),
    ("5/6 密钥扫描", check_secrets, True),
    ("6/6 契约字段命名（snake_case）", check_contract_keys, False),
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
        print("[失败] 0/6 文件清单为空")
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

    print()
    if total:
        print(f"门禁未通过：共 {len(total)} 条问题。逐条修完再 push（口径见 docs/协作规范.md 第 4 节）。")
        return 1
    print("门禁全部通过。")
    return 0


if __name__ == "__main__":
    sys.exit(main())
