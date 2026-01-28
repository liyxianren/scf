# 工程手册 (Engineering Handbook) 系统实施方案

## 一、需求概述

为 SCF Hub 平台添加"工程手册"功能,将学生的科创项目转化为专业的技术文档,用于大学申请。

### 核心需求
- **自动化程度**: 完全自动生成初稿,人工审核
- **语言版本**: 全中文
- **生成时机**: 项目结束后一次性生成
- **申请体系**: 美国/英国/港新三种体系,每种风格不同

### 申请体系差异

| 维度 | 美国体系 | 英国体系 | 港新体系 |
|------|---------|---------|---------|
| 核心关注 | 个人特质与成长 | 学术热情与深度 | 技术实力与规范 |
| 重点章节 | 执行摘要、反思展望 | 背景调研、技术选型 | 系统设计、测试验证 |
| 语言风格 | 叙事化、情感连接 | 学术化、客观严谨 | 技术化、数据支撑 |
| 建议篇幅 | 15-20页 | 10-15页 | 20-30页 |

## 二、系统架构设计

### 2.1 技术栈
- **后端**: Flask Blueprint + SQLAlchemy
- **AI生成**: DeepSeek-R1 (带深度思考能力)
- **异步处理**: Threading (daemon threads, 复用 ProjectPlan 模式)
- **文件存储**: 本地文件系统 `data/handbooks/`
- **前端**: Vanilla JS + Markdown 渲染

### 2.2 数据流
```
用户上传材料 → API保存文件 → 创建Handbook记录
→ 后台线程启动 → AI分析材料 → 逐章节生成
→ 体系化调整(美/英/港新) → 保存多版本 → 用户查看/下载
```

## 三、核心实现内容

### 3.1 数据库模型 (新增)

**文件**: [models/models.py](models/models.py)

新增 `EngineeringHandbook` 模型:

```python
class EngineeringHandbook(db.Model):
    __tablename__ = 'engineering_handbooks'

    # 基本信息
    id = Integer, PK
    project_name_cn = String(200)  # 项目中文名
    project_name_en = String(200)  # 项目英文名
    author_name = String(100)      # 学生姓名
    version = String(20)           # 版本号 v1.0.0
    completion_date = Date         # 完成日期

    # 目标体系 (JSON数组: ["US", "UK", "HK-SG"])
    target_systems = Text

    # 生成状态
    status = String(20)            # pending/generating/completed/failed
    content_versions = Text        # JSON: {"US": "...", "UK": "...", "HK-SG": "..."}

    # 输入材料
    project_description = Text     # 项目说明文档内容
    project_description_file = String(500)  # 上传文件路径
    source_code_url = String(500)  # GitHub URL
    source_code_file = String(500) # 代码ZIP路径
    process_materials = Text       # JSON数组:素材文件路径列表

    # 管理字段
    is_favorited = Boolean
    error_message = Text
    created_at = DateTime
    completed_at = DateTime
    expires_at = DateTime          # 30天过期(未收藏)
```

### 3.2 文件存储结构

创建目录结构:
```
data/handbooks/
├── uploads/           # 用户上传的材料
│   ├── 1/            # Handbook ID
│   │   ├── description.pdf
│   │   ├── code.zip
│   │   └── materials/
│   │       ├── screenshot1.png
│   │       └── test_data.xlsx
│   └── 2/
└── generated/        # 生成的手册
    ├── 1/
    │   ├── handbook_US.md
    │   ├── handbook_UK.md
    │   └── handbook_HK-SG.md
    └── 2/
```

**新建文件**: [utils/storage_helper.py](utils/storage_helper.py)

工具函数:
- `get_upload_dir(handbook_id)` - 获取上传目录
- `get_generated_dir(handbook_id)` - 获取生成文件目录
- `save_uploaded_file(file, handbook_id, subdir)` - 保存上传文件

### 3.3 API路由

**新建文件**: [routes/handbook_routes.py](routes/handbook_routes.py)

注册蓝图: `app.register_blueprint(handbook_bp, url_prefix='/company/handbook')`

#### 页面路由
- `GET /company/handbook/generator` → [handbook_generator.html](templates/handbook_generator.html)
- `GET /company/handbook/library` → [handbook_library.html](templates/handbook_library.html)
- `GET /company/handbook/library/<id>` → [handbook_detail.html](templates/handbook_detail.html)

#### API路由
- `GET /company/handbook/api/handbooks` - 获取所有手册列表
- `GET /company/handbook/api/handbooks/<id>` - 获取单个手册详情
- `POST /company/handbook/api/handbooks/upload` - 上传材料并创建记录
- `POST /company/handbook/api/handbooks/<id>/generate` - 触发生成(后台异步)
- `GET /company/handbook/api/handbooks/<id>/download/<system_type>` - 下载特定版本
- `POST /company/handbook/api/handbooks/<id>/favorite` - 切换收藏
- `DELETE /company/handbook/api/handbooks/<id>` - 删除手册

### 3.4 AI生成引擎

**新建文件**: [utils/handbook_agent.py](utils/handbook_agent.py)

#### 生成流程 (5节点流水线)

```
Node 1: 材料分析
   ↓ (提取关键信息: 问题陈述/技术栈/目标用户/挑战/成果)
Node 2-3: 章节生成 (8大章节)
   ↓ (每章节根据体系调整prompt)
Node 4: 体系化适配
   ↓ (美国→叙事化 | 英国→学术化 | 港新→技术化)
Node 5: 组装打磨
   ↓ (添加目录/页眉页脚/格式统一)
```

#### 8大章节结构

1. **元数据 (Metadata)**: 项目名/版本/作者/修订历史/术语表
2. **执行摘要 (Executive Summary)**: 问题陈述/解决方案/关键指标/个人贡献 (1页)
3. **问题定义与需求分析**: 背景调研/利益相关者/需求规格/成功标准
4. **系统设计**: 技术选型/架构设计/数据流/接口规范
5. **实现与迭代** ⭐核心章节: 开发环境/模块实现/技术挑战/版本迭代
6. **测试与验证**: 测试策略/测试用例/性能基准/用户反馈
7. **反思与展望**: 经验总结/技术债务/未来改进
8. **附录**: 代码链接/代码片段/数据样本/参考文献

#### 核心类设计

```python
class HandbookAgent:
    def __init__(self):
        self.client = DeepSeekClient()  # 使用DeepSeek-R1
        self.sections = [
            'metadata', 'executive_summary',
            'problem_definition', 'system_design',
            'implementation',  # 核心章节
            'testing', 'reflection', 'appendix'
        ]

    def generate_handbook(
        project_description, system_type,
        project_name_cn, project_name_en,
        author_name, source_code_url, ...
    ):
        # 1. 材料分析
        analysis = self._analyze_materials(...)

        # 2-3. 逐章节生成
        sections_content = {}
        for section in self.sections:
            content = self._generate_section(
                section, analysis, system_type, ...
            )
            sections_content[section] = content

        # 4-5. 组装打磨
        final_handbook = self._assemble_handbook(
            sections_content, system_type, ...
        )
        return final_handbook

    def _get_section_prompt(section, system_type):
        # 基础prompt + 体系化调整prompt
        base_prompts = {...}
        system_adaptations = {
            'US': "叙事化、情感连接...",
            'UK': "学术化、引用论文...",
            'HK-SG': "技术化、数据支撑..."
        }
        return base_prompts[section] + system_adaptations[system_type]
```

### 3.5 前端界面

#### 3.5.1 生成器页面

**新建**: [templates/handbook_generator.html](templates/handbook_generator.html)

功能:
- 项目信息表单 (中文名/英文名/作者)
- 目标体系多选框 (美国/英国/港新)
- 文件上传区域:
  - 项目说明文档 (PDF/Word/Markdown)
  - 源代码 (GitHub URL 或 ZIP)
  - 过程素材 (多文件: 截图/测试数据等)
- 提交按钮触发上传 + 生成
- 进度指示器

#### 3.5.2 手册库页面

**新建**: [templates/handbook_library.html](templates/handbook_library.html)

功能:
- 卡片网格布局 (类似 plans.html)
- 筛选标签: 全部/已收藏/已完成/生成中/失败
- 每个卡片显示:
  - 项目名称 (中英文)
  - 目标体系徽章
  - 状态徽章 (颜色编码)
  - 创建日期
  - 操作按钮: 查看/下载/收藏/删除
- 实时轮询 (5秒间隔) 更新生成中的状态

#### 3.5.3 手册详情页

**新建**: [templates/handbook_detail.html](templates/handbook_detail.html)

功能:
- 标签页切换体系版本 (美国/英国/港新)
- Markdown渲染 + 语法高亮
- 目录侧边栏 (自动从标题生成)
- 下载按钮 (按版本)
- 元数据显示 (版本/作者/日期)

### 3.6 后台异步生成

**复用模式**: 参考 `agent_routes.py` 中的 `_generate_plan_background`

```python
def _generate_handbook_background(app, handbook_id):
    with app.app_context():
        handbook = EngineeringHandbook.query.get(handbook_id)
        handbook.status = 'generating'
        db.session.commit()

        try:
            agent = HandbookAgent()
            target_systems = json.loads(handbook.target_systems)
            content_map = {}

            # 为每个目标体系生成
            for system in target_systems:  # ["US", "UK", "HK-SG"]
                content = agent.generate_handbook(
                    project_description=handbook.project_description,
                    system_type=system,
                    ...
                )
                content_map[system] = content

            handbook.content_versions = json.dumps(content_map)
            handbook.status = 'completed'
            handbook.completed_at = datetime.utcnow()
            db.session.commit()

        except Exception as e:
            handbook.status = 'failed'
            handbook.error_message = str(e)
            db.session.commit()
```

## 四、实施步骤

### Phase 1: 数据库与存储 (第1周)
1. 在 [models/models.py](models/models.py) 添加 `EngineeringHandbook` 模型
2. 更新 [init_db.py](init_db.py) 数据库初始化
3. 创建 `data/handbooks/` 目录结构
4. 实现 [utils/storage_helper.py](utils/storage_helper.py)

### Phase 2: 后端API (第2周)
5. 创建 [routes/handbook_routes.py](routes/handbook_routes.py)
6. 实现所有API端点
7. 实现文件上传处理逻辑
8. 在 [app.py](app.py) 注册blueprint

### Phase 3: AI生成引擎 (第3周)
9. 创建 [utils/handbook_agent.py](utils/handbook_agent.py)
10. 实现材料分析节点 (Node 1)
11. 实现8个章节的生成prompt (Node 2-3)
12. 实现体系化适配逻辑 (Node 4)
13. 实现组装函数 (Node 5)
14. 用样本项目测试生成质量

### Phase 4: 前端界面 (第4周)
15. 创建 [templates/handbook_generator.html](templates/handbook_generator.html)
16. 实现文件上传表单与验证
17. 创建 [templates/handbook_library.html](templates/handbook_library.html)
18. 实现状态轮询与实时更新
19. 创建 [templates/handbook_detail.html](templates/handbook_detail.html)
20. 集成Markdown渲染

### Phase 5: 测试与优化 (第5周)
21. 端到端测试 (真实项目材料)
22. Prompt调优 (基于生成质量)
23. UI/UX改进
24. 错误处理完善
25. 性能优化

## 五、关键文件清单

### 需要创建的文件 (5个核心 + 3个模板)

**后端核心**:
1. [routes/handbook_routes.py](routes/handbook_routes.py) - 所有API端点和路由
2. [utils/handbook_agent.py](utils/handbook_agent.py) - AI生成引擎核心逻辑
3. [utils/storage_helper.py](utils/storage_helper.py) - 文件存储工具函数

**前端模板**:
4. [templates/handbook_generator.html](templates/handbook_generator.html) - 上传与生成界面
5. [templates/handbook_library.html](templates/handbook_library.html) - 手册管理界面
6. [templates/handbook_detail.html](templates/handbook_detail.html) - 手册详情查看

### 需要修改的文件 (3个)

7. [models/models.py](models/models.py) - 添加 `EngineeringHandbook` 模型
8. [app.py](app.py) - 注册新的 blueprint
9. [init_db.py](init_db.py) - 添加数据库初始化逻辑

### 需要创建的目录

10. `data/handbooks/uploads/` - 用户上传材料
11. `data/handbooks/generated/` - AI生成手册

## 六、技术要点

### 6.1 Prompt工程策略

每个章节需要精心设计prompt:
- **平衡结构与创意**: 既要保证规范性,又要鼓励个性化
- **融入体系差异**: 自然体现美/英/港新的风格差异
- **控制技术深度**: 引导AI使用适当的技术细节
- **强调证据支撑**: 要求基于事实而非泛泛而谈

示例 (系统设计章节 - 港新体系):
```
# Task
生成系统设计章节,包括:
- 技术选型与理由 (为什么选择这些技术)
- 系统架构设计 (整体结构、模块划分、依赖关系)
- 数据流与交互逻辑
- 接口规范 (API定义、数据格式、错误处理)

# System-Specific Requirements (港新体系)
- 核心关注: 技术硬实力和工程规范性
- 系统设计: 非常详细,包括完整的架构图和数据流图
- 建议使用 Mermaid 图表描述架构
- 技术细节完整呈现

# Output Format
直接输出 Markdown 格式内容。
```

### 6.2 材料质量评估

生成前检查材料充分性:
- **最低要求**: 项目说明文档 (至少500字)
- **推荐配置**: 源代码 + 过程素材
- **不足时**: 显示补充清单,建议需要哪些材料

### 6.3 生成时间管理

完整生成 (3体系 × 8章节) 预计 10-20 分钟:
- 使用后台daemon线程避免超时
- 提供细粒度进度更新 (按章节)
- 允许用户离开后回来查看
- 考虑并行生成多体系 (ThreadPoolExecutor)

### 6.4 内容验证

生成后验证:
- Markdown语法正确性
- 章节完整性 (8个章节都存在)
- 长度适当性 (美:15-20页 | 英:10-15页 | 港新:20-30页)
- 无占位符或不完整句子
- 术语有适当解释

### 6.5 安全考虑

- 文件上传sanitization (安全文件名)
- 文件类型和大小验证
- 文件存储在web根目录外
- 不向前端暴露内部路径
- 考虑敏感项目材料加密存储

## 七、未来扩展方向

### 7.1 更多申请体系
- 加拿大/澳洲/欧洲体系
- 只需添加新的体系化prompt变体

### 7.2 语言支持
- 生成纯英文版本
- 中英双语对照版本

### 7.3 导出格式
- Word (.docx) 带格式
- PDF 专业模板
- LaTeX 学术出版

### 7.4 协作编辑
- 多用户审阅与评论
- 版本控制
- 修改对比视图

### 7.5 模板库
- 常见项目类型预置模板
- 行业特定手册结构

### 7.6 智能补充建议
- 分析生成的手册
- 识别薄弱章节
- 建议具体补充材料

## 八、风险与对策

### 风险1: AI生成质量不稳定
**对策**:
- 多轮测试调优prompt
- 提供人工编辑功能
- 允许重新生成特定章节

### 风险2: 生成时间过长
**对策**:
- 后台异步处理
- 进度实时反馈
- 考虑分阶段生成+合并

### 风险3: 材料不足导致内容空洞
**对策**:
- 上传前材料质量检查
- 提供详细的补充清单
- 可选的人工补充环节

### 风险4: 不同体系风格差异不明显
**对策**:
- 强化体系化prompt差异
- 对比测试三种版本
- 参考真实申请文档样本

## 九、成功标准

1. ✅ 能够成功上传项目材料并创建记录
2. ✅ 后台异步生成稳定运行,无超时
3. ✅ 生成的手册包含完整的8个章节
4. ✅ 美/英/港新三种版本风格差异明显
5. ✅ Markdown格式正确,可正常渲染
6. ✅ 用户可以查看、下载、收藏手册
7. ✅ 界面友好,操作流程清晰
8. ✅ 错误处理完善,异常情况有明确提示

---

**实施优先级**: 按Phase 1-5顺序递进,每个阶段完成后可交付可测试的功能模块。

**预计工期**: 5周 (每周约20-30小时开发时间)

**技术依赖**: DeepSeek API配额充足,文件存储空间足够 (预估每个手册约5-10MB)
