# Docs Governance

更新时间：2026-03-21

## 目的

这套规则用于确保：

- 产品路线图有稳定落点
- 当前进度有统一记录
- 新 agent 接手时不需要重新扫全仓库
- `AGENTS.md / CLAUDE.md` 不会再次膨胀成过时说明书

## Source Of Truth 层级

1. 运行事实：代码、模型、迁移、测试
2. 产品版本事实：`docs/versions/*.md`
3. 当前架构事实：`docs/architecture/current-system.md`
4. 当前接手焦点：`docs/handoff/current-focus.md`
5. 入口与协作规则：`AGENTS.md`、`CLAUDE.md`

## 更新规则

| 触发事件 | 必须更新的文档 |
| --- | --- |
| 新需求进入下一阶段规划 | `docs/versions/V2.md` 或 `docs/versions/V3.md` |
| 当前已做内容、风险、下一步发生变化 | `docs/versions/V1-status.md` |
| 已落地能力边界变化 | `docs/versions/V1.md` |
| 模块职责、核心对象、主流程变化 | `docs/architecture/current-system.md` |
| 一轮大任务结束、准备交接 | `docs/handoff/current-focus.md` |
| 当前工作流、dirty worktree、活跃分支状态变化 | `docs/handoff/current-focus.md` |
| 文档树结构、阅读顺序、主入口职责变化 | `docs/README.md` |
| 协作入口或技能规则变化 | `AGENTS.md`、`CLAUDE.md` |

## 版本文档怎么写

- `V1.md`
  - 只写当前已实现基线
  - 必须基于代码、测试、提交事实
- `V1-status.md`
  - 只用结构化状态表记录当前状态
  - 状态限定为：`Done / In Progress / Planned / Risk`
  - 证据必须来自 repo 内工件，不能引用聊天记录
- `V2.md`
  - 写下一阶段的明确目标、核心对象、默认边界
  - 未锁死的决策要显式写在文档中，不能只留在 handoff
- `V3.md`
  - 写远期方向，不提前锁死实现细节

## Freshness 规则

- 每个顶层事实文档都应有 `更新时间` 或等价 freshness 标记。
- `docs/handoff/current-focus.md` 应在工作区状态检查后写入最近一次校验信息。

## AGENTS / CLAUDE 怎么写

- 只保留：
  - 当前事实摘要
  - 文档入口顺序
  - 当前优先级
  - system map
  - source of truth
  - skill 使用规则
  - 验证命令
  - 文档维护规则
- 不把完整版本状态、详细架构、长篇路线图写回入口文件。

## Skills 规则

- 仓库内的 `skills/` 目录是 source-controlled skill 资产。
- 如果要让 Codex 自动触发 repo-local skill，需要把对应 skill 安装到 `$CODEX_HOME/skills`。
- 未安装时：
  - 文档仍然必须完整可用
  - 不能把关键知识只写进 repo skill 而不写进 `docs/`

## 文档变更的最小完成标准

一次非细碎任务结束前，至少检查：

1. `V1-status.md` 是否需要更新
2. `current-focus.md` 是否需要更新
3. 架构边界是否变化，若变化则更新 `current-system.md`
4. `docs/README.md` 的入口顺序是否仍准确
5. `AGENTS.md / CLAUDE.md` 是否仍与当前事实一致

## 不要这样做

- 不要把版本路线写进 `AGENTS.md`
- 不要把临时讨论记录当成正式状态文档
- 不要在没有代码/测试证据时把能力标记为已完成
- 不要让 repo-local skill 成为唯一知识入口
