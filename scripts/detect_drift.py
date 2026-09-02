"""确定性漂移检测 —— bands.yaml 的"检测"环节。

关键设计（对应 06.1 原文）：
  **检测保持确定性** —— 不用 AI 判断有没有越界。
  均值/标准差/判异规则全部脚本算，结果可复现、可审计、有单测。

判异规则：Western Electric 简化版
  · 越出 1σ：正常波动（log）
  · 越出 2σ：需关注（diagnose）
  · 越出 3σ：显著异常（act）
  另加一条：连续 6 点单调上升/下降 → 视为慢漂移，至少升到 2σ 档。

用法:
    # 直接给历史值
    python scripts/detect_drift.py --metric ci_test_failure_rate \
        --value 0.18 --history '{"values":[0.02,0.03,0.02,0.04,0.03,0.02,0.03]}'

    # 从文件读历史
    python scripts/detect_drift.py --metric ci_test_failure_rate \
        --value 0.18 --history-file metrics/ci_test_failure_rate.json

输出（stdout，JSON）:
    {"metric": "...", "value": 0.18, "mean": 0.027, "std": 0.007,
     "sigma_level": 21.8, "tier": "3sigma", "action": "act", "reason": "..."}
"""

from __future__ import annotations

import argparse
import json
import sys
from itertools import pairwise
from pathlib import Path
from statistics import mean, pstdev


def detect(values: list[float], current: float) -> dict:
    """给定历史值与当前值，判定偏离档位。"""
    if len(values) < 2:
        return {
            "tier": "insufficient_data",
            "action": "log",
            "reason": f"历史样本不足（{len(values)} 个），至少需要 2 个",
        }

    m = mean(values)
    sd = pstdev(values)

    if sd == 0:
        # 历史完全无波动：任何偏离都值得看一眼
        level = 0.0 if abs(current - m) < 1e-12 else 3.0
    else:
        level = abs(current - m) / sd

    # 单调漂移检测：最近 6 点是否持续同向
    recent = values[-6:] + [current]
    drift = len(recent) >= 6 and (
        all(b > a for a, b in pairwise(recent))
        or all(b < a for a, b in pairwise(recent))
    )

    if level >= 3:
        tier, action = "3sigma", "act"
        reason = f"偏离 {level:.1f}σ，超出 3σ，显著异常"
    elif level >= 2:
        tier, action = "2sigma", "diagnose"
        reason = f"偏离 {level:.1f}σ，超出 2σ，需要关注"
    elif level >= 1:
        tier, action = "1sigma", "log"
        reason = f"偏离 {level:.1f}σ，超出 1σ，正常波动"
    else:
        tier, action = "normal", "log"
        reason = f"偏离 {level:.1f}σ，在 1σ 内，正常"

    if drift and tier in ("normal", "1sigma"):
        tier, action = "2sigma", "diagnose"
        reason += "；且最近 6 点单调漂移（慢漂移），升档到 2σ"

    return {
        "mean": round(m, 6),
        "std": round(sd, 6),
        "sigma_level": round(level, 2),
        "tier": tier,
        "action": action,
        "reason": reason,
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--metric", required=True)
    ap.add_argument("--value", required=True, type=float)
    ap.add_argument("--history", help="JSON 字符串，形如 {\"values\": [...]}")
    ap.add_argument("--history-file", help="JSON 文件路径，形如 {\"values\": [...]}")
    args = ap.parse_args()

    if args.history_file:
        data = json.loads(Path(args.history_file).read_text(encoding="utf-8"))
    elif args.history:
        data = json.loads(args.history)
    else:
        data = {"values": []}

    result = detect(list(data.get("values", [])), args.value)
    result = {"metric": args.metric, "value": args.value, **result}

    print(json.dumps(result, ensure_ascii=False, indent=2))

    # 退出码供 CI 使用：3σ = 2，2σ = 1，其余 0
    return {"3sigma": 2, "2sigma": 1}.get(result["tier"], 0)


if __name__ == "__main__":
    sys.exit(main())
