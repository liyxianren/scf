# V1 当前进度与风险

更新时间：2026-03-21

## 当前状态表

| Area | State | What Exists | Evidence | Gap / Next |
| --- | --- | --- | --- | --- |
| Auth 与角色面板 | Done | Admin / Teacher / Student 登录、角色跳转、角色 API 已实现 | `modules/auth/routes.py`, `modules/auth/models.py` | 后续只需随着业务扩展补权限边界 |
| Enrollment 与 intake | Done | 报名创建、token intake、学生档案绑定、排课匹配、学生确认/拒绝已形成主流程 | `modules/auth/enrollment_routes.py`, `modules/auth/services.py`, `tests/integration/test_enrollment_flow.py` | 下一层不是继续堆状态，而是补项目交付对象 |
| Workflow todo 闭环 | In Progress | 重排、补课、反馈待办已具备业务语义和角色动作；teacher/admin/student action center 已形成统一 `next_action` 聚合，补课偏好、驳回说明、proposal warning、反馈详情均已结构化进入页面 | `modules/auth/workflow_routes.py`, `modules/auth/workflow_services.py`, `modules/auth/routes.py`, `modules/auth/templates/auth/*.html`, `tests/integration/test_action_centers.py`, `tests/integration/test_enrollment_flow.py` | 已接近试运行状态，但仍需继续做浏览器层 smoke、老师提案前置引导和剩余边界回归 |
| OA 课表与课后反馈 | Done | 课表 CRUD、反馈提交、请假/补课/反馈联动已可用 | `modules/oa/routes.py`, `modules/oa/models.py`, `tests/integration/test_oa_routes.py` | 下一步是和项目交付节点形成联动，而不是只围绕课次 |
| Excel 导入链路 | In Progress | 导入记录、语义解析、冲突检测、绑定待办已实现 | `modules/oa/services.py`, `modules/oa/models.py`, 提交 `c7fdcd7`, `39d4602` | 仍需持续验证导入重放、冲突保留、绑定状态一致性 |
| 内部聊天协作 | Done | 会话列表、未读数、消息收发、排课反馈回流已存在 | `modules/auth/chat_routes.py`, `tests/integration/test_enrollment_flow.py` | 后续可考虑与项目节点提醒结合 |
| Education 模块 | Done | Lessons / Exercises / Playground / Python+C 执行器已存在 | `modules/education/`, `app.py` | 非当前主重心，维持即可 |
| Agents 与 Handbook | Done | 创意生成、计划书、工程手册生成与导出已存在 | `modules/agents/`, `modules/handbook/` | 后续可作为项目交付输出物能力接入 |
| 文档治理底座 | Done | `docs/`、repo-local skills、入口型 `AGENTS.md/CLAUDE.md` 已落地 | `docs/`, `skills/`, `AGENTS.md`, `CLAUDE.md` | 后续需要在真实迭代中持续维护，不要再次失效 |
| 项目交付管理 | Planned | 已完成需求梳理和版本定位，V2 目标已定义 | `docs/versions/V2.md` | 尚未建模 `ProjectTrack / SubProject / Milestone / Risk Board` |
| 项目交付风险可见性 | Risk | 当前仍主要依赖人脑和零散待办记忆交付节点 | `docs/versions/V2.md`, `docs/handoff/current-focus.md` | 这是下一阶段最核心缺口，需要尽快进入实现 |

## 当前风险

- `Enrollment` 目前承载的是确认服务与排课执行，不是项目交付生命周期。
- 没有显式的里程碑模型时，`Demo ready / 拍摄 / 比赛报名 / 结课材料输出` 仍无法被系统主动预警。
- OA P1 仍在稳定化阶段，当前工作区也存在未提交的相关修改，后续实现需要避免误回滚。

## 建议的下一步

1. 把 `V2` 中的项目交付对象模型细化到可实现级别。
2. 明确里程碑模板：
   - 纯技术项目
   - 技术 + 商业项目
   - 技术 + 商业 + 比赛项目
3. 明确风险面板的默认视图：
   - 未来 3 天
   - 未来 5 天
   - 未来 7 天
   - 已逾期
4. 在真实迭代里持续更新本表，而不是把进度写回 `AGENTS.md`。
