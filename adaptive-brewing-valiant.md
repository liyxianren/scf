# 专业级 DOCX 导出功能实现计划

## 目标

将当前简陋的 DOCX 导出功能升级为**生产级质量**，用户下载后可直接使用，无需任何手动调整。

---

## 当前问题分析

### 现有实现的缺陷（`utils/export_helper.py`）

| 问题类别 | 具体问题 | 严重程度 |
|----------|----------|----------|
| **列表处理** | 只支持 `- ` 无序列表，不支持有序列表 `1.` | 严重 |
| | 不支持嵌套列表（多级缩进） | 严重 |
| | 列表后续段落缩进丢失 | 中等 |
| **内联格式** | 不支持 `**粗体**` | 严重 |
| | 不支持 `*斜体*` | 严重 |
| | 不支持 `` `代码` `` 内联格式 | 中等 |
| | 不支持 `[链接](url)` | 中等 |
| **标题层级** | 只处理 `#`、`##`、`###`，缺少 4-6 级 | 中等 |
| | 标题样式未自定义（使用默认样式） | 中等 |
| **表格** | 无边框样式 | 严重 |
| | 无表头背景色 | 中等 |
| | 单元格内不支持格式 | 中等 |
| **代码块** | 无背景色/边框 | 中等 |
| | 不区分语言高亮 | 低 |
| **字体** | 未设置中文字体（宋体/微软雅黑） | 严重 |
| | 西文字体未统一 | 中等 |
| **页面布局** | 无页眉页脚 | 中等 |
| | 无页码 | 中等 |
| | 无目录（TOC） | 低 |
| **特殊内容** | Mermaid 图无法渲染（直接显示代码） | 中等 |

---

## 技术方案

### 核心依赖

```
python-docx>=0.8.11  # Word 文档生成
lxml                 # XML 处理（python-docx 依赖）
```

### 架构设计

```
MarkdownToDocxConverter
├── MarkdownParser          # Markdown 解析器
│   ├── BlockParser         # 块级元素解析（标题、段落、列表、表格、代码块）
│   └── InlineParser        # 内联元素解析（粗体、斜体、代码、链接）
├── DocxStyleManager        # Word 样式管理器
│   ├── 标题样式 (Heading 1-6)
│   ├── 正文样式 (Normal, Body Text)
│   ├── 列表样式 (List Bullet, List Number, 多级)
│   ├── 代码样式 (Code Block, Inline Code)
│   └── 表格样式 (Table Grid, Header Row)
├── DocxRenderer            # Word 渲染器
│   ├── render_heading()
│   ├── render_paragraph()
│   ├── render_list()
│   ├── render_table()
│   ├── render_code_block()
│   └── render_inline()
└── PageLayoutManager       # 页面布局管理器
    ├── setup_page()        # 页面尺寸、边距
    ├── add_header()        # 页眉
    ├── add_footer()        # 页脚（页码）
    └── add_toc()           # 目录（可选）
```

---

## 详细实现规格

### 1. 字体配置

```python
FONT_CONFIG = {
    # 中文字体
    "cn_heading": "微软雅黑",      # 标题
    "cn_body": "宋体",             # 正文
    # 西文字体
    "en_heading": "Arial",         # 标题
    "en_body": "Times New Roman",  # 正文
    "code": "Consolas",            # 代码
    # 字号（磅）
    "size_h1": 22,
    "size_h2": 16,
    "size_h3": 14,
    "size_h4": 12,
    "size_body": 11,
    "size_code": 9,
}
```

### 2. 列表处理

**无序列表**（支持 `-`、`*`、`+`）：
```markdown
- 第一级
  - 第二级
    - 第三级
```
转换为 Word 多级列表，使用圆点 → 空心圆 → 方块符号。

**有序列表**（支持 `1.`、`1)`）：
```markdown
1. 第一项
2. 第二项
   1. 嵌套项
```
转换为 Word 编号列表，支持 `1. 1.1 1.1.1` 格式。

**实现要点**：
- 使用 `python-docx` 的 `numbering` 模块创建自定义列表样式
- 通过缩进检测（2/4空格或制表符）识别嵌套层级
- 最多支持 3 级嵌套

### 3. 内联格式解析

使用正则表达式解析内联格式：

```python
INLINE_PATTERNS = [
    (r'\*\*(.+?)\*\*', 'bold'),           # **粗体**
    (r'\*(.+?)\*', 'italic'),              # *斜体*
    (r'`(.+?)`', 'code'),                  # `代码`
    (r'\[(.+?)\]\((.+?)\)', 'link'),       # [文本](链接)
]
```

**渲染逻辑**：
```python
def render_inline(paragraph, text):
    """将带格式的文本添加到段落"""
    # 1. 解析文本，识别所有内联格式
    # 2. 按顺序创建 Run，应用对应格式
    # 3. 粗体：run.bold = True
    # 4. 斜体：run.italic = True
    # 5. 代码：run.font.name = "Consolas", 背景色
    # 6. 链接：添加超链接
```

### 4. 表格样式

```python
TABLE_STYLE = {
    "border_color": "000000",      # 黑色边框
    "border_width": Pt(0.5),       # 边框宽度
    "header_bg": "0EA5E9",         # 表头背景色（科技蓝）
    "header_text_color": "FFFFFF", # 表头文字颜色（白色）
    "cell_padding": Pt(5),         # 单元格内边距
    "alternate_row_bg": "F8FAFC",  # 隔行背景色（浅灰）
}
```

**实现**：
- 使用 `python-docx` 的 `Table` API
- 通过 `OxmlElement` 设置边框和背景色
- 表头行加粗、居中、背景色
- 支持单元格内的粗体/斜体

### 5. 代码块样式

```python
CODE_BLOCK_STYLE = {
    "font": "Consolas",
    "font_size": Pt(9),
    "bg_color": "F4F4F5",          # 浅灰背景
    "border_color": "E4E4E7",      # 边框颜色
    "padding": Pt(8),              # 内边距
    "line_spacing": 1.2,           # 行间距
}
```

**实现**：
- 代码块作为单独段落，设置背景色和边框
- 保留原始缩进和换行
- 使用等宽字体

### 6. 页面布局

```python
PAGE_LAYOUT = {
    "width": Inches(8.27),         # A4 宽度
    "height": Inches(11.69),       # A4 高度
    "margin_top": Inches(1),
    "margin_bottom": Inches(1),
    "margin_left": Inches(1.25),
    "margin_right": Inches(1.25),
}
```

**页眉**：
- 左侧：文档标题
- 右侧：体系版本（US/UK/HK-SG）

**页脚**：
- 居中：页码（第 X 页 / 共 Y 页）

### 7. Mermaid 图处理

由于 Word 无法原生渲染 Mermaid，采用以下策略：

**方案 A（推荐）**：占位符提示
```
[Mermaid 图表]
请使用 Mermaid Live Editor (https://mermaid.live) 查看以下代码：
---
graph TD
    A --> B
---
```

**方案 B（可选扩展）**：服务端渲染为图片后嵌入
- 调用 mermaid-cli 或在线 API 渲染为 PNG
- 将图片嵌入 Word 文档

---

## 文件修改清单

### 1. 重写 `utils/export_helper.py`

完全重写，新结构约 400-500 行代码：

```python
# utils/export_helper.py

import io
import re
from docx import Document
from docx.shared import Pt, Inches, RGBColor
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.enum.table import WD_TABLE_ALIGNMENT
from docx.oxml.ns import qn
from docx.oxml import OxmlElement


class MarkdownToDocxConverter:
    """专业级 Markdown 转 Word 转换器"""

    def __init__(self, title="工程手册", system_type="US"):
        self.title = title
        self.system_type = system_type
        self.doc = Document()
        self._setup_styles()
        self._setup_page_layout()

    def convert(self, md_content: str) -> bytes:
        """转换 Markdown 为 Word 文档字节流"""
        self._add_header_footer()
        self._parse_and_render(md_content)

        buffer = io.BytesIO()
        self.doc.save(buffer)
        return buffer.getvalue()

    def _setup_styles(self):
        """配置文档样式"""
        # 标题样式
        # 正文样式
        # 列表样式
        # 代码样式
        # 表格样式
        pass

    def _setup_page_layout(self):
        """配置页面布局"""
        pass

    def _add_header_footer(self):
        """添加页眉页脚"""
        pass

    def _parse_and_render(self, md_content: str):
        """解析并渲染 Markdown 内容"""
        pass


class HandbookExporter:
    """工程手册导出工具（保持原有接口）"""

    def to_word(self, md_content: str, title: str = "工程手册",
                system_type: str = "US") -> bytes:
        converter = MarkdownToDocxConverter(title, system_type)
        return converter.convert(md_content)

    def to_pdf(self, md_content: str, title: str = "工程手册") -> bytes:
        # PDF 导出保持原有实现
        pass
```

### 2. 无需修改的文件

- `routes/handbook_routes.py` - 接口已支持多格式，无需改动
- `utils/handbook_agent.py` - 与导出无关

---

## 核心代码实现细节

### 列表解析与渲染

```python
def _parse_list_block(self, lines: list) -> list:
    """解析列表块，返回结构化列表数据"""
    result = []
    stack = []  # (indent_level, list_type, items)

    for line in lines:
        indent = len(line) - len(line.lstrip())
        content = line.strip()

        # 判断列表类型
        if content.startswith(('- ', '* ', '+ ')):
            list_type = 'bullet'
            text = content[2:]
        elif re.match(r'^\d+[\.\)] ', content):
            list_type = 'number'
            text = re.sub(r'^\d+[\.\)] ', '', content)
        else:
            continue

        level = indent // 2  # 每2空格一级
        result.append({
            'level': level,
            'type': list_type,
            'text': text
        })

    return result

def _render_list(self, list_data: list):
    """渲染列表到 Word"""
    for item in list_data:
        level = item['level']
        list_type = item['type']
        text = item['text']

        # 创建段落
        p = self.doc.add_paragraph()

        # 设置列表样式
        if list_type == 'bullet':
            style_name = f'List Bullet {level + 1}' if level < 3 else 'List Bullet 3'
        else:
            style_name = f'List Number {level + 1}' if level < 3 else 'List Number 3'

        p.style = style_name

        # 渲染内联格式
        self._render_inline_to_paragraph(p, text)
```

### 表格渲染

```python
def _render_table(self, rows: list):
    """渲染表格"""
    if not rows:
        return

    # 创建表格
    table = self.doc.add_table(rows=len(rows), cols=len(rows[0]))
    table.alignment = WD_TABLE_ALIGNMENT.CENTER

    # 设置表格边框
    self._set_table_borders(table)

    for row_idx, row_data in enumerate(rows):
        row = table.rows[row_idx]
        for col_idx, cell_text in enumerate(row_data):
            cell = row.cells[col_idx]

            # 表头样式
            if row_idx == 0:
                self._set_cell_shading(cell, "0EA5E9")
                p = cell.paragraphs[0]
                p.alignment = WD_ALIGN_PARAGRAPH.CENTER
                run = p.add_run(cell_text)
                run.bold = True
                run.font.color.rgb = RGBColor(255, 255, 255)
            else:
                # 隔行背景色
                if row_idx % 2 == 0:
                    self._set_cell_shading(cell, "F8FAFC")
                self._render_inline_to_paragraph(cell.paragraphs[0], cell_text)

def _set_table_borders(self, table):
    """设置表格边框"""
    tbl = table._tbl
    tblPr = tbl.tblPr if tbl.tblPr is not None else OxmlElement('w:tblPr')
    tblBorders = OxmlElement('w:tblBorders')

    for border_name in ['top', 'left', 'bottom', 'right', 'insideH', 'insideV']:
        border = OxmlElement(f'w:{border_name}')
        border.set(qn('w:val'), 'single')
        border.set(qn('w:sz'), '4')
        border.set(qn('w:color'), '000000')
        tblBorders.append(border)

    tblPr.append(tblBorders)
    tbl.tblPr = tblPr

def _set_cell_shading(self, cell, color: str):
    """设置单元格背景色"""
    shading = OxmlElement('w:shd')
    shading.set(qn('w:fill'), color)
    cell._tc.get_or_add_tcPr().append(shading)
```

### 内联格式渲染

```python
def _render_inline_to_paragraph(self, paragraph, text: str):
    """渲染带内联格式的文本到段落"""
    # 定义格式模式
    patterns = [
        (r'\*\*(.+?)\*\*', 'bold'),
        (r'\*(.+?)\*', 'italic'),
        (r'`(.+?)`', 'code'),
        (r'\[(.+?)\]\((.+?)\)', 'link'),
    ]

    # 合并所有模式
    combined = '|'.join(f'({p[0]})' for p in patterns)

    last_end = 0
    for match in re.finditer(combined, text):
        # 添加匹配前的普通文本
        if match.start() > last_end:
            paragraph.add_run(text[last_end:match.start()])

        # 确定匹配的是哪种格式
        matched_text = match.group(0)

        if matched_text.startswith('**'):
            content = re.match(r'\*\*(.+?)\*\*', matched_text).group(1)
            run = paragraph.add_run(content)
            run.bold = True
        elif matched_text.startswith('*'):
            content = re.match(r'\*(.+?)\*', matched_text).group(1)
            run = paragraph.add_run(content)
            run.italic = True
        elif matched_text.startswith('`'):
            content = re.match(r'`(.+?)`', matched_text).group(1)
            run = paragraph.add_run(content)
            run.font.name = 'Consolas'
            run.font.size = Pt(9)
            # 内联代码背景色需要额外处理
        elif matched_text.startswith('['):
            link_match = re.match(r'\[(.+?)\]\((.+?)\)', matched_text)
            link_text = link_match.group(1)
            link_url = link_match.group(2)
            self._add_hyperlink(paragraph, link_url, link_text)

        last_end = match.end()

    # 添加剩余的普通文本
    if last_end < len(text):
        paragraph.add_run(text[last_end:])
```

---

## 验证测试用例

### 测试 1：列表渲染

输入：
```markdown
- 第一项
- 第二项
  - 嵌套项 A
  - 嵌套项 B
- 第三项

1. 有序第一
2. 有序第二
   1. 嵌套有序
```

预期：Word 中显示正确的多级列表，带符号/编号。

### 测试 2：内联格式

输入：
```markdown
这是**粗体**和*斜体*，以及`代码`，还有[链接](https://example.com)。
```

预期：粗体加粗、斜体倾斜、代码等宽字体、链接可点击。

### 测试 3：表格

输入：
```markdown
| 列1 | 列2 | 列3 |
|-----|-----|-----|
| A   | B   | C   |
| D   | E   | F   |
```

预期：表格有边框、表头蓝色背景白色文字、隔行浅灰背景。

### 测试 4：代码块

输入：
```markdown
​```python
def hello():
    print("Hello")
​```
```

预期：灰色背景、Consolas 字体、保留缩进。

### 测试 5：完整手册

使用 `盲人视觉辅助系统_US_工程手册.md` 生成 DOCX，检查：
- [ ] 所有标题层级正确
- [ ] 列表格式正确
- [ ] 表格样式美观
- [ ] 代码块清晰可读
- [ ] Mermaid 图有占位提示
- [ ] 页眉页脚正确
- [ ] 整体排版专业

---

## 实现步骤

| 步骤 | 任务 | 预计代码量 |
|------|------|------------|
| 1 | 创建 `MarkdownToDocxConverter` 类框架 | 50 行 |
| 2 | 实现样式配置 `_setup_styles()` | 80 行 |
| 3 | 实现页面布局 `_setup_page_layout()` | 30 行 |
| 4 | 实现 Markdown 块级解析 | 100 行 |
| 5 | 实现内联格式解析 `_render_inline_to_paragraph()` | 60 行 |
| 6 | 实现列表渲染 `_render_list()` | 50 行 |
| 7 | 实现表格渲染 `_render_table()` | 70 行 |
| 8 | 实现代码块渲染 | 40 行 |
| 9 | 实现页眉页脚 | 40 行 |
| 10 | 集成测试与调试 | - |

**总计约 500 行代码**

---

## 依赖确认

当前 `requirements.txt` 已包含：
- `python-docx` - 需确认版本 >= 0.8.11

无需新增依赖。
