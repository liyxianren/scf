# 当前系统结构

更新时间：2026-03-26

## 当前真实定位

SCF Hub 当前真实形态是一个 Flask 单体应用，既包含对外教学和展示模块，也包含内部交付运营模块。

当前真正的产品中心已经从“编程学习网站”偏移到：

- `auth`
- `enrollment`
- `workflow`
- `oa`
- `feedback`
- `chat`

## 业务域地图

| 业务域 | 主要职责 | 关键对象 / 能力 | 主要路径 |
| --- | --- | --- | --- |
| `auth` | 用户、角色、报名、学生 intake、聊天、工作流入口 | `User`, `StudentProfile`, `Enrollment`, `LeaveRequest`, `ChatMessage`, `availability_intake` | `modules/auth/` |
| `oa` | 排课、待办、反馈、Excel 导入、内部 AI 工具 | `CourseSchedule`, `CourseFeedback`, `OATodo`, `ScheduleImportRun`, `PainPoint` | `modules/oa/` |
| `education` | 编程学习与代码执行 | `Lesson`, `Exercise`, `Submission`, `CodeExecutor`, `CExecutor` | `modules/education/` |
| `agents` | 创意项目生成与计划书生成 | `Agent`, `CreativeProject`, `ProjectPlan` | `modules/agents/` |
| `handbook` | 工程手册生成与导出 | `EngineeringHandbook`, `HandbookAgent`, `HandbookExporter` | `modules/handbook/` |

## 当前主执行链

当前系统最成熟的执行链已经演进为：

1. 创建 `Enrollment`
2. 教务设定排课约束：
   - `sessions_per_week`
   - `delivery_urgency`
   - `target_finish_date`
3. 学生通过 intake 表达可上课时间：
   - 结构化时段
   - 文本
   - 粘贴截图/聊天文本
4. 系统解析并落库：
   - `availability_intake`
   - `candidate_slot_pool`
   - `recommended_bundle`
   - `risk_assessment`
5. 低风险方案进入老师提案或直通学生确认，高风险方案回教务处理
6. 学生通过统一 action item 确认或退回
7. 正式课次进入执行
8. 请假 / 补课 / 反馈继续通过 workflow todo 流转

## 当前架构事实

- 应用入口在 `app.py`，以 Flask application factory 组装所有蓝图。
- 运行期主事实仍来自数据库模型与业务服务，不来自文档或外部系统。
- AI 排课状态没有单独的旁路真相源，而是继续落在网站数据库和既有 workflow payload 中。
- 当前学生端主交互已经开始从“对象中心”收敛到“动作中心”。
- 集成测试已经存在，且覆盖了 auth、enrollment、OA、action center、删除链路和回归流程。

主要证据：

- `app.py`
- `modules/auth/*`
- `modules/oa/*`
- `tests/integration/*`

## 当前系统缺口

系统当前 **没有** 独立的项目交付管理层。

这意味着：

- `Enrollment` 是服务确认对象，不是完整的项目交付对象。
- 课次和待办可以被管理，但 `Demo ready / 拍摄 / 比赛报名 / 结课交付` 这些节点还不是系统一等公民。
- 交付风险仍难以做成主动预警面板。

系统当前也 **没有** 完整的多模态时间理解和基础设施级容灾。

这意味着：

- 真正的图片上传/OCR、语音/视频时间解析还未完成。
- 当前“容灾”主要是业务流程层的风险回退、失效对象收口和人工兜底。
- 平台级灾备、高可用和基础设施切换不在当前已完成范围内。

## 当前优先级判断

- 优先维护内部交付效率，而不是先做对外 SaaS 化包装。
- 优先把学生优先的 AI 排课与业务容灾做稳，而不是同时扩散过多外部集成面。
- 优先复用现有网站业务层和数据模型，而不是为 AI 单独新建真相源。
