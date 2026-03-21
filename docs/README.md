# SCF Docs Index

更新时间：2026-03-21

这是仓库内的主文档入口。后续任何 agent 或开发者接手，都应先从这里开始，而不是直接扫描整个仓库。

## 阅读顺序

1. [V1 当前进度与风险](versions/V1-status.md)
2. [当前接手焦点](handoff/current-focus.md)
3. [V1 当前产品基线](versions/V1.md)
4. [V2 目标：项目交付管理](versions/V2.md)
5. [V3 目标：售前与全链路平台化](versions/V3.md)
6. [当前系统结构](architecture/current-system.md)
7. [文档治理规则](governance/docs-governance.md)

如果你是在继续当前开发，而不是单纯理解项目，请优先读完 `V1-status.md` 和 `current-focus.md`，再进入 `V2/V3`。

## 每份文档负责什么

| 文档 | 作用 | 什么时候更新 |
| --- | --- | --- |
| `versions/V1.md` | 记录当前已实现的产品基线 | 当前能力边界发生实质变化时 |
| `versions/V1-status.md` | 记录 Done / In Progress / Planned / Risk | 当前工作流、风险、下一步变化时 |
| `handoff/current-focus.md` | 记录当前正在推进什么、下一步从哪里接 | 当前工作流、dirty worktree、活跃分支状态变化时 |
| `versions/V2.md` | 记录下一阶段的产品目标与对象模型方向 | 新需求进入下一阶段规划时 |
| `versions/V3.md` | 记录更远期的平台化方向 | 路线图大方向变化时 |
| `architecture/current-system.md` | 记录当前真实系统分层与业务域 | 架构边界、模块职责变化时 |
| `governance/docs-governance.md` | 规定文档和入口文件如何维护 | 文档治理规则需要调整时 |

## 使用原则

- 代码、模型、测试、迁移是运行事实。
- `docs/versions/*.md` 是产品版本与路线图事实。
- `docs/architecture/current-system.md` 是当前架构事实。
- `AGENTS.md` 和 `CLAUDE.md` 只做入口索引与协作规则，不承载全部细节。

## Skills 说明

仓库内的 source-controlled skills 位于：

- `skills/scf-docs-governance/`
- `skills/scf-delivery-workflow/`

注意：

- 这些目录是仓库里的技能源码，不代表已经被 Codex 自动安装。
- 自动触发仍依赖把 skill 安装到 `$CODEX_HOME/skills`。
- 未安装时，`docs/` 仍然是唯一可靠入口。
