# 当前系统结构

更新时间：2026-03-21

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
| `auth` | 用户、角色、报名、学生 intake、聊天、工作流入口 | `User`, `StudentProfile`, `Enrollment`, `LeaveRequest`, `ChatMessage` | `modules/auth/` |
| `oa` | 排课、待办、反馈、Excel 导入、内部 AI 工具 | `CourseSchedule`, `CourseFeedback`, `OATodo`, `ScheduleImportRun`, `PainPoint` | `modules/oa/` |
| `education` | 编程学习与代码执行 | `Lesson`, `Exercise`, `Submission`, `CodeExecutor`, `CExecutor` | `modules/education/` |
| `agents` | 创意项目生成与计划书生成 | `Agent`, `CreativeProject`, `ProjectPlan` | `modules/agents/` |
| `handbook` | 工程手册生成与导出 | `EngineeringHandbook`, `HandbookAgent`, `HandbookExporter` | `modules/handbook/` |

## 当前主执行链

当前系统最成熟的执行链是：

1. 创建 `Enrollment`
2. 学生提交 intake
3. 老师维护 availability
4. Admin 匹配与确认排课方案
5. 学生确认或拒绝
6. 课次进入正式执行
7. 请假 / 补课 / 反馈通过 workflow todo 流转

## 当前架构事实

- 应用入口在 `app.py`，以 Flask application factory 组装所有蓝图。
- 运行期主事实仍来自数据库模型与业务服务，不来自文档或外部系统。
- 集成测试已经存在，且覆盖了 auth、enrollment、OA 和回归流程。

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

这也是为什么 V2 会聚焦在：

- `ProjectTrack`
- `SubProject`
- `Milestone`
- `Risk Board`

## 当前优先级判断

- 优先维护内部交付效率，而不是先做对外 SaaS 化包装。
- 优先完善调度、反馈、协作与项目交付可视化，而不是扩散无关功能面。
