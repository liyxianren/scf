# 排课 AI Phase 1 工程任务单

更新时间：2026-03-29

## 目标

- 把 `docs/handoff/scheduling-ai-backlog.md` 的 `Phase 1` 压到可直接施工的工程任务级。
- 当前只覆盖排课主链路，不扩到请假、补课、短信、腾讯会议。
- 当前目标不是美化页面，而是先把：
  - 产品对象
  - 角色动作
  - 风险分流
  - 测试闭环
  稳定下来。

## Phase 1 范围

- `R1. scheduling_case 生命周期`
- `R2. 4 类分流规则`
- `R3. 全职模板外规则`
- `S1. AI 时间输入主入口`
- `S2. 低置信度澄清回合`
- `T2. 全职异常确认任务`
- `A1. 排课协同台`
- `AI2. needs_student_clarification`

## 约束

- 继续复用当前网站业务层和数据库真相源。
- 不新建旁路 AI 状态库。
- 当前兼容期内，底层仍可以保留 `Enrollment`、workflow todo、risk case。
- 但产品层和接口层开始向统一 `scheduling_case` 收敛。

## 一、接口改动清单

### 1. `scheduling_case` 聚合接口

- 新增：
  - `GET /auth/api/scheduling-cases`
  - `GET /auth/api/scheduling-cases/<id>`
  - `POST /auth/api/scheduling-cases/<id>/actions/<action>`
- 目标：
  - 对学生、老师、教务都返回统一 case 视图
  - 不再让前端自己拼 `enrollment + workflow + risk case`
- 返回结构建议：
  - `id`
  - `case_type`
  - `status`
  - `status_label`
  - `current_blocker`
  - `next_actor`
  - `next_step`
  - `entity_refs`
  - `student_view`
  - `teacher_view`
  - `admin_view`
  - `risk_assessment`
  - `recommended_bundle`
  - `candidate_slot_pool`

### 2. 学生 intake 主入口接口

- 当前挂点：
  - [enrollment_routes.py](C:/Users/Administrator/Desktop/scf-main/modules/auth/enrollment_routes.py)
  - 现有：
    - `POST /auth/intake/<token>/availability-parse`
    - `POST /auth/api/enrollments/<id>/availability-parse`
    - `POST /auth/intake/<token>`
    - `PUT /auth/api/enrollments/<id>/intake`
- Phase 1 改造方向：
  - 保留 parse preview 能力
  - 但新增统一提交结构：
    - `availability_evidence_items[]`
    - `confirmed_parse_result`
    - `manual_adjustments`
- 目标：
  - 学生提交一次即可完成“表达 -> parse -> 确认 -> 保存”
  - 结构化时间格改成 fallback，不再是默认主表单字段

### 3. 风险分流接口

- 当前挂点：
  - [services.py](C:/Users/Administrator/Desktop/scf-main/modules/auth/services.py)
  - [workflow_services.py](C:/Users/Administrator/Desktop/scf-main/modules/auth/workflow_services.py)
- 需要新增或稳定：
  - `recommended_action == needs_student_clarification`
  - `recommended_action == needs_teacher_confirmation`
  - `recommended_action == needs_admin_intervention`
  - `recommended_action == direct_to_student`
- 要求：
  - 风险分流必须能直接映射到 `scheduling_case.case_type`

### 4. 老师动作接口

- 当前挂点：
  - [routes.py](C:/Users/Administrator/Desktop/scf-main/modules/auth/routes.py)
  - [workflow_services.py](C:/Users/Administrator/Desktop/scf-main/modules/auth/workflow_services.py)
- 目标：
  - 兼职老师继续保留提案入口
  - 全职老师新增“异常时段确认”动作入口
- 新动作语义建议：
  - `confirm_exception_slots`
  - `decline_exception_case`
  - `submit_part_time_plan`

### 5. 教务协同接口

- 当前挂点：
  - `GET /auth/api/admin/action-center`
  - [routes.py](C:/Users/Administrator/Desktop/scf-main/modules/auth/routes.py)
- Phase 1 目标：
  - 新增统一 `scheduling_cases`
  - 当前 `pending_schedule_enrollments + pending_admin_send_workflows + scheduling_risk_cases` 在接口层先聚合，不再由前端分别理解

## 二、页面改动清单

### 1. 学生 intake 页面

- 当前文件：
  - [intake_form.html](C:/Users/Administrator/Desktop/scf-main/modules/auth/templates/auth/intake_form.html)
- 要改的点：
  - 把 AI 输入区提升为默认主入口
  - 结构化时间格折叠进“展开手动修改”
  - 若当前没有真图片上传/OCR，就把“截图可直接处理”文案改诚实
  - 新增低置信度确认步骤
- 完成标准：
  - 学生不再需要先理解时间格才能提交

### 2. 学生首页

- 当前文件：
  - [student_dashboard.html](C:/Users/Administrator/Desktop/scf-main/modules/auth/templates/auth/student_dashboard.html)
- 要改的点：
  - 不再同时以“我的课程 + 案件跟踪”承载排课动作
  - 首页改成单一任务中心
  - 所有排课相关动作都从 `scheduling_case` 渲染
- 完成标准：
  - 学生首页只能看到“现在要你做什么”和“处理中事项”

### 3. 老师面板

- 当前文件：
  - [teacher_dashboard.html](C:/Users/Administrator/Desktop/scf-main/modules/auth/templates/auth/teacher_dashboard.html)
- 要改的点：
  - 把当前“待我提案”拆成：
    - 兼职老师提案
    - 全职异常确认
  - 全职老师模板内正常情况不出现常规待办
  - 全职模板外 case 要有明确文案，不再和普通提案混在一起
- 完成标准：
  - 全职老师能一眼知道“这次为什么需要我介入”

### 4. 教务首页

- 当前文件：
  - [admin_dashboard.html](C:/Users/Administrator/Desktop/scf-main/modules/auth/templates/auth/admin_dashboard.html)
  - [enrollments.html](C:/Users/Administrator/Desktop/scf-main/modules/auth/templates/auth/enrollments.html)
- 要改的点：
  - 在不整站重写的前提下，先加一个 `排课协同台`
  - 聚合展示：
    - 当前 blocker
    - next actor
    - next action
    - risk summary
- 完成标准：
  - 教务处理排课不再需要在三块列表里自己找同一件事

## 三、状态机改动清单

### 1. 产品层新增 `scheduling_case`

- 说明：
  - 这不是要求立刻新建数据库表
  - Phase 1 可先做服务层聚合对象
- 必须固化的 case 类型：
  - `direct_pass_case`
  - `teacher_exception_case`
  - `student_clarification_case`
  - `admin_risk_case`

### 2. `recommended_action` 与 case 的映射

- `direct_to_student`
  - 对应：`direct_pass_case`
- `needs_teacher_confirmation`
  - 对应：`teacher_exception_case`
- `needs_student_clarification`
  - 对应：`student_clarification_case`
- `needs_admin_intervention`
  - 对应：`admin_risk_case`

### 3. 全职老师规则固化

- 当前规则必须写死到状态机，不再只停留在文档：
  - 模板内且满足周配额：
    - 不需要老师确认
  - 模板外 / 休息日 / 工作时间外：
    - 进入老师异常确认
  - 老师确认后仍无法满足周配额或完成日期：
    - 进入教务风险兜底

### 4. 学生澄清分支

- 新增分支：
  - 当 AI 解析低置信度或时间表达不完整时
  - 不直接回教务
  - 优先生成学生澄清 case

## 四、测试清单

### 1. 接口测试

- 新增 `scheduling_case` 聚合接口测试
- 验证 4 类 case 返回结构一致
- 验证学生、老师、教务看到的是同一 case，不是三套对象拼接结果

### 2. 学生链路测试

- 学生只提交文本，也能完成 parse + confirm + save
- 低置信度时进入学生澄清，而不是直接教务风险
- 没有真图片上传时，页面文案不再透支能力

### 3. 老师链路测试

- 全职老师模板内正常排课，不生成老师待办
- 全职老师模板外 case，生成异常确认任务
- 兼职老师仍需选满 `sessions_per_week`

### 4. 教务链路测试

- 教务 action center 能看到统一排课协同项
- 低风险 case 可一键复核
- 老师异常确认失败后能回到教务风险 case

### 5. 回归测试

- 不破坏当前：
  - 学生确认 / 拒绝
  - workflow todo
  - 删除链路容灾
  - OA 路由回归

## 五、建议施工顺序

1. 先在服务层引入 `scheduling_case` 聚合对象和 case 类型映射。
2. 再补 `needs_student_clarification`，把分流规则补齐。
3. 改学生 intake 主入口和学生任务中心渲染逻辑。
4. 改老师端，把全职异常确认从普通提案里拆出来。
5. 最后改教务协同台和相关接口聚合。

## 六、建议改动文件

### 优先改

- [services.py](C:/Users/Administrator/Desktop/scf-main/modules/auth/services.py)
- [workflow_services.py](C:/Users/Administrator/Desktop/scf-main/modules/auth/workflow_services.py)
- [enrollment_routes.py](C:/Users/Administrator/Desktop/scf-main/modules/auth/enrollment_routes.py)
- [routes.py](C:/Users/Administrator/Desktop/scf-main/modules/auth/routes.py)
- [intake_form.html](C:/Users/Administrator/Desktop/scf-main/modules/auth/templates/auth/intake_form.html)
- [student_dashboard.html](C:/Users/Administrator/Desktop/scf-main/modules/auth/templates/auth/student_dashboard.html)
- [teacher_dashboard.html](C:/Users/Administrator/Desktop/scf-main/modules/auth/templates/auth/teacher_dashboard.html)
- [admin_dashboard.html](C:/Users/Administrator/Desktop/scf-main/modules/auth/templates/auth/admin_dashboard.html)

### 同步补测试

- [test_enrollment_flow.py](C:/Users/Administrator/Desktop/scf-main/tests/integration/test_enrollment_flow.py)
- [test_auth_access.py](C:/Users/Administrator/Desktop/scf-main/tests/integration/test_auth_access.py)
- [test_oa_routes.py](C:/Users/Administrator/Desktop/scf-main/tests/integration/test_oa_routes.py)
- [test_oa_p1_regressions.py](C:/Users/Administrator/Desktop/scf-main/tests/integration/test_oa_p1_regressions.py)
