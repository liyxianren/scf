# 当前接手焦点

更新时间：2026-03-21
最近一次工作区校验：`git status --short` on 2026-03-21

## 当前真实情况

- 当前仓库已经具备 `auth + enrollment + workflow + oa + feedback + chat` 的内部交付闭环雏形。
- 项目交付管理仍未建模，这是下一阶段的产品主任务。
- 本次任务新增了 `docs/` 文档体系、repo-local skills，以及入口型 `AGENTS.md / CLAUDE.md`。

## 当前工作流重点

### 1. Docs 治理底座已建立

- 已创建版本文档、状态文档、架构文档、handoff 文档、治理规则和模板。
- 已把 `AGENTS.md / CLAUDE.md` 改成入口索引，而不是旧式的全量系统说明。

### 2. OA P1 仍在稳定化

当前工作区已有未提交的 OA / workflow 相关改动，涉及：

- `app.py`
- `modules/auth/models.py`
- `modules/auth/enrollment_routes.py`
- `modules/auth/routes.py`
- `modules/auth/services.py`
- `modules/auth/workflow_services.py`
- `modules/auth/templates/auth/admin_dashboard.html`
- `modules/auth/templates/auth/enrollment_detail.html`
- `modules/auth/templates/auth/student_dashboard.html`
- `modules/auth/templates/auth/teacher_dashboard.html`
- `modules/oa/models.py`
- `modules/oa/routes.py`
- `modules/oa/services.py`
- `tests/factories.py`
- `tests/integration/test_action_centers.py`
- `tests/integration/test_enrollment_flow.py`
- `tests/integration/test_oa_p1_regressions.py`

这些修改不是本次 docs 任务引入的，后续接手时不要误回滚。

当前这轮已经完成的 OA P1 收口重点：

- 三端 action center 已形成 `下一步动作` 聚合视图，老师、学生、教务不再只靠聊天或报名详情页推进流程。
- 请假驳回说明、补课偏好、补课确认回写、提案 warning 展示都已进入结构化 payload 和页面。
- 学生确认中心已能预览 workflow 方案；学生首页已展示完整老师反馈。
- 最新一轮又补了：
  - `enrollment_replan` workflow 带出学生长期可上课时间 / 禁排日期摘要
  - 老师重排弹窗直接展示这些时间画像
  - 教务 `待教务发送` 卡片增加简版课次预览
  - 学生 `最近老师反馈` 卡片可直接打开报名详情

代码与测试事实：

- `pytest -q tests/integration` on 2026-03-21 -> `40 passed`

### 3. 下一个产品主线是 V2

V2 的目标已经固定为“项目交付管理”：

- `ProjectTrack`
- `SubProject`
- `Milestone`
- `Risk Board`

但这仍是当前默认方向，不是完整实施 spec。未锁死的实现决策见 `docs/versions/V2.md` 中的 `Open Decisions / Not Yet Locked`。

## 推荐的下一步

1. 把 `V2` 的对象模型和接口边界补到可实现级别。
2. 确定默认里程碑模板：
   - 纯技术
   - 技术 + 商业
   - 技术 + 商业 + 比赛
3. 决定风险预警优先落在什么界面：
   - OA dashboard
   - 专门的风险面板
   - 自动生成的待办列表
4. 在实现 V2 前，先确认如何把 `OATodo` 作为执行任务层复用，而不是直接替代项目模型。

## 当前阻塞与开放点

- V2 的产品方向已经稳定，但数据库模型、API 形态、页面入口仍未实现。
- 需要在实施前进一步锁定：
  - 项目主表与子项目表的关系
  - milestone 是否支持模板化批量生成
  - 风险面板默认按学生、项目还是负责人聚合

## 接手规则

- 新 agent 接手时，先读 `docs/README.md`。
- 在继续当前开发时，先看本文件，再看 `docs/versions/V2.md`。
- 在开始实现 V2 前，先确认 `docs/versions/V2.md` 和本文件仍然一致。
- 做完较大任务后，回写本文件，而不是把状态塞回 `AGENTS.md`。
