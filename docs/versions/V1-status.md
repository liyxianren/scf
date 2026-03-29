# V1 当前进度与风险

更新时间：2026-03-29

## 当前状态表

| Area | State | What Exists | Evidence | Gap / Next |
| --- | --- | --- | --- | --- |
| V1 交付基站 | Done | `auth + enrollment + workflow + oa + feedback + chat` 主干已经打通，集成回归覆盖排课、工作流、OA、删除链路和学生动作中心 | `modules/auth/*`, `modules/oa/*`, `tests/integration/test_enrollment_flow.py`, `tests/integration/test_action_centers.py`, `tests/integration/test_oa_routes.py`, `tests/integration/test_deletion_flows.py` | 当前主任务不再是补基站，而是在这个基线上做 AI 增效与业务容灾 |
| Auth 与角色面板 | Done | Admin / Teacher / Student 登录、角色跳转、角色 API 已实现 | `modules/auth/routes.py`, `modules/auth/models.py` | 后续只需随着业务扩展补权限边界 |
| Enrollment 与 intake 基线 | Done | 报名创建、token intake、学生档案绑定、排课匹配、学生确认/拒绝已形成主流程 | `modules/auth/enrollment_routes.py`, `modules/auth/services.py`, `tests/integration/test_enrollment_flow.py` | 保持稳定，不再继续堆额外状态分支 |
| 学生优先排课 AI 基座 | In Progress | 文本时间解析、`sessions_per_week` 硬约束、`availability_intake / candidate_slot_pool / recommended_bundle / risk_assessment`、统一 `student_action_items`、全职/兼职老师分流规则已落地 | `modules/auth/availability_ai_services.py`, `modules/auth/services.py`, `modules/auth/routes.py`, `modules/auth/enrollment_routes.py`, `modules/auth/workflow_services.py`, `tests/integration/test_enrollment_flow.py`, `tests/integration/test_action_centers.py`, `tests/integration/test_auth_access.py` | 下一步是把 AI 输入提升为真正主入口、收敛前台 `scheduling_case` 对象、补老师候选池工作台、补真实图片上传/OCR，并让请假/补课复用同一套 parser/planner/risk engine |
| Workflow todo 与业务容灾 | In Progress | 重排、补课、反馈待办闭环已存在；低风险直通学生、高风险回教务、孤儿待办清理、教务 `scheduling_risk_cases` 已落地 | `modules/auth/workflow_services.py`, `modules/auth/routes.py`, `modules/oa/routes.py`, `tests/integration/test_deletion_flows.py`, `tests/integration/test_enrollment_flow.py` | 仍需把更多异常流统一进风险台，并继续补空页面、失效对象、回退文案回归 |
| OA 课表与课后反馈 | Done | 课表 CRUD、反馈提交、请假/补课/反馈联动已可用 | `modules/oa/routes.py`, `modules/oa/models.py`, `tests/integration/test_oa_routes.py` | 下一步主要是和 AI 风险流、会议反馈流接轨 |
| Excel 导入链路 | In Progress | 导入记录、语义解析、冲突检测、绑定待办已实现 | `modules/oa/services.py`, `modules/oa/models.py`, `tests/integration/test_oa_p1_regressions.py` | 仍需持续验证导入重放、冲突保留、绑定状态一致性 |
| 内部聊天协作 | Done | 会话列表、未读数、消息收发、排课反馈回流已存在 | `modules/auth/chat_routes.py`, `tests/integration/test_enrollment_flow.py` | 后续可考虑和 AI 风险说明、下一步提醒联动 |
| Education 模块 | Done | Lessons / Exercises / Playground / Python+C 执行器已存在 | `modules/education/`, `app.py` | 非当前主重心，维持即可 |
| Agents 与 Handbook | Done | 创意生成、计划书、工程手册生成与导出已存在 | `modules/agents/`, `modules/handbook/` | 后续可作为交付输出物能力继续复用 |
| 文档治理底座 | Done | `docs/`、repo-local skills、入口型 `AGENTS.md/CLAUDE.md` 已落地 | `docs/`, `skills/`, `AGENTS.md`, `CLAUDE.md` | 需要随着 AI / 容灾主线持续回写，避免再次过期 |
| 项目交付管理 | Planned | 已完成需求梳理和版本定位，V2 目标仍存在 | `docs/versions/V2.md` | 目前优先级低于 V1 的 AI / 容灾增强，尚未建模 `ProjectTrack / SubProject / Milestone / Risk Board` |
| 项目交付风险可见性 | Risk | 当前已具备排课风险视图，但还没有完整交付节点、交付物和里程碑层面的系统预警 | `docs/versions/V2.md`, `docs/architecture/current-system.md` | 等当前 V1 AI / 容灾主线稳定后，再进入更完整的交付风险板实现 |

## 当前风险

- 当前 AI 仍以文本解析和结构化落库为主，真正的图片上传/OCR、多模态识别还没有进入已完成态。
- 当前产品层仍存在 `enrollment / workflow / risk case / action item` 多对象并行，角色端对同一排课事的语义还没完全统一。
- 当前“容灾”主要是业务流程层兜底，还不是基础设施级灾备或高可用能力。
- 老师端还没有完全切成 AI-native 工作台，当前更多是后端约束和摘要提示先到位。
- 请假、补课、重排虽然已经接入 workflow，但还没有完全复用同一套 AI parser / planner / risk engine。
- `Enrollment` 仍然是服务确认对象，不是完整的项目交付对象。

## 建议的下一步

1. 先把学生 AI 时间输入改成真正主入口，而不是先 parse 再回填表单。
2. 收敛前台排课对象，避免 `enrollment / workflow / risk case / action item` 多套语义并行。
3. 给老师端补齐候选池与周配额约束的工作台，并区分“兼职提案”和“全职异常确认”。
4. 把请假、补课、重排统一复用同一套时间解析、候选池和风险分流。
5. 继续补业务容灾回归：
   - 失效对象
   - 删除链路
   - 空页面
   - 回退文案
   - 低置信度人工校正
6. 在这条主线稳定后，再回到 V2 的外部集成和项目交付对象建模。
