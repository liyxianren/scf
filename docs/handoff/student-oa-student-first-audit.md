# 学生 OA 学生效率优先审查

更新时间：2026-03-25

## 审查目标

- 本轮不是继续从教务流程完整性出发，而是改成从学生动作完成效率出发。
- 判断标准不是“内部状态表达是否完整”，而是：
  - 学生能不能最快知道自己现在要做什么
  - 学生能不能用最自然的方式表达时间和限制
  - 学生做完动作后，下一步是否清晰
  - 是否把内部 workflow / 状态机 / 数据结构负担转嫁给了学生

## 当前默认原则

- 排课、补课、请假相关时间输入，应优先支持 `自然语言 / 图片 / 截图 / 多模态` -> `LLM + function calling` 解析 -> 学生确认 / 微调。
- 结构化时间表单、点时间格、手填禁排日期，应降级为 fallback，而不是默认主入口。
- 学生首页应按“待我完成的动作”组织，而不是按内部流程对象组织。
- 学生侧不应默认暴露 `workflow / tracking / revision / waiting_teacher_proposal` 这类内部语义。

## 当前已锁定问题

### P0. 时间输入默认要求学生手工结构化建模

- 学生当前需要先把真实生活里的安排翻译成“周几 + 起止时间”的网格，再额外维护禁排日期。
- 这要求学生先理解系统的数据结构，而不是直接表达“我什么时候能上课”。
- 建议把默认入口改成自然语言或多模态表达，例如“我周二周四晚上可以，下周五不行”或上传课表截图，再由系统解析为候选时段，学生只做确认和微调。
- 证据：
  - [modules/auth/templates/auth/intake_form.html](C:/Users/Administrator/Desktop/scf-main/modules/auth/templates/auth/intake_form.html)
  - 主输入文案是“点击或滑动选择每周可上课的时段”
  - 另有单独“不可上课的日期”选择区

### P0. 学生首页的信息架构仍以内部流程为中心

- 学生首页主标题是“我的课表”，但核心动作区却叫“案件跟踪中心”，并按“待我处理 / 流程跟踪”组织。
- 后端接口直接返回 `action_required_workflows / tracking_workflows / pending_workflows / pending_enrollments`，说明当前页面心智模型仍是内部工作流对象，而不是学生任务清单。
- 这会让学生先理解你们内部怎么分流程，再决定自己该点哪里，属于把内部协同结构直接外露给学生。
- 建议改成学生任务语言：
  - `现在需要你确认`
  - `你的下一节课`
  - `本次请假的处理进度`
  - `最近老师反馈`
- 建议进一步把学生端返回协议收敛成统一的 `student_action_item`，前端只关心：
  - `title`
  - `next_step`
  - `primary_action`
  - `secondary_action`
  - `detail_preview`
  - `status_label`
- 证据：
  - [modules/auth/templates/auth/student_dashboard.html](C:/Users/Administrator/Desktop/scf-main/modules/auth/templates/auth/student_dashboard.html)
  - [modules/auth/routes.py](C:/Users/Administrator/Desktop/scf-main/modules/auth/routes.py)

### P0. 请假时再次要求学生手工填写补课结构化偏好，认知负担过高

- 学生在申请请假时，不只要写请假原因，还要立刻补“这次补课临时时段、禁排日期、备注”。
- 这等于让学生在一个高频动作里再次做一次小型排课建模，而且和长期档案重复。
- 本质上是把“我要请一次假”设计成了“我要先自己完成一轮补课排程”。
- 建议改成分层收集：
  - 第一步只收 `请假原因 + 是否愿意补课`
  - 默认复用长期可上课时间
  - 只问“这次有没有额外限制”
  - 允许一句话补充，系统再解析成临时补课约束
- 证据：
  - [modules/auth/templates/auth/student_dashboard.html](C:/Users/Administrator/Desktop/scf-main/modules/auth/templates/auth/student_dashboard.html)
  - 请假 modal 内包含补课时段、禁排日期、补课备注三块临时结构化输入

### P1. 学生端仍暴露大量内部 workflow 术语和元数据

- 页面内直接展示或围绕 `workflow` 组织内容，还展示 `revision / 更新 / 等待开始 / 排课重排 / 请假补课 / 待教务处理` 等语义。
- 这类信息对内部协同有价值，但对学生来说多数不是可执行动作，只会增加理解成本。
- 学生真正关心的是“我现在要不要点、点完会怎样、最晚什么时候处理”，不是“当前处于哪条内部流程”。
- 建议把页面收敛成三类学生可理解信息：
  - 当前需要你做的动作
  - 不需要你做动作，但正在处理中
  - 结果和下一步预期
- 证据：
  - [modules/auth/templates/auth/student_dashboard.html](C:/Users/Administrator/Desktop/scf-main/modules/auth/templates/auth/student_dashboard.html)
  - 页面存在 `案件跟踪中心`、`流程跟踪`、`revision`、`workflowStatusLabel` 等实现

### P1. 学生确认 / 退回存在双入口，背后是迁移复杂度，不是学生产品设计

- 当前既有 `/api/enrollments/<id>/student-confirm|student-reject`，也有 `/api/workflow-todos/<id>/student-confirm|student-reject`。
- 前端还要先判断有没有 `workflowTodoMap` 再走哪条路，这说明产品表面还没完成“一个动作，一个入口”的收敛。
- 这会把“工作流待办不存在”这类内部错误直接暴露给学生，导致同一个动作在学生侧语义不稳定。
- 建议学生侧统一成单一动作入口，不让历史兼容路径继续主导学生交互模型。
- 证据：
  - [modules/auth/templates/auth/student_dashboard.html](C:/Users/Administrator/Desktop/scf-main/modules/auth/templates/auth/student_dashboard.html)
  - [modules/auth/enrollment_routes.py](C:/Users/Administrator/Desktop/scf-main/modules/auth/enrollment_routes.py)
  - [modules/auth/workflow_routes.py](C:/Users/Administrator/Desktop/scf-main/modules/auth/workflow_routes.py)

## 建议的学生端收敛方向

1. 首页只保留 3 到 4 个任务导向入口：
   - `待确认课程`
   - `我要改时间`
   - `请假与补课`
   - `进行中的申请`
2. 学生端接口统一成单一 `student_action_item` 协议，不再让前端拼接 `enrollment + workflow` 两套对象。
3. 学生确认 / 退回统一成单一业务动作入口，后台自行路由到底层对象。
4. 请假动作拆成一步完成，补课偏好后置且默认继承长期档案。
5. 时间表达默认支持文本优先，并预留截图 / 课表图片解析入口；网格和日期字段退为 fallback。

### P2. 成功页把账号交付风险转嫁给学生

- 学生提交信息后，被要求“截图保存账号密码，密码仅显示一次”。
- 这不是学生的主任务，却把账号交付和密码保管转成学生自己的人工操作。
- 建议改成短信/邮件/安全链接激活，至少提供“重新发送登录链接”而不是只给一次明文密码。
- 证据：
  - [modules/auth/templates/auth/intake_form.html](C:/Users/Administrator/Desktop/scf-main/modules/auth/templates/auth/intake_form.html)

## 上线前建议分层

### 必须在学生 OA 上线前处理

1. 把学生时间输入从“纯结构化默认入口”改成“自然表达优先，结构化兜底”。
2. 把学生首页从“流程中心”重写成“动作中心”。
3. 把请假动作里的补课偏好收集从强结构化改成复用长期档案 + 轻补充。
4. 学生确认 / 退回统一成单一动作入口，不再保留前端分支式判断。
5. 学生动作列表改成统一协议，避免继续把兼容期对象模型暴露到学生端。

### 可以紧随上线补强

1. 账号交付改成安全激活链路。
2. 线上课会议信息改成更学生化的表达，不把“待创建 / 会议号”这类中间态直接暴露为主要信息。
3. 把反馈、请假、排课进度统一成一套更生活化的状态文案。

## 下一步输出物

- 需要把以上问题进一步整理成：
  - `上线前必须改`
  - `上线后 1 周内补`
  - `适合做成 LLM / 多模态能力的入口`
- 下一轮应补两份直接可执行的产品产物：
  - 学生侧 IA 草图，明确首页和排课输入的学生任务流
  - `student_action_item` 返回协议草案，作为学生 OA 和底层 workflow / enrollment 的隔离层
