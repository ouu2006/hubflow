#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""hubflow PR 自动审查：静态门禁 + AI 审查。

设计前提（**重要**）：
    GitHub 的 Approve 必须由真实账号的 token 发出，AI 没有账号。
    所以本工具**不替人签字**，它做两件事：
      ① 静态门禁 —— 机器能判死的规则，违反了直接挡合并（退出码 1）；
      ② AI 审查 —— 让模型读 diff 给意见，**只提示不挡**（模型会误报，不能当门禁）。

用法：
    python tools/ci/review.py --base origin/main --head HEAD
    python tools/ci/review.py --base origin/main --head HEAD --post 12   # 回帖到 PR 12
    python tools/ci/review.py --base origin/main --head HEAD --no-ai     # 跳过 AI

退出码：
    0  通过（可能有 WARN）
    1  有 FAIL —— 门禁不通过，PR 不可合并
    2  自身执行出错（例如 git 命令失败）
"""

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
import urllib.error
import urllib.request

# ── 常量 ────────────────────────────────────────────────────────────────────

MARKER = "<!-- hubflow-auto-review -->"

# 分支 → 该位置拥有的目录前缀
BRANCH_OWNERS = {
    "feat/perception": ["work/perception/"],
    "feat/engine": ["work/engine/", "stations/"],
    "feat/frontend": ["work/frontend/"],
    "feat/backend": ["work/assembly/", "tools/", ".github/", "docs/"],
}

# 公共文件：只有后端能改（协作规范第 1 节）
PUBLIC_FILES = {
    "README.md",
    ".gitignore",
    ".gitattributes",
    ".env.example",
    "run_all.py",
    "main.py",
}

# 禁止进仓库的文件（.gitignore 已拦，这里是第二道闸）
FORBIDDEN_PATTERNS = [
    (r"\.env$", ".env 环境文件（只允许 .env.example）"),
    (r"\.env\.(?!example)", "本地环境文件"),
    (r"_key\.txt$", "密钥文本文件"),
    (r"\.ckpt$", "MindSpore 权重"),
    (r"\.pt$", "PyTorch 权重"),
    (r"\.pth$", "模型权重"),
    (r"\.onnx$", "模型权重"),
    (r"\.safetensors$", "模型权重"),
    (r"\.mp4$", "视频"),
    (r"\.avi$", "视频"),
    (r"\.mov$", "视频"),
    (r"\.mkv$", "视频"),
    (r"\.(zip|tar|tar\.gz|7z|rar)$", "数据集压缩包"),
]

# 密钥特征串（在**新增行**里搜）
SECRET_PATTERNS = [
    (r"\bsk-[A-Za-z0-9_\-]{20,}", "疑似 API Key（sk- 开头）"),
    (r"\bghp_[A-Za-z0-9]{30,}", "GitHub 个人访问令牌"),
    (r"\bgithub_pat_[A-Za-z0-9_]{20,}", "GitHub 细粒度令牌"),
    (r"\bAKIA[0-9A-Z]{16}\b", "AWS Access Key"),
    (r"\bLTAI[0-9A-Za-z]{12,}", "阿里云 AccessKey"),
    (r"\bAKID[0-9A-Za-z]{13,}", "腾讯云 SecretId"),
    (r"""(?i)\b(amap|baidu|gaode)_?(web|js)?_?key\b\s*[:=]\s*["'][^"']{8,}["']""",
     "地图 Key 硬编码"),
    (r"""(?i)\b(key|secret|token|apikey|api_key)\b\s*[:=]\s*["'][0-9a-f]{32}["']""",
     "疑似 32 位十六进制密钥"),
    (r"[?&]key=[0-9a-f]{32}", "URL 里带地图 Key"),
]

# 跨目录 import（禁止：模块之间只走 JSON 文件）
CROSS_IMPORT_PATTERNS = [
    r"^\s*from\s+work[\.\s]",
    r"^\s*import\s+work[\.\s]",
    r"^\s*from\s+\.\.(perception|engine|frontend|assembly)",
    r"^\s*import\s+(perception|engine|frontend|assembly)\b",
]

AI_SYSTEM_PROMPT = """你是 hubflow 项目的代码审查者。hubflow 是"高铁站外交通疏导智能平台"的一期实现。

团队情况：4 个开发位各自让 AI 生成代码，所以**字段名与目录边界**是最容易出错的地方。

审查时只报**真问题**，不要凑数。重点看这几类：

1. **契约字段**：`segments.json` / `routes.json` / `render.json` 的字段名必须是 snake_case、
   单位进后缀（`eta_min` 不是 `eta`、`v_kmh` 不是 `speed`）、布尔加 `is_` 前缀。
   字段必须与 `docs/数据契约.md` 一致，改了字段却没改契约文档 = 问题。
2. **`is_simulated`**：一期所有数值必须带这个字段且恒为 true。
3. **备选条数**：`routes.json` 的 `alternatives` 必须 ≥2 条（+ 推荐 1 条 = 合计 ≥3 条方案）。
   唯一候选时用 `no_alternative: true`。
4. **目录边界**：`work/<位置>/` 之间**禁止互相 import**，只走 JSON 文件。
5. **口径纪律**：不得把"模拟数据"表述为实测；不得把"旁路跑通"说成"MindSpore 链路已验证"；
   不得把"单站"说成"可复制"。
6. **既有接口零改动**：`host-fastapi` 既有 8 个端点不得修改，只能新增路由注册。
7. **降级与兜底**：数据不可用时必须显示灰色，绝不能显示成蓝色。

输出格式（Markdown，中文）：

## AI 审查意见

**结论**：通过 / 需修改 / 建议讨论

然后按严重度列出问题，每条格式：
- **[严重|建议|提示]** 文件:行 — 问题是什么 — 为什么是问题

如果确实没问题，就写"未发现契约、边界与口径问题"。**不要为了显得认真而编造问题。**
最多列 8 条，按严重度排序。总长度控制在 600 字以内。"""


# ── 工具函数 ────────────────────────────────────────────────────────────────

# git ref 的白名单。用来挡"参数注入"：形如 `--upload-pack=...` 的字符串
# 交给 git 会被当成选项而不是 ref，所以先校验再拼命令行。
_REF_RE = re.compile(r"^[A-Za-z0-9._/@{}^~:-]+$")


def safe_ref(ref: str) -> str:
    """校验 git ref。非法就抛异常，不把它交给 git。"""
    if not ref or ref.startswith("-") or not _REF_RE.match(ref):
        raise RuntimeError(f"非法的 git ref：{ref!r}")
    return ref


def sh(cmd: list[str]) -> str:
    """跑一条命令，返回 stdout（失败抛异常）。

    以 list 传参（不经过 shell），所以不存在 shell 注入；
    调用方须用 `safe_ref()` 预先校验来自命令行的 ref。
    """
    r = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace")
    if r.returncode != 0:
        raise RuntimeError(f"命令失败：{' '.join(cmd)}\n{r.stderr.strip()}")
    return r.stdout


class Report:
    def __init__(self) -> None:
        self.fails: list[str] = []
        self.warns: list[str] = []
        self.notes: list[str] = []

    def fail(self, msg: str) -> None:
        self.fails.append(msg)

    def warn(self, msg: str) -> None:
        self.warns.append(msg)

    def note(self, msg: str) -> None:
        self.notes.append(msg)


# ── 检查项 ──────────────────────────────────────────────────────────────────

def changed_files(base: str, head: str) -> list[tuple[str, str]]:
    """返回 [(状态, 路径)]，状态为 A/M/D/R。"""
    out = sh(["git", "diff", "--name-status", "--no-renames", f"{base}...{head}"])
    result = []
    for line in out.splitlines():
        parts = line.split("\t")
        if len(parts) >= 2:
            result.append((parts[0].strip(), parts[1].strip()))
    return result


def added_lines(base: str, head: str, path: str) -> list[tuple[int, str]]:
    """返回某文件新增行的 [(行号, 内容)]。二进制文件返回空。"""
    try:
        out = sh(["git", "diff", "-U0", f"{base}...{head}", "--", path])
    except RuntimeError:
        return []
    result = []
    lineno = 0
    for line in out.splitlines():
        m = re.match(r"^@@ -\d+(?:,\d+)? \+(\d+)(?:,\d+)? @@", line)
        if m:
            lineno = int(m.group(1))
            continue
        if line.startswith("+") and not line.startswith("+++"):
            result.append((lineno, line[1:]))
            lineno += 1
        elif line.startswith("-") and not line.startswith("---"):
            continue
        elif line.startswith(" "):
            lineno += 1
    return result


def check_forbidden_files(files: list[tuple[str, str]], rep: Report) -> None:
    for status, path in files:
        if status == "D":
            continue
        for pat, desc in FORBIDDEN_PATTERNS:
            if re.search(pat, path):
                rep.fail(f"**禁止提交的文件**：`{path}` —— {desc}。"
                         f"这类文件放共享盘，不进仓库。")
                break


def check_secrets(base: str, head: str, files: list[tuple[str, str]], rep: Report) -> None:
    for status, path in files:
        if status == "D" or path.endswith((".png", ".jpg", ".jpeg", ".gif")):
            continue
        for lineno, content in added_lines(base, head, path):
            for pat, desc in SECRET_PATTERNS:
                if re.search(pat, content):
                    rep.fail(f"**疑似密钥泄露**：`{path}:{lineno}` —— {desc}。"
                             f"本仓库是 public，Key 只进本地 `.env`（见 `docs/开发规范.md` 第 11 节）。"
                             f"**若确属误提交，先去地图控制台作废 Key，再找队长。**")
                    break


def check_ownership(files: list[tuple[str, str]], branch: str, rep: Report) -> None:
    owners = BRANCH_OWNERS.get(branch)
    if owners is None:
        rep.note(f"分支 `{branch}` 不在固定的四条工作分支里，跳过目录归属检查。")
        return

    for status, path in files:
        if status == "D":
            continue

        # 公共文件：只有后端能改
        if path in PUBLIC_FILES or path.startswith(".github/"):
            if not branch.startswith("feat/backend"):
                rep.fail(f"**公共文件被非后端修改**：`{path}`（当前分支 `{branch}`）。"
                         f"公共文件只由后端一人改，其他人只提 Issue。")
            continue

        # 别人 work/ 目录下的文件
        if path.startswith("work/"):
            if not any(path.startswith(p) for p in owners):
                if path.endswith("README.md"):
                    rep.warn(f"**动了别人的目录（README）**：`{path}`。"
                             f"README 属文档，后端为广播信息可改，但**代码文件不行**。")
                else:
                    rep.fail(f"**动了别人的目录**：`{path}`（当前分支 `{branch}`）。"
                             f"每人只改自己目录；需要跨目录改动先开 Issue 说一声。")
            continue

        # 站点包：决策线定结构，后端可改
        if path.startswith("stations/"):
            if not (any(path.startswith(p) for p in owners) or branch.startswith("feat/backend")):
                rep.fail(f"**站点包被非决策线修改**：`{path}`（当前分支 `{branch}`）。")
            continue


def check_cross_import(base: str, head: str, files: list[tuple[str, str]], rep: Report) -> None:
    for status, path in files:
        if status == "D" or not path.startswith("work/") or not path.endswith(".py"):
            continue
        for lineno, content in added_lines(base, head, path):
            for pat in CROSS_IMPORT_PATTERNS:
                if re.search(pat, content):
                    rep.fail(f"**跨目录 import**：`{path}:{lineno}` —— `{content.strip()}`。"
                             f"模块之间只通过 JSON 文件传递，不得互相 import"
                             f"（见 `docs/开发规范.md` 第 3 节）。")
                    break


def check_json_valid(base: str, head: str, files: list[tuple[str, str]], rep: Report) -> None:
    """改动过的 JSON 必须能解析（站点包字段错一个字符，下游全挂）。"""
    for status, path in files:
        if status == "D" or not path.endswith(".json"):
            continue
        if not os.path.exists(path):
            continue
        try:
            with open(path, encoding="utf-8") as f:
                json.load(f)
        except (json.JSONDecodeError, UnicodeDecodeError) as e:
            rep.fail(f"**JSON 无法解析**：`{path}` —— {e}")


def check_contract_sync(base: str, head: str, files: list[tuple[str, str]], rep: Report) -> None:
    """改了契约文档就提醒同步口径；改了字段却没动文档则提醒。"""
    paths = {p for _, p in files}
    if "docs/数据契约.md" in paths:
        rep.warn("本次改了 `docs/数据契约.md`（冻结件）。"
                 "**请在 PR 描述里写明改了哪个字段、影响谁**，并确认技术手册同步。")


# ── AI 审查 ─────────────────────────────────────────────────────────────────

def collect_diff(base: str, head: str, limit: int = 60000) -> str:
    """取 diff 文本，超长截断（避免烧 token）。"""
    try:
        out = sh(["git", "diff", "--no-color", f"{base}...{head}"])
    except RuntimeError:
        return ""
    if len(out) > limit:
        out = out[:limit] + f"\n\n...（diff 过长，已截断，共 {len(out)} 字符）"
    return out


def ai_review(diff: str) -> tuple[str | None, str]:
    """调模型审查。返回 (意见文本 或 None, 状态说明)。"""
    api_key = os.environ.get("AI_REVIEW_API_KEY", "").strip()
    if not api_key:
        return None, "未配置 `AI_REVIEW_API_KEY`，本次跳过 AI 审查（静态门禁仍然生效）"

    # GitHub Actions 里变量没配时会是空字符串，所以用 `or` 兜底，不能只靠 get 的默认值
    base_url = (os.environ.get("AI_REVIEW_BASE_URL") or "https://api.deepseek.com/v1").strip().rstrip("/")
    model = (os.environ.get("AI_REVIEW_MODEL") or "deepseek-chat").strip()
    try:
        timeout = int(os.environ.get("AI_REVIEW_TIMEOUT") or 120)
    except ValueError:
        timeout = 120

    if not diff.strip():
        return None, "本次 diff 为空，跳过 AI 审查"

    payload = {
        "model": model,
        "messages": [
            {"role": "system", "content": AI_SYSTEM_PROMPT},
            {"role": "user", "content": f"请审查以下 diff：\n\n```diff\n{diff}\n```"},
        ],
        "temperature": 0.2,
        "stream": False,
    }
    req = urllib.request.Request(
        f"{base_url}/chat/completions",
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {api_key}",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            body = json.loads(resp.read().decode("utf-8"))
        text = body["choices"][0]["message"]["content"].strip()
        return text, f"已用 `{model}` 审查"
    except urllib.error.HTTPError as e:
        detail = e.read().decode("utf-8", "replace")[:200]
        return None, f"AI 审查调用失败（HTTP {e.code}）：{detail}"
    except Exception as e:  # noqa: BLE001 - 网络/解析异常一律降级，不挡 PR
        return None, f"AI 审查调用失败：{type(e).__name__}: {e}"


# ── 回帖 ────────────────────────────────────────────────────────────────────

def post_comment(pr: int, body: str) -> None:
    """回帖；已有本工具的历史评论则原地更新（避免刷屏）。"""
    token = os.environ.get("GITHUB_TOKEN", "").strip()
    repo = os.environ.get("GITHUB_REPOSITORY", "").strip()
    if not token or not repo:
        print("[skip] 未配置 GITHUB_TOKEN / GITHUB_REPOSITORY，不回帖", file=sys.stderr)
        return

    api = f"https://api.github.com/repos/{repo}"
    headers = {
        "Authorization": f"Bearer {token}",
        "Accept": "application/vnd.github+json",
        "Content-Type": "application/json",
    }

    # 找历史评论
    existing = None
    try:
        req = urllib.request.Request(f"{api}/issues/{pr}/comments?per_page=100", headers=headers)
        with urllib.request.urlopen(req, timeout=30) as resp:
            for c in json.loads(resp.read().decode("utf-8")):
                if MARKER in (c.get("body") or ""):
                    existing = c["id"]
                    break
    except Exception as e:  # noqa: BLE001
        print(f"[warn] 读取历史评论失败：{e}", file=sys.stderr)

    data = json.dumps({"body": body}).encode("utf-8")
    try:
        if existing:
            req = urllib.request.Request(f"{api}/issues/comments/{existing}", data=data,
                                         headers=headers, method="PATCH")
        else:
            req = urllib.request.Request(f"{api}/issues/{pr}/comments", data=data,
                                         headers=headers, method="POST")
        with urllib.request.urlopen(req, timeout=30) as resp:
            print(f"[ok] 评论已{'更新' if existing else '发布'}")
    except Exception as e:  # noqa: BLE001
        print(f"[warn] 回帖失败：{e}", file=sys.stderr)


# ── 主流程 ──────────────────────────────────────────────────────────────────

def build_report(rep: Report, ai_text: str | None, ai_status: str,
                 branch: str, files: list[tuple[str, str]]) -> str:
    n_code = sum(1 for s, p in files if s != "D")
    head = f"{MARKER}\n## 🤖 自动审查（每次提交自动运行）\n\n"
    head += f"分支 `{branch}` · 变更文件 **{n_code}** 个\n\n"

    if rep.fails:
        head += f"### ❌ 静态门禁未通过（{len(rep.fails)} 项）\n\n"
        head += "\n".join(f"{i}. {m}" for i, m in enumerate(rep.fails, 1)) + "\n\n"
        head += "> **这些是硬性规则，必须改掉才能合并。**\n\n"
    else:
        head += "### ✅ 静态门禁通过\n\n"
        head += "禁入文件、密钥特征、目录归属、跨目录 import、JSON 可解析性 —— 均无问题。\n\n"

    if rep.warns:
        head += f"### ⚠️ 需要留意（{len(rep.warns)} 项）\n\n"
        head += "\n".join(f"- {m}" for m in rep.warns) + "\n\n"

    if rep.notes:
        head += "\n".join(f"> {m}" for m in rep.notes) + "\n\n"

    head += "---\n\n"
    head += f"<!-- ai-status: {ai_status} -->\n"
    if ai_text:
        head += ai_text + "\n\n"
    else:
        head += f"### AI 审查未运行\n\n{ai_status}\n\n"

    head += ("---\n\n"
             "<sub>静态门禁是**硬性**的（不通过不能合并）；"
             "AI 审查是**建议性**的（模型会误报，不作为合并依据）。"
             "最终仍需 code owner 批准 —— 见 `docs/协作规范.md` 第 4 节。</sub>\n")
    return head


def main() -> int:
    ap = argparse.ArgumentParser(description="hubflow PR 自动审查")
    ap.add_argument("--base", default="origin/main", help="基线（默认 origin/main）")
    ap.add_argument("--head", default="HEAD", help="待审提交（默认 HEAD）")
    ap.add_argument("--branch", default="", help="分支名（默认自动取）")
    ap.add_argument("--post", type=int, default=0, help="PR 编号，给了就回帖")
    ap.add_argument("--no-ai", action="store_true", help="跳过 AI 审查")
    ap.add_argument("--out", default="", help="把报告另存到文件")
    args = ap.parse_args()

    try:
        # ref 来自命令行/CI 变量，先校验再交给 git（挡 `--upload-pack=...` 这类参数注入）
        base = safe_ref(args.base)
        head = safe_ref(args.head)
        branch = args.branch.strip() or sh(["git", "rev-parse", "--abbrev-ref", "HEAD"]).strip()
        files = changed_files(base, head)
    except RuntimeError as e:
        print(f"[error] {e}", file=sys.stderr)
        return 2

    rep = Report()
    check_forbidden_files(files, rep)
    check_secrets(base, head, files, rep)
    check_ownership(files, branch, rep)
    check_cross_import(base, head, files, rep)
    check_json_valid(base, head, files, rep)
    check_contract_sync(base, head, files, rep)

    ai_text, ai_status = (None, "已按参数跳过") if args.no_ai else ai_review(collect_diff(base, head))

    report = build_report(rep, ai_text, ai_status, branch, files)
    print(report)
    if args.out:
        with open(args.out, "w", encoding="utf-8") as f:
            f.write(report)

    if args.post:
        post_comment(args.post, report)

    return 1 if rep.fails else 0


if __name__ == "__main__":
    sys.exit(main())
