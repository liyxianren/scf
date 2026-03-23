# OpenClaw Tools

这个目录是 OpenClaw / Feishu 外化联调的正式工具集。

当前建议只用这里的工具，不再直接依赖根目录里多份重复脚本。根目录保留的 Python 入口只是兼容包装。

## 目录结构

- `openclaw_api_smoke.py`
  - 通用 API smoke 客户端。
  - 用来模拟 “查询我的课表 / 查询我的待办 / 拉 reminder / ack reminder / 拉 daily brief”。
- `manage_external_identity.py`
  - 外部身份绑定管理工具。
  - 用来把 `provider + external_user_id` 绑定到网站里的真实 `User`。
  - 也负责切换绑定、停用绑定、查看当前绑定。
- `openclaw_integration_smoke.ps1`
  - Windows 下的快速入口。
  - 本质上是对 `openclaw_api_smoke.py` 的 PowerShell 包装。

## 核心原则

### 1. 网站用户才是真实身份

OpenClaw / Feishu 不是业务身份真相源。

当前可信链路是：

`provider + external_user_id -> ExternalIdentity -> User -> role/permission`

也就是说：

- 不要传 `user=liyu`
- 不要在 OpenClaw 侧自报 `admin`
- 一切权限最终都来自网站里的真实 `User.role`

对应模型在：

- [models.py](/C:/Users/ly/Desktop/scf-main/modules/auth/models.py#L276)

对应鉴权与映射逻辑在：

- [external_api.py](/C:/Users/ly/Desktop/scf-main/modules/oa/external_api.py#L42)
- [external_api.py](/C:/Users/ly/Desktop/scf-main/modules/oa/external_api.py#L59)

### 2. 一个 external_user_id 只能绑定一个真实用户

在同一个 `provider` 下，`external_user_id` 是唯一键。

这意味着：

- 一个 Feishu actor 入口同一时刻只能映射到一个网站用户
- 如果要从老师切到教务，本质上就是“换绑到另一个真实用户”
- 如果同一个真人既要看老师视角又要看 admin 视角，建议使用不同的 `external_user_id`，分别绑定到不同网站账号

### 3. cron 机器人不要和真人共用 external_user_id

`reminders/ack` 是按 `receiver_external_id` 生效的。

如果 cron 机器人和真人客户端共用同一个 `external_user_id`：

- 机器人 ack 之后
- 真人会看不到这些 reminder

所以建议：

- 真人：一个 `external_user_id`
- cron 机器人：单独一个 `external_user_id`

## 工具 1：API Smoke

脚本：

- `python scripts/openclaw_tools/openclaw_api_smoke.py`

### 查询我的课表

```bash
python scripts/openclaw_tools/openclaw_api_smoke.py --external-user-id ou_liyu schedule-query --date 2026-03-23
```

等价 alias：

```bash
python scripts/openclaw_tools/openclaw_api_smoke.py --external-user-id ou_liyu schedule --date 2026-03-23
```

### 查询我的 summary

```bash
python scripts/openclaw_tools/openclaw_api_smoke.py --external-user-id ou_liyu summary
```

### 查询我的 work-items

```bash
python scripts/openclaw_tools/openclaw_api_smoke.py --external-user-id ou_liyu work-items
```

### 查询 reminders

```bash
python scripts/openclaw_tools/openclaw_api_smoke.py --external-user-id ou_liyu reminders --status pending
```

### ack reminders

```bash
python scripts/openclaw_tools/openclaw_api_smoke.py --external-user-id ou_liyu ack --event-id 12 --event-id 18
```

### 拉取 daily brief

```bash
python scripts/openclaw_tools/openclaw_api_smoke.py --external-user-id ou_liyu daily-brief --date 2026-03-23
```

兼容 alias：

```bash
python scripts/openclaw_tools/openclaw_api_smoke.py --external-user-id ou_liyu daily-digest --date 2026-03-23
```

### 常用参数

- `--base-url`
  - 默认 `http://127.0.0.1:5000`
- `--token`
  - 默认 `openclaw233`
  - 正式环境必须改成环境变量管理，不要继续用默认值
- `--provider`
  - 默认 `feishu`
- `--external-user-id`
  - 必填
  - 必须是已经绑定好的外部身份，不是网站用户名
- `--json`
  - 输出原始 JSON

## 工具 2：真实用户绑定

脚本：

- `python scripts/openclaw_tools/manage_external_identity.py`

### 先看网站里有哪些真实用户

```bash
python scripts/openclaw_tools/manage_external_identity.py list-users --active-only
```

按角色查：

```bash
python scripts/openclaw_tools/manage_external_identity.py list-users --role teacher --active-only
```

### 查看当前有哪些外部绑定

```bash
python scripts/openclaw_tools/manage_external_identity.py list-bindings --provider feishu
```

### 绑定一个外部身份到真实用户

```bash
python scripts/openclaw_tools/manage_external_identity.py bind --provider feishu --external-user-id ou_liyu --username liyu
```

这条命令做的事情是：

- 在 `external_identities` 表里创建或更新一条记录
- 让 `feishu + ou_liyu` 指向网站里的 `username=liyu`

### 查看某个 external_user_id 现在绑到了谁

```bash
python scripts/openclaw_tools/manage_external_identity.py whois --provider feishu --external-user-id ou_liyu
```

### 用户切换 / 重新绑定

如果原来 `ou_liyu` 绑的是老师账号，现在想切到 admin 账号：

```bash
python scripts/openclaw_tools/manage_external_identity.py switch --provider feishu --external-user-id ou_liyu --username liyu_admin
```

这就是“用户切换”的正式做法。

本质不是改 OpenClaw 里的角色，而是把这个外部入口重新绑定到另一个真实网站用户。

### 暂时停用一个绑定

```bash
python scripts/openclaw_tools/manage_external_identity.py deactivate --provider feishu --external-user-id ou_liyu
```

恢复：

```bash
python scripts/openclaw_tools/manage_external_identity.py activate --provider feishu --external-user-id ou_liyu
```

## 真实绑定应该怎么做

推荐流程：

1. 先确认网站里真实用户已存在
   - 例如 `liyu`、`liyu_admin`
2. 拿到 OpenClaw / Feishu 侧真实 `external_user_id`
3. 用 `manage_external_identity.py bind` 建立映射
4. 用 `openclaw_api_smoke.py` 验证课表查询和 daily brief
5. 如果后续需要切角色，用 `switch`

## 关于“同一个人多角色”

当前系统里一个网站 `User` 只有一个 `role`。

所以：

- 一个老师账号不可能同时天然拥有 admin 视角
- 如果同一个真人既要老师视角又要 admin 视角，应该用两个网站账号
- 然后给这两个账号分别绑定不同的 `external_user_id`

不建议做：

- 同一个 `external_user_id` 在不同请求里临时自报 `teacher/admin`

因为这样会绕开真实权限模型。

## 当前已知缺口

这些不是脚本问题，是当前 API 的产品边界：

- `me/work-items` 没有 `today_only`
- `reminders` 更适合 pull feed，不是 daily digest 成品接口
- admin 的 `me/*` 语义仍偏全局总览，不完全是“我的”

所以第一版 daily brief 仍建议由脚本聚合：

- `summary`
- `today schedules`
- `work-items`
- `pending reminders`

## 环境说明

绑定工具默认读取当前应用配置，也就是：

- `SCF_DB_PATH`
- `OPENCLAW_INTEGRATION_TOKEN`

如果你要操作正式库，先确认环境变量和数据库路径正确，再执行绑定命令。
