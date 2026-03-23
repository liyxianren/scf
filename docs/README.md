# SCF 文档入口

更新时间：2026-03-23

这是仓库内的主文档入口。
开始接手项目前，先从这里进入，不要直接扫描整个仓库。

## 阅读顺序

1. `docs/versions/V1-status.md`
2. `docs/handoff/current-focus.md`
3. `docs/versions/V1.md`
4. `docs/architecture/current-system.md`

然后按任务类型继续：

- 当前 OA、auth、排课、反馈、chat 或 workflow 相关工作：
  - 先读 `skills/scf-platform-context/SKILL.md`
- V2 交付模型规划或实现：
  - 先读 `skills/scf-platform-context/SKILL.md`
  - 再读 `skills/scf-delivery-workflow/SKILL.md`
  - 再读 `docs/versions/V2.md`
- 长期平台化、外部产品化、未来集成方向：
  - 读 `docs/versions/V3.md`
- 文档治理、handoff、入口文件更新：
  - 先读 `skills/scf-docs-governance/SKILL.md`
  - 再读 `docs/governance/docs-governance.md`

## V1 / V2 / V3 协议

- `V1-status.md` 记录当前进度、风险和下一步。
- `current-focus.md` 记录当前接手焦点和活动工作流。
- `V1.md` 与 `current-system.md` 记录当前已实现或当前架构事实。
- `V2.md` 是下一阶段规划。
- `V3.md` 是更长期方向。

不要把 `V2` 或 `V3` 直接当作当前已上线能力，除非代码与测试已经证明存在。

## Repo Local Skills

仓库内的 source-controlled skills 位于：

- `skills/scf-platform-context/`
- `skills/scf-delivery-workflow/`
- `skills/scf-docs-governance/`

如果这些 skills 还没有安装到 `$CODEX_HOME/skills`，则需要先手动阅读对应的本地 `SKILL.md`。

## 真相源层级

- 运行事实：代码、模型、迁移、测试
- 版本事实：`docs/versions/*.md`
- 当前架构事实：`docs/architecture/current-system.md`
- 入口规则：`AGENTS.md`、`CLAUDE.md`、本文件
