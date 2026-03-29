# 排课 AI PM 审查

更新时间：2026-03-29

## 审查范围

- 当前范围只覆盖排课主链路：
  - `报名 intake -> 学生表达可上课时间 -> AI 解析/推荐 -> 老师/教务确认 -> 学生确认`
- 当前审查目标不是判断代码能否运行，而是判断：
  - 这条链路是否已经是“学生优先的 AI 执行层”
  - 角色责任边界是否清楚
  - 前台对象和页面语义是否顺

## 审查依据

- `modules/auth/availability_ai_services.py`
- `modules/auth/enrollment_routes.py`
- `modules/auth/routes.py`
- `modules/auth/services.py`
- `modules/auth/workflow_services.py`
- `modules/auth/templates/auth/intake_form.html`
- `modules/auth/templates/auth/student_dashboard.html`
- `modules/auth/templates/auth/teacher_dashboard.html`
- `modules/auth/templates/auth/admin_dashboard.html`
- `modules/auth/templates/auth/enrollments.html`

## 结论摘要

- 当前方向是对的，但产品状态仍然是“AI 新链路 + 老 OA 流程壳”的混合态。
- 现在最大的落差不在模型能力，而在：
  - AI 还不是学生主入口
  - 前台对象仍然过多
  - 老师和教务的动作层还不够 AI-native
- 当前最需要的不是继续堆新对象，而是先把同一件排课事收敛成统一 case，再把学生、老师、教务三端动作改成真正任务导向。

## 正式审查表

| 问题 | 影响角色 | 现状证据 | 建议改法 | 优先级 |
| --- | --- | --- | --- | --- |
| AI 还不是学生主入口，更像解析器插件 | 学生 | `intake_form.html` 仍要求“解析时间”后再把结果填回兜底表单；结构化时间仍是主提交流程的一部分 | 学生端改成“提交这些时间”一次完成，系统自动解析并自动落到结构化结果；时间格只作为展开修改 | P0 |
| “支持截图”在产品表达上透支 | 学生 | `intake_form.html` 的文案像真图片处理，但当前入口更接近文本粘贴辅助；`enrollment_routes.py` 也还是 parse preview 形态 | 要么尽快补真实图片上传/OCR，要么立刻改文案，不再暗示已具备完整多模态闭环 | P0 |
| 学生动作被拆成多块，不像任务中心 | 学生 | `student_dashboard.html` 里“我的课程”“待确认与进行中的安排”“打开案件跟踪”同时承载同一件事 | 学生首页收敛成单一“现在要你做什么”区，不再让对象分栏承载动作 | P0 |
| 前台对象过多，同一排课事在不同角色端像不同事情 | 学生 / 老师 / 教务 | 当前产品层同时存在 `enrollment`、`workflow todo`、`scheduling_risk_cases`、`action_items` | 在产品层新增统一 `scheduling_case`，学生、老师、教务都围绕同一 case 看状态、卡点和下一步 | P0 |
| 老师端候选池还是提示，不是工作台 | 老师 | `teacher_dashboard.html` 里候选池主要以文本摘要存在，老师仍需手工填 proposal 行 | 把候选池改成可点选对象，并显示 `quota_required / quota_selected / risk_assessment` 的工作台式交互 | P0 |
| 缺少 `needs_student_clarification` 这一类 case | 学生 / 教务 | 当前风险更多落在 `needs_admin_intervention / needs_admin_review / needs_teacher_confirmation` | 增加“学生补充澄清”分支，把“时间没说清”从“教务风险”中拆出来 | P1 |
| 全职老师模板外时段的语义还不够产品化 | 老师 / 教务 | 当前底层复用 `enrollment_replan` 流程，容易让人误解为学生退回后的二次流程 | 把这类情况明确命名成“异常排课确认”或“模板外时段确认”，不要再沿用“重排”语义 | P1 |
| 教务仍然容易在多页面、多语义里手工判断 | 教务 | `admin_dashboard.html` 还同时承载待排课报名、workflow、风险 case | 教务首页收敛成“排课协同台”，每条只展示：为什么到这里、当前卡点、下一责任人、下一动作 | P1 |
| 成功页仍把内部交付风险甩给学生 | 学生 | `intake_form.html` 仍提示学生截图保存账号密码 | 改成首登设置密码，或至少提供稳定的后续查看 / 重置路径 | P1 |
| 低置信度 parse 还没有形成连续对话式澄清 | 学生 | `services.py` 已有低置信度判断，但学生侧主要还是一次 parse 结果展示 | 增加“我理解的是这些时间，你确认吗”的确认式交互，不再只丢结果框 | P1 |
| 全职老师异常确认和兼职老师常规提案还共用一套文案 | 老师 | `teacher_dashboard.html` 仍以“待我提案 / 提交排课建议”为主文案 | 老师端拆成两类任务：`自动接单结果通知` 与 `异常时段确认` | P1 |
| 周配额是硬约束，但例外周的治理规则仍不清楚 | 老师 / 教务 | 当前系统强调 `sessions_per_week`，但没有明确“本周排不满能否用后续周补齐”的产品规则 | 在 PRD 中补齐“硬约束 / 可补偿约束 / 冲刺交付例外”的规则表 | P2 |

## PRD 收敛方向

### 1. 产品对象收敛

- 前台只保留一个统一对象：`scheduling_case`
- 底层可以继续保留 `Enrollment`、workflow、risk case
- 但页面和接口不再把多套对象直接暴露给角色端

### 2. case 类型固定为 4 类

- `AI 低风险直通`
- `老师例外确认`
- `学生补充澄清`
- `教务风险兜底`

### 3. 学生端重写成“表达意图”

- 默认入口：
  - 文本
  - 图片
  - 结构化 fallback
- 默认行为：
  - 学生提交
  - AI 自动解析
  - 学生确认解析结果
  - 系统继续推进

### 4. 老师端按职责拆工作台

- 兼职老师：
  - 在候选池内选满
  - 必须满足 `sessions_per_week`
- 全职老师：
  - 模板内正常情况不进待办
  - 只有模板外、休息日、工作时间外才进入“异常时段确认”

### 5. 教务端改成排课协同台

- 每条 case 只展示：
  - 为什么到这里
  - 当前卡点
  - 下一责任人
  - 下一动作
- 不再把同一件事拆成报名列表、流程列表、风险列表三处找

## 上线前建议顺序

1. 先把学生 AI 输入改成真正主入口，并修正文案透支问题。
2. 把前台对象收敛成 `scheduling_case`，至少先在学生端和教务端完成统一。
3. 把老师端改成候选池工作台，并拆清“兼职提案 / 全职异常确认”。
4. 补 `needs_student_clarification` 分支，避免学生不清晰输入都回到教务。
5. 再推进真实图片上传/OCR 和更完整的多模态闭环。
