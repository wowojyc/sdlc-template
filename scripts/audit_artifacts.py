"""产物链状态推导 —— 把"需求链路"变成可审计的确定性事实。

链路（每环一个提交的产物）：
    Issue（原始需求）→ intent/<slug>.md（MRD）→ spec/<slug>.md（PRD）
    → plan/<slug>.md（技术方案）→ src/（代码）→ tests/（测试）

关键设计（与 detect_drift.py 同一铁律）：
  **检测保持确定性** —— 不用 AI 判断链路状态。
  文件存在性与顺序全部脚本算，结果可复现、可审计、有单测。

文档链按需求（slug）独立成行，且是弹性的：
  · intent 是每个需求的源头（登记处），必须有
  · spec / plan 按需存在 —— 不需要设计/开发的需求可以不写
  · 需求完成即归档：intent/spec/plan 三份文档一起移入各自 archive/

判读规则：
  · 阶段 = 活跃需求文档链最靠后的环节（intent → spec → plan）
  · 断链 = 顶层 spec/<slug>.md 或 plan/<slug>.md 的 slug 不在活跃 intent 里
    （孤儿文档：需求源头缺失，或需求已归档但文档没跟着归档）
  · src/ tests/ 是仓库共享现状（不归属任何需求），只展示、不推高阶段

用法:
    # JSON 输出（机器可读，退出码供 CI 判断）
    python scripts/audit_artifacts.py

    # 人读的进度表
    python scripts/audit_artifacts.py --format markdown

输出（stdout，JSON）:
    {"stage": "intent", "stage_label": "需求已登记（MRD 已提交）", "ok": true,
     "artifacts": [{"name": "intent", "path": "intent", "label": "01 规划 · MRD",
                    "exists": true}, ...],
     "requirements": [{"slug": "flow-tracking", "intent": true, "spec": false,
                       "plan": false, "stage": "intent"}],
     "broken_links": []}
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

# 产物链定义：顺序即流程；intent 必有，spec/plan 按需，src/tests 为共享环节
ARTIFACTS: list[dict] = [
    {"name": "intent", "path": "intent", "kind": "docs", "label": "01 规划 · MRD"},
    {"name": "spec", "path": "spec", "kind": "docs", "label": "02 设计 · PRD"},
    {"name": "plan", "path": "plan", "kind": "docs", "label": "03 计划 · 技术方案"},
    {"name": "src", "path": "src", "kind": "src", "label": "04 构建 · 代码"},
    {"name": "tests", "path": "tests", "kind": "tests", "label": "05 测试 · 用例"},
]

STAGE_LABELS: dict[str, str] = {
    "none": "无活跃需求（链路未启动）",
    "intent": "需求已登记（MRD 已提交）",
    "spec": "设计中（PRD 已产出）",
    "plan": "已计划（技术方案已产出）",
}

# 文档链环节顺序（src/tests 是共享现状，不参与需求阶段）
STAGE_ORDER: dict[str, int] = {"intent": 0, "spec": 1, "plan": 2}


def _top_md_slugs(root: Path, rel: str) -> set[str]:
    """收集目录顶层 *.md 的 slug 集合（archive/ 归档不计）。"""
    d = root / rel
    if not d.is_dir():
        return set()
    return {p.stem for p in d.glob("*.md")}


def artifact_exists(root: Path, item: dict) -> bool:
    """按产物类型判定存在性：docs 看顶层 *.md；src 需有 .py；tests 需有 test_*.py。"""
    p = root / item["path"]
    if item["kind"] == "docs":
        return any(p.glob("*.md"))
    if item["kind"] == "src":
        return p.is_dir() and any(p.glob("*.py"))
    if item["kind"] == "tests":
        return p.is_dir() and any(p.glob("test_*.py"))
    return p.is_file()


def audit(root: Path) -> dict:
    """推导产物链状态：各环节存在性、活跃需求文档链进度、孤儿文档断链。"""
    active_intents = _top_md_slugs(root, "intent")
    active_specs = _top_md_slugs(root, "spec")
    active_plans = _top_md_slugs(root, "plan")

    artifacts = [
        {"name": "intent", "path": "intent", "label": "01 规划 · MRD", "exists": bool(active_intents)},
        {"name": "spec", "path": "spec", "label": "02 设计 · PRD", "exists": bool(active_specs)},
        {"name": "plan", "path": "plan", "label": "03 计划 · 技术方案", "exists": bool(active_plans)},
        {
            "name": "src",
            "path": "src",
            "label": "04 构建 · 代码",
            "exists": artifact_exists(root, {"kind": "src", "path": "src"}),
        },
        {
            "name": "tests",
            "path": "tests",
            "label": "05 测试 · 用例",
            "exists": artifact_exists(root, {"kind": "tests", "path": "tests"}),
        },
    ]

    # 每个活跃需求的文档链进度（spec/plan 按需，缺了不算错）
    requirements = [
        {
            "slug": slug,
            "intent": True,
            "spec": slug in active_specs,
            "plan": slug in active_plans,
            "stage": "plan"
            if slug in active_plans
            else "spec"
            if slug in active_specs
            else "intent",
        }
        for slug in sorted(active_intents)
    ]

    # 阶段 = 活跃需求文档链最靠后的环节
    stage = "none"
    if requirements:
        stage = max(requirements, key=lambda r: STAGE_ORDER[r["stage"]])["stage"]

    # 断链 = 顶层 spec/plan 的 slug 不在活跃 intent 里（孤儿文档 / 归档遗漏）
    broken: list[str] = []
    for slug in sorted(active_specs - active_intents):
        broken.append(f"spec/{slug}.md 存在，但无对应活跃需求 intent/{slug}.md（孤儿文档或归档遗漏）")
    for slug in sorted(active_plans - active_intents):
        broken.append(f"plan/{slug}.md 存在，但无对应活跃需求 intent/{slug}.md（孤儿文档或归档遗漏）")

    return {
        "stage": stage,
        "stage_label": STAGE_LABELS.get(stage, stage),
        "ok": not broken,
        "artifacts": artifacts,
        "requirements": requirements,
        "broken_links": broken,
    }


def to_markdown(result: dict) -> str:
    """把审计结果渲染成人读的进度表。"""
    lines = ["## 需求链路进度", "", "| 阶段 | 产物 | 状态 |", "|---|---|---|"]
    for a in result["artifacts"]:
        mark = "✅" if a["exists"] else "⬜"
        lines.append(f"| {a['label']} | `{a['path']}/` | {mark} |")
    if result["requirements"]:
        lines += ["", "**活跃需求**："]
        for r in result["requirements"]:
            chain = f"MRD {'✅' if r['intent'] else '⬜'} → PRD {'✅' if r['spec'] else '⬜'} → 方案 {'✅' if r['plan'] else '⬜'}"
            lines.append(f"- `{r['slug']}`：{chain}")
    lines += ["", f"**当前阶段**：{result['stage_label']}"]
    if result["broken_links"]:
        lines += ["", "**⚠️ 断链告警**（顶层 spec/plan 无对应活跃需求）："]
        lines += [f"- {b}" for b in result["broken_links"]]
    return "\n".join(lines) + "\n"


def main() -> int:
    ap = argparse.ArgumentParser(description="推导需求链路状态（确定性，无 AI 参与）")
    ap.add_argument("--root", type=Path, default=Path("."), help="仓库根目录（默认当前目录）")
    ap.add_argument("--format", choices=("json", "markdown"), default="json")
    args = ap.parse_args()

    # Windows 控制台默认 GBK，强制 UTF-8 输出，避免 emoji/中文打印崩溃（重定向不受影响）
    sys.stdout.reconfigure(encoding="utf-8")

    result = audit(args.root)
    if args.format == "markdown":
        print(to_markdown(result))
    else:
        print(json.dumps(result, ensure_ascii=False, indent=2))

    # 退出码供 CI 使用：断链 = 1，其余 0
    return 1 if result["broken_links"] else 0


if __name__ == "__main__":
    sys.exit(main())
