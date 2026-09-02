# [项目名] · SDLC 流程规则

> 这是 Qoder 的项目规则文件，每次会话自动读取。保持在一页内，细节放 `.qoder/rules/`。
> 本文件由 sdlc-template 骨架生成：**替换 [项目名] 与占位内容**，其余流程规则保持原样。
> 完整流程说明见 README.md（Gate 1→5 runbook）。

## Commands
- Test: `make test`（健康输出示例：`N passed in 0.42s`）
- Lint: `make lint`（健康输出示例：`All checks passed!`）
- Run: `make run`（按项目实际启动命令填）

## Conventions
- Python 3.11+，标准库优先，**不随意新增依赖**
- 计数与金额用 `int`，不用 `float`
- 每个对外函数都要有 docstring 和对应单元测试
- 错误用异常抛出，不返回 `None` 伪装成功
- **commit message 必须引用 Issue（#数字）**——本地 commit-msg hook 强制，云端 check-commit-refs 兜底

## Architecture
- `src/`：领域逻辑（纯函数，不碰 I/O）
- `tests/`：pytest，与 `src/` 目录结构一一对应
- `intent/` `spec/` `plan/`：需求链路文档（Issue → MRD → PRD → 技术方案），完成即归档到各自 `archive/`
- `src/gen/`：生成目录，**禁止手改**

## Things AI gets wrong
- **不要为了让测试通过而修改 `tests/` 下的文件**——测试失败要改 `src/`；改已有测试文件前想清楚：新增覆盖还是放宽断言？（REVIEW.md 有判定标准）
- 不要擅自升级依赖版本
- 业务规则以 spec/plan 为准，不要自创

## Verifying your work
- Test: `make test`（必须全绿；绝不跳过或删除失败的测试）
- Lint: `make lint`（零告警）

Run both before reporting any task complete, and paste the output.
If a test fails, fix the code, not the test.
