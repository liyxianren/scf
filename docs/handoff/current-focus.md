# 当前接手焦点

更新时间：2026-03-29
最近一次工作区校验：`git status --short` on 2026-03-29

## 当前真实情况

- 当前仓库已经具备 `auth + enrollment + workflow + oa + feedback + chat` 的 V1 交付基站。
- 网站端继续是当前业务信息和流程状态的母端口，后续 AI 与外部通道都应复用网站业务层与数据库真相源。
- 当前真正的第一优先级，已经从“继续补基站”切换成“在既有基站上做学生优先的 AI 增效和业务容灾”。
- `短信提醒 / 销售前端接入 / 腾讯会议课后反馈` 这些 V2 方向仍然保留，但短期不再压过当前这条 V1 强化主线。

## 当前工作流重点

### 1. V1 基站已完成，不再把主精力放在补齐基础模块

- 当前已经打通的主链路是：
  - Enrollment 创建
  - 学生 intake
  - 老师 availability
  - Admin 匹配/确认
  - 学生确认/拒绝
  - workflow todo 流转
  - 课后反馈与 OA 执行
- 当前回归覆盖的重点也已经形成：
  - `tests/integration/test_enrollment_flow.py`
  - `tests/integration/test_action_centers.py`
  - `tests/integration/test_oa_routes.py`
  - `tests/integration/test_oa_p1_regressions.py`
  - `tests/integration/test_auth_access.py`
  - `tests/integration/test_deletion_flows.py`

### 2. 当前第一主线：学生优先排课 AI

- 当前已落地的基座包括：
  - `availability_intake` 文本时间解析
  - `candidate_slot_pool`
  - `recommended_bundle`
  - `risk_assessment`
  - `sessions_per_week` 硬约束
  - `student_action_items` 统一学生动作协议
- 这一轮 PM 审查已经形成正式文档：
  - `docs/handoff/scheduling-ai-pm-audit.md`
  - `docs/handoff/scheduling-ai-backlog.md`
  - `docs/handoff/scheduling-ai-phase1-engineering.md`
- 当前审查结论已经比较明确：
  - AI 还不是学生主入口，更像 parser + planner 基座
  - 前台仍然存在 `enrollment / workflow / risk case / action item` 多对象割裂
  - 老师和教务的动作层还不够 AI-native，尤其老师候选池仍偏摘要提示
- 这条主线当前要继续推进的内容是：
  - 把学生 AI 时间输入改成真正主入口，而不是先解析再回填表单
  - 把前台对象收敛成统一 `scheduling_case`
  - 给老师端补成真正的候选池工作台，并拆开“兼职提案 / 全职异常确认”
  - 真正的图片上传/OCR、多模态时间识别
  - 请假 / 补课 / 重排复用同一套 parser / planner / risk engine
- 当前不要回退到以手工表格为中心的学生时间采集方式。

### 3. 当前第二主线：业务容灾与异常兜底

- 当前“容灾”优先指业务流程层，而不是基础设施层。
- 当前已落地的兜底包括：
  - 孤儿待办和失效流程对象自动收口
  - 高风险排课回教务处理
  - 低风险方案直通学生确认
  - 学生端统一动作入口，减少双对象模型导致的空页面和死链
- 下一步应继续覆盖：
  - 删除链路
  - 目标对象失效
  - 低置信度 AI 解析回退
  - 文案兜底
  - 无动作页面

### 4. 当前第三主线：学生 OA 最终从流程中心切到任务中心

- 当前这轮已经把学生首页从“案件/流程中心”开始改成“任务中心”。
- 但这条线还没有结束，后续还需要继续完成：
  - 统一首页 IA
  - 统一学生确认/退回协议
  - 统一“下一步动作”文案
  - 把请假/补课输入也收敛成学生表达意图，而不是让学生手工建模
- 可参考的专项审查文档：
  - `docs/handoff/student-oa-student-first-audit.md`

### 5. V2 外部集成主线暂时后移，但不删除

- 下列方向仍然有效：
  - 短信提醒
  - 销售前端接入
  - 腾讯会议接入课后反馈
  - OpenClaw / Feishu
- 但当前更合理的执行顺序是：
  1. 先把 V1 的 AI 排课和业务容灾主线稳定下来
  2. 再恢复这些外部集成主线

## 推荐的下一步

1. 先按 `docs/handoff/scheduling-ai-phase1-engineering.md` 推 Phase 1，优先定义统一 `scheduling_case`。
2. 把学生 AI 输入改成真正主入口，并去掉“截图能力”上的文案透支。
3. 补老师端候选池工作台，明确区分“兼职提案”和“全职异常时段确认”。
4. 把请假、补课、重排统一到同一套 AI 时间理解与风险分流框架。
5. 继续补异常回归，优先覆盖：
   - 删除后残留待办
   - 失效对象空页面
   - 低置信度解析
   - 死链和无动作页面
6. 当前这条主线稳定后，再恢复 V2 外部集成的并行推进。

## 当前阻塞与开放点

- 真正的图片上传/OCR、多模态解析还没有进入已完成态。
- 产品层仍存在 `enrollment / workflow / risk case / action item` 多对象并行，角色端语义还没完全统一。
- `function calling + LLM` 的模型供应商、置信度阈值、审计边界和人工校正 UI 还没有最终锁死。
- 老师候选池选课的前端交互还没有正式成型，全职异常确认和兼职提案也还没完全分开。
- 请假/补课对 AI 时间解析的复用还没有完全落地。
- 当前“容灾”仍主要覆盖业务对象失效和风险回退，不是基础设施级 DR。
- V2 的短信、销售前端、腾讯会议主线仍然存在，但当前不是第一优先级。

## 接手规则

- 新 agent 接手时，先读 `docs/README.md`。
- 继续当前主线时，先读本文件，再读 `docs/versions/V1.md` 与 `docs/versions/V1-status.md`。
- 如果开始恢复 V2 外部集成，再去看 `docs/versions/V2.md`。
- 做完较大任务后，回写本文件，而不是把状态塞回 `AGENTS.md`。
