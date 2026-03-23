# 当前接手焦点

更新时间：2026-03-23
最近一次工作区校验：`git status --short` on 2026-03-23

## 当前真实情况

- 当前仓库已经具备 `auth + enrollment + workflow + oa + feedback + chat` 的内部交付闭环雏形。
- 网站端继续是当前业务信息的母端口，后续对内对外通道都应复用网站业务层与接口边界。
- 当前活跃主线已锁定为：`V2 Phase 1 = OpenClaw / Feishu 外化提醒与动作网关`。
- 第一阶段确定内部先行，不做学生外部入口。
- 外化不是把整站搬出去，而是“角色摘要 + 动作白名单 + 网站真相源”。
- 项目交付管理仍未建模，但它已退到 V2 后续主产品层，不再压过 Phase 1 的外化提醒与动作入口。
- 销售前端接入仍在讨论范围，但是否进入 V2 仍待 leadership 进一步确认。

## 当前工作流重点

### 1. OA P1 稳定化仍需保留

- 当前工作区仍有未提交的 OA / workflow 收口改动，后续接手时不要误回滚。
- 当前这轮已完成的 OA P1 重点包括：
  - 三端 action center 已形成 `下一步动作` 聚合视图
  - 请假驳回说明、补课偏好、补课确认回写、提案 warning 已进入结构化 payload
  - 学生确认中心可预览 workflow 方案
  - 学生首页已展示完整老师反馈
- 代码与测试事实：
  - `pytest -q tests/integration` on 2026-03-23 -> `67 passed`

### 2. V2 Phase 1 方向已锁定

- 第一阶段采用 `OpenClaw + Feishu`。
- 查询能力优先做角色摘要接口，不镜像站内整页 dashboard。
- 修改能力统一走 OpenClaw 专用动作网关，不做全量 API 后门。
- 鉴权方向已锁定为“服务 Token + 用户映射 + 服务端二次权限校验”。
- 请求方自报 `user=admin` 或共享管理员身份，不再作为可接受方案。

### 3. 本轮 API 外化盘点结论

- 当前仓库已经存在 `/oa/api/external/*` 雏形。
- 当前 external 层的核心问题不是“完全没有 API”，而是“对象 CRUD 多，安全动作 API 少”。
- `workflow / chat / action-center / feedback` 仍未 externalize。
- 当前高风险点包括：
  - `leave approve/reject`
  - `schedule external CRUD`
  - `todo external CRUD`
- 当前 external 鉴权仍只有单一 API key，尚不具备 actor 级身份语义。

### 4. 项目交付管理仍是 V2 后续层

- `ProjectTrack / SubProject / Milestone / Risk Board` 仍属于 V2 主产品层。
- 但当前默认顺序已调整为：
  - 先做外化提醒与动作网关
  - 再在这套底座上承接项目交付管理

## 推荐的下一步

1. 先把 `docs/versions/V2.md` 锁定为当前已决的 Phase 1 方案。
2. 收口现有 external 风险写口，避免继续扩张薄写接口。
3. 建 `ExternalIdentity / ReminderEvent / ReminderDelivery / IntegrationActionLog` 这套提醒与集成底座。
4. 建 OpenClaw 读接口与 `command` 写网关。
5. 先落第一批教务 / 老师动作，再考虑学生站外入口。

## 当前阻塞与开放点

- 外部学生提醒第一版采用什么通道，仍未锁死。
- 销售前端接入属于 V2 还是继续留在 V3，仍未锁死。
- 项目交付模型最终是否落成完整 `ProjectTrack / SubProject / Milestone` 三层，仍未锁死。
- 风险面板默认按学生、项目、负责人还是时间窗口聚合，仍未锁死。

## 接手规则

- 新 agent 接手时，先读 `docs/README.md`。
- 在继续当前开发时，先看本文件，再看 `docs/versions/V2.md`。
- 在开始实现 V2 前，先确认 `docs/versions/V2.md` 和本文件仍然一致。
- 做完较大任务后，回写本文件，而不是把状态塞回 `AGENTS.md`。
