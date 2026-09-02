# sdlc-template · SDLC 流程骨架

一套**去业务化**的 SDLC 流程骨架，从 [SDLCDemo](https://github.com/wowojyc/SDLCDemo) 端到端演习（Issue #18 → v0.1.1）实证沉淀。
用 GitHub Template 机制复制到新项目后，按下方「落地清单」配置即可获得与 SDLCDemo 等价的工程门禁：

**需求链路**（Issue → intent/MRD → spec/PRD → plan → commit(#xx) → PR）→ **4 checks 门禁**（check-commit-refs / flow-audit / review / test）→ **AI 双审查**（本地 pre-push + 云端 pr-review，非阻塞）→ **维护闭环**（bands.yaml + maintenance-scan 三段式）→ **发版流水线**（vX.Y.Z tag → Release）。

---

## 落地清单（Use this template 之后）

新仓库复制完成后，按顺序做 5 件事：

### 1. 个性化
- [ ] `AGENTS.md`：替换 `[项目名]`，按项目语言/生态调整（Python 骨架默认）
- [ ] `Makefile`：`run` 目标填真实启动命令；非 Python 项目重写 test/lint 目标（ci.yml 依赖 `make test`/`make lint`）
- [ ] `.github/dependabot.yml`：非 Python 项目按生态改写（当前为 pip 版）
- [ ] `README.md`：替换本文档为自己的项目说明（本文档内容可保留到 docs/）

### 2. 启用本地 hooks（每台开发机一次）
```bash
git config core.hooksPath .githooks
```
- `commit-msg`：commit 必须引用 Issue（#数字）
- `pre-commit`：自动跑测试 + 拦截"同时改 src/ 与 tests/"的提交
- `pre-push`：本地 AI 审查（需装 qodercli/qoderclicn，未装时自动跳过不阻断）

### 3. 配云端 Secret / 变量（Settings → Secrets and variables → Actions）
| 名称 | 用途 | 必填 |
|---|---|---|
| `LLM_API_KEY` | 云端 AI 审查 + 维护诊断（硅基流动 key，OpenAI 兼容） | 需要云端审查时 |
| `LLM_BASE_URL` / `LLM_MODEL` | 可选覆盖（默认硅基流动 + DeepSeek-V3） | 可选 |

也可命令行：`gh secret set LLM_API_KEY`（引导输入，不回显）。

### 4. 配 main 分支保护（Settings → Branches，或 API）
```bash
# 用 API 配置（等价于网页勾选：Require PR + 4 required checks）
gh api -X PUT repos/{owner}/{repo}/branches/main/protection \
  --input - <<'JSON'
{
  "required_status_checks": {
    "strict": true,
    "contexts": ["check-commit-refs", "flow-audit", "review", "test"]
  },
  "enforce_admins": true,
  "required_pull_request_reviews": null,
  "restrictions": null
}
JSON
```
> 注意：单人仓库**不要**勾选 "Require approvals"——PR 作者不能 approve 自己的 PR，单账号必死锁（SDLCDemo 实证教训）。AI review 的发现项仅供参考不阻塞合并（pr-review.yml 设计如此），防 AI 误报卡死。

### 5. 验收（关键！）
- [ ] 开第一个需求 Issue → 建 feature 分支 → 随便改一行 → commit（引用 #xx）→ push → 开 PR
- [ ] 确认 **4/4 checks 全绿**（test 至少 1 个用例 + 无断链）
- [ ] 手动触发一次 `maintenance-scan`（workflow_dispatch）确认能跑通分档（示例数据 → normal）
- [ ] 打 `git tag v0.1.0 && git push origin v0.1.0` 验证 Release 生成

---

## Gate 1→5 流程（每个需求的完整路径）

| Gate | 做什么 | 产物 | 检查 |
|---|---|---|---|
| 1 需求登记 | 开 Issue（用 issue forms）→ 写 `intent/<slug>.md`（六字段 MRD：意图/作者/状态/来源/问题/预期成果） | Issue + intent/ | 人工批准 MRD |
| 2 设计/计划 | 按需写 `spec/<slug>.md`（PRD）与 `plan/<slug>.md`（技术方案） | spec/ plan/ | 人工确认 |
| 3 写码 + 自验 | 先建分支（`git branch feat/xxx origin/main` + `git switch`）→ TDD（测试先行）→ `make test` + `make lint` | src/ tests/ | pre-commit + pre-push |
| 4 评审 | push 分支 → 开 PR（body 写 `Closes #xx`）→ 等 4 checks | PR | check-commit-refs / flow-audit / review / test |
| 5 合并 + 发版 | merge（自动关 Issue）→ 需求文档归档 `archive/` → tag 发版 | Release | release.yml 门禁 |

审计链自动追踪：`scripts/audit_artifacts.py` 每次 push/PR 推导产物链状态（断链即失败），进度表输出到 workflow Step Summary。

---

## 维护闭环（第 9 环，可选启用）

`bands.yaml`（层级声明） + `maintenance-scan.yml`（每日 UTC 19:00 三段式）+ `scripts/detect_drift.py`（确定性分档）：
- 1σ 内 → 记日志；越 2σ → AI 只读诊断；越 3σ → 自动开 Issue 走人工分诊
- 模板带示例数据可直接体验分档；接真实采集时注意：
  - **写回走独立数据分支**（如 `metrics-data`）——main 受分支保护，workflow 直推会被拒（`GH006`，SDLCDemo 实证）
  - 首次 push 新分支用完整 refname：`git push origin HEAD:refs/heads/metrics-data`（`HEAD:metrics-data` 报 not a full refname，实证教训）
  - 采集脚本零新增依赖、原子写、commit 引用 Issue 溯源

---

## 设计要点（为什么这么做）

1. **AI 审查非阻塞**：发现项仅供参考，人通过分支保护做最终决策——AI 误报（实证出现过 3 连误报）不卡合法 PR
2. **检测保持确定性**：分档/审计不用 AI 判断，脚本算（可复现、有单测）；AI 只在越界后做诊断
3. **双保险**：本地 hooks（commit-msg/pre-push）+ 云端兜底（check-commit-refs/flow-audit）——`--no-verify` 跳过本地也逃不过云端
4. **hooks 零依赖降级**：无 make 退 pytest、无 qodercli 跳过审查——环境缺件只降级不误伤
5. **review.md 防臆测**：审查必须基于 diff 逐行核对，需求目标不算缺陷，宁可漏报不可错报
