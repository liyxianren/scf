import hashlib
import json
import os
import re
from utils.deepseek_client import DeepSeekClient


SECTION_TITLES = {
    "metadata": "元数据",
    "executive_summary": "执行摘要",
    "problem_definition": "问题定义与需求分析",
    "system_design": "系统设计",
    "implementation": "实现与迭代",
    "testing": "测试与验证",
    "reflection": "反思与展望",
    "appendix": "附录",
}


SYSTEM_STYLES = {
    "US": (
        "【申请体系】美国本科（Common App / Coalition App）\n"
        "【核心目标】展示申请者作为一个人的特质、动机和成长历程\n"
        "【写作风格要求】\n"
        "1. 使用第一人称叙事，建立情感连接\n"
        "2. 每个技术决策都要说明“我为什么这样选择”\n"
        "3. 适度加入困难时刻的心理描写和克服过程\n"
        "4. 强调项目对自己的影响和个人成长\n"
        "【章节侧重】\n"
        "- 执行摘要：强调个人动机\n"
        "- 问题定义：加入对社区/用户的实际影响\n"
        "- 实现与迭代：描述遇到困难时的心理状态和坚持\n"
        "- 反思与展望：核心章节，篇幅更大\n"
    ),
    "UK": (
        "【申请体系】英国 UCAS Personal Statement 配套材料\n"
        "【核心目标】展示对所申请学科的学术热情和知识深度\n"
        "【写作风格要求】\n"
        "1. 学术化、客观严谨，避免过多个人情感表达\n"
        "2. 强调对技术原理和学术背景的理解\n"
        "3. 技术选型需体现学术思考\n"
        "4. 参考文献必须规范\n"
        "【章节侧重】\n"
        "- 问题定义：详实，展示领域现状\n"
        "- 系统设计：技术选型部分需引用权威资料\n"
        "- 附录：参考文献规范完整\n"
    ),
    "HK-SG": (
        "【申请体系】香港、新加坡院校本科申请\n"
        "【核心目标】展示技术硬实力和工程规范性\n"
        "【写作风格要求】\n"
        "1. 技术化、数据驱动\n"
        "2. 大量使用图表、代码和量化数据\n"
        "3. 强调工程规范和最佳实践\n"
        "4. 详细的技术细节展示\n"
        "【章节侧重】\n"
        "- 系统设计：必须包含架构图、数据流图\n"
        "- 实现与迭代：多展示代码片段\n"
        "- 测试与验证：量化数据充分\n"
    ),
}


SYSTEM_SECTION_WEIGHTS = {
    "US": {
        "metadata": "标准",
        "executive_summary": "详细（强调个人动机，约1.5页）",
        "problem_definition": "中等（强调社会影响）",
        "system_design": "中等",
        "implementation": "中等（强调克服困难的过程）",
        "testing": "简要",
        "reflection": "非常详细（核心章节，约3-4页）",
        "appendix": "简要",
    },
    "UK": {
        "metadata": "标准",
        "executive_summary": "简要客观",
        "problem_definition": "非常详细（核心章节，强调学术调研，约3-4页）",
        "system_design": "详细（强调技术论证和引用）",
        "implementation": "中等",
        "testing": "中等",
        "reflection": "中等（学术反思风格）",
        "appendix": "详细（必须有规范的参考文献列表）",
    },
    "HK-SG": {
        "metadata": "标准",
        "executive_summary": "简要（数据驱动）",
        "problem_definition": "中等",
        "system_design": "非常详细（核心章节，必须有多个Mermaid图，约4-5页）",
        "implementation": "详细（多代码片段，约4-5页）",
        "testing": "非常详细（核心章节，大量表格和数据，约3-4页）",
        "reflection": "简要",
        "appendix": "详细（完整代码和数据样本）",
    },
}


COMMON_SECTION_CONSTRAINTS = (
    "【关键约束 - 必须遵守】\n"
    "1. 只使用分析信息中明确提供的数据，禁止虚构任何具体的：\n"
    "   - 人名、团队成员名字\n"
    "   - 代码仓库链接、URL\n"
    "   - 具体数字（准确率、延迟、百分比等）\n"
    "   - 用户反馈、测试案例\n"
    "2. 当信息不足时，使用占位符明确标注，格式为：[待补充：xxx]\n"
    "3. 避免使用例如/如/比如来引入编造的例子\n"
    "4. 可以基于技术栈进行合理的技术原理解释，但不能编造项目特定细节\n"
    "【Markdown 格式要求 - 严格遵守】\n"
    "1. 无序列表只能使用 - 开头（禁止 * 或 +）\n"
    "2. 有序列表编号规则（极其重要）：\n"
    "   - 每个独立的有序列表必须从 1. 开始\n"
    "   - 列表项之间不要有空行\n"
    "   - 不同主题的列表之间必须用空行分隔\n"
    "   - 禁止跨段落连续编号（错误示例：2. 3. 4.）\n"
    "3. 绝对禁止使用以下符号：点号圆圈方块箭头等特殊符号\n"
    "4. 多级列表使用4个空格缩进\n"
)


BASE_SECTION_PROMPTS = {
    "metadata": (
        "生成文档元数据内容，严格要求：\n"
        "1. 项目名称（中英文），英文名若未提供请合理翻译并标注[自动翻译]\n"
        "2. 作者信息：未提供则写“作者：[待补充]”\n"
        "3. 版本号：使用分析信息中的版本号\n"
        "4. 完成日期：未提供则写[待补充完成日期]\n"
        "5. 文档编号：使用分析信息中的document_id\n"
        "6. 修订历史（Markdown表格）\n"
        "| 版本号 | 修订日期 | 修订人 | 修订说明 |\n"
        "|--------|----------|--------|----------|\n"
        "| v1.0.0 | [日期] | [作者] | 初版文档建立 |\n"
        "7. 术语表（Markdown表格，3-6个关键术语）\n"
        "| 术语 | 定义 | 项目应用 |\n"
        "|------|------|----------|\n"
        "| [术语1] | 通用定义 | [待补充具体应用场景] |\n"
        "仅输出内容，不要输出标题。"
    ),
    "executive_summary": (
        "生成执行摘要，控制在1页以内，包含：\n"
        "1. 问题陈述：基于problem_statement，未提供则写“本项目旨在[待补充：具体问题描述]”\n"
        "2. 解决方案概述：基于solution_summary与tech_stack\n"
        "3. 关键技术指标：列出3-5条，仅使用provided_metrics；若为空，输出待补充占位符\n"
        "4. 个人贡献声明：若作者未提供则写“本人在项目中负责[待补充：具体贡献内容]”\n"
        "仅输出内容，不要输出标题。"
    ),
    "problem_definition": (
        "生成问题定义与需求分析章节，包含：\n"
        "1. 背景调研：问题重要性、现有方案不足（缺失则标注[待补充]）、相关技术现状\n"
        "2. 利益相关者分析：主要用户群体、核心诉求、约束条件\n"
        "3. 需求规格说明（表格）\n"
        "| 需求类型 | 需求描述 | 优先级 |\n"
        "|----------|----------|--------|\n"
        "| 功能性需求 | [基于solution_summary推断] | 高 |\n"
        "| 非功能性需求 | [如性能/安全/可用性] | 中 |\n"
        "4. 成功标准定义：有指标则引用，缺失则输出待补充占位符\n"
        "仅输出内容，不要输出标题。"
    ),
    "system_design": (
        "生成系统设计章节，要求：\n"
        "1. 技术选型与理由（必须使用对比分析表格）\n"
        "| 技术方案 | 优点 | 缺点 | 选择理由 |\n"
        "|----------|------|------|----------|\n"
        "| [选用技术] | ... | ... | ✓ 选择，因为... |\n"
        "| [备选方案1] | ... | ... | ✗ 未选择，因为... |\n"
        "| [备选方案2] | ... | ... | ✗ 未选择，因为... |\n"
        "若材料未提供对比分析，备选方案可基于技术知识合理补充，但标注[基于技术调研推断]\n"
        "2. 系统架构设计（必须使用Mermaid架构图，若细节不足需标注[基于技术栈推断的架构设计]）\n"
        "3. 数据流与交互逻辑（Mermaid流程图或时序图）\n"
        "4. 接口规范：若无代码信息，写“接口规范[待补充：详细API定义]”\n"
        "仅输出内容，不要输出标题。"
    ),
    "implementation": (
        "生成实现与迭代章节，使用CAIR结构：\n"
        "1. 开发环境与工具链：基于tech_stack与代码信息\n"
        "2. 核心模块实现：每个模块使用表格\n"
        "| 维度 | 描述 |\n"
        "|------|------|\n"
        "| 挑战(Challenge) | [待补充或材料信息] |\n"
        "| 思路(Approach) | ... |\n"
        "| 实现(Implementation) | ... |\n"
        "| 结果(Result) | [provided_metrics或待补充] |\n"
        "3. 关键技术挑战与解决方案：基于challenges_mentioned，缺失则输出待补充\n"
        "4. 版本迭代记录（表格）\n"
        "| 版本 | 主要变更 | 变更原因 |\n"
        "|------|----------|----------|\n"
        "| v0.1 | 初始原型 | 验证核心功能可行性 |\n"
        "| v1.0 | [待补充] | [待补充] |\n"
        "仅输出内容，不要输出标题。"
    ),
    "testing": (
        "生成测试与验证章节：\n"
        "1. 测试策略说明\n"
        "2. 测试用例与执行结果（表格，实际结果缺失必须写[待补充]）\n"
        "| 测试类别 | 测试用例 | 预期结果 | 实际结果 |\n"
        "|----------|----------|----------|----------|\n"
        "| 功能测试 | ... | ... | [待补充] |\n"
        "| 性能测试 | ... | ... | [待补充] |\n"
        "3. 性能基准测试：provided_metrics有数据则引用，否则写待补充\n"
        "4. 用户测试反馈：缺失则写“用户测试反馈[待补充：实际用户体验和建议]”\n"
        "仅输出内容，不要输出标题。"
    ),
    "reflection": (
        "生成反思与展望章节：\n"
        "1. 工程经验总结\n"
        "2. 技术债务与已知限制：基于missing_info与evidence_level\n"
        "3. 未来改进方向：可基于技术栈提出合理建议\n"
        "仅输出内容，不要输出标题。"
    ),
    "appendix": (
        "生成附录章节：\n"
        "1. 附录A：代码仓库链接，未提供则写[待补充：GitHub/GitLab链接]\n"
        "2. 附录B：关键代码片段，未提供则输出占位模板\n"
        "3. 附录C：原始数据样本，未提供则写[待补充]\n"
        "4. 附录D：参考文献列表，使用真实官方链接或[待补充]\n"
        "仅输出内容，不要输出标题。"
    ),
}


class HandbookAgent:
    def __init__(self):
        self.client = DeepSeekClient()
        self.sections = list(SECTION_TITLES.keys())

    def generate_handbook(
        self,
        project_description,
        system_type,
        project_name_cn,
        project_name_en=None,
        author_name=None,
        version=None,
        completion_date=None,
        source_code_url=None,
        source_code_file=None,
        process_materials=None,
    ):
        system_style = SYSTEM_STYLES.get(system_type, SYSTEM_STYLES["US"])
        analysis = self._analyze_materials(
            project_description=project_description,
            project_name_cn=project_name_cn,
            project_name_en=project_name_en,
            author_name=author_name,
            version=version,
            completion_date=completion_date,
            system_type=system_type,
            source_code_url=source_code_url,
            source_code_file=source_code_file,
            process_materials=process_materials,
        )
        material_feedback = self._check_material_sufficiency(analysis)
        analysis["material_feedback"] = material_feedback

        sections_content = {}
        for section in self.sections:
            sections_content[section] = self._generate_section(
                section_key=section,
                analysis=analysis,
                system_style=system_style,
                system_type=system_type,
            )

        content = self._assemble_handbook(
            project_name_cn=project_name_cn,
            system_type=system_type,
            sections_content=sections_content,
        )
        quality_issues = self._post_generation_check(content, system_type)
        return {
            "content": content,
            "meta": {
                "material_feedback": material_feedback,
                "post_generation_issues": quality_issues,
                "evidence_level": analysis.get("evidence_level", "low"),
                "missing_info": analysis.get("missing_info", []),
            },
        }

    def _analyze_materials(
        self,
        project_description,
        project_name_cn,
        project_name_en=None,
        author_name=None,
        version=None,
        completion_date=None,
        system_type=None,
        source_code_url=None,
        source_code_file=None,
        process_materials=None,
    ):
        trimmed_description = self._trim_text(project_description, max_chars=6000)
        code_text = self._read_text_file(source_code_file, max_chars=4000)
        materials_text = self._read_materials(process_materials, max_chars=4000)

        system_prompt = (
            "你是工程文档分析专家。请严格基于用户提供的材料进行分析，遵循以下原则：\n"
            "【信息提取原则】\n"
            "1. 只提取材料中明确提及的信息，绝对不要推测或虚构具体细节\n"
            "2. 对于每个字段，如果材料中没有明确提及，填写“未提供”或空数组\n"
            "3. 识别并列出材料中缺少的关键信息\n"
            "【输出JSON格式】\n"
            "{\n"
            "  \"problem_statement\": \"问题陈述（未提及则填'未提供'）\",\n"
            "  \"target_users\": \"目标用户群体\",\n"
            "  \"solution_summary\": \"解决方案概述\",\n"
            "  \"tech_stack\": [\"技术1\", \"技术2\"],\n"
            "  \"provided_metrics\": [\"材料中明确提供的量化指标\"],\n"
            "  \"challenges_mentioned\": [\"材料中明确提到的挑战\"],\n"
            "  \"code_highlights\": [\"从代码中提取的关键实现点\"],\n"
            "  \"missing_info\": [\"缺少具体测试数据\", \"缺少技术对比分析\"],\n"
            "  \"evidence_level\": \"high/medium/low\",\n"
            "  \"raw_keywords\": [\"关键词1\", \"关键词2\"]\n"
            "}\n"
            "【重要】evidence_level 判断标准：\n"
            "- high: 有详细项目说明 + 源代码 + 过程材料\n"
            "- medium: 有项目说明但缺少代码或细节\n"
            "- low: 只有简单描述或关键词\n"
        )
        completion_text = completion_date.isoformat() if completion_date else ""
        user_content = (
            f"项目名称: {project_name_cn}\n"
            f"项目英文名: {project_name_en or ''}\n"
            f"作者: {author_name or ''}\n"
            f"版本号: {version or ''}\n"
            f"完成日期: {completion_text}\n"
            f"体系版本: {system_type or ''}\n"
            f"项目说明:\n{trimmed_description}\n\n"
            f"源码链接: {source_code_url or ''}\n"
            f"代码片段:\n{code_text}\n\n"
            f"过程材料:\n{materials_text}\n"
        )
        response = self.client.generate_chat(
            system_prompt, user_content, temperature=0.4, enable_thinking=True
        )
        analysis = self._parse_json_response(response)
        if not analysis:
            analysis = {}
        analysis = self._normalize_analysis(analysis)
        analysis.update(
            {
                "project_name_cn": project_name_cn,
                "project_name_en": project_name_en or "",
                "author_name": author_name or "",
                "version": version or "v1.0.0",
                "completion_date": completion_text,
                "system_type": system_type or "",
                "source_code_url": source_code_url or "",
                "document_id": self._build_document_id(
                    project_name_cn, system_type, completion_date, version
                ),
            }
        )
        return analysis

    def _generate_section(self, section_key, analysis, system_style, system_type):
        base_prompt = BASE_SECTION_PROMPTS.get(section_key, "")
        weight_hint = SYSTEM_SECTION_WEIGHTS.get(system_type, {}).get(section_key, "标准")
        system_prompt = (
            "你是专业工程手册撰写专家。请基于给定分析信息撰写指定章节，"
            "使用中文，内容严谨具体。"
            f"\n{system_style}"
        )
        user_content = (
            f"章节: {SECTION_TITLES.get(section_key, section_key)}\n"
            f"分析信息(JSON):\n{json.dumps(analysis, ensure_ascii=False)}\n"
            f"章节权重建议: {weight_hint}\n"
            f"{COMMON_SECTION_CONSTRAINTS}\n"
            f"写作要求: {base_prompt}\n"
        )
        response = self.client.generate_chat(
            system_prompt, user_content, temperature=0.6, enable_thinking=True
        )
        return (response or "").strip()

    def _assemble_handbook(self, project_name_cn, system_type, sections_content):
        title = f"# 工程手册: {project_name_cn} ({system_type})"
        toc = ["## 目录"]
        for key in self.sections:
            toc.append(f"- {SECTION_TITLES.get(key, key)}")

        body = []
        for key in self.sections:
            section_title = SECTION_TITLES.get(key, key)
            body.append(f"## {section_title}")
            body.append(sections_content.get(key, "").strip())

        content = "\n\n".join([title, "\n".join(toc)] + body).strip() + "\n"
        return self._sanitize_markdown(content)

    def _read_materials(self, materials, max_chars=2000):
        if not materials:
            return ""
        paths = []
        if isinstance(materials, str):
            try:
                parsed = json.loads(materials)
                if isinstance(parsed, list):
                    paths = parsed
            except Exception:
                paths = [materials]
        elif isinstance(materials, list):
            paths = materials

        collected = []
        for path in paths:
            if not path:
                continue
            text = self._read_text_file(path, max_chars=max_chars)
            if text:
                collected.append(text)
        return "\n\n".join(collected)

    def _read_text_file(self, path, max_chars=2000):
        if not path or not os.path.exists(path):
            return ""
        try:
            with open(path, "r", encoding="utf-8", errors="ignore") as handle:
                content = handle.read(max_chars)
            return content
        except Exception:
            return ""

    def _trim_text(self, text, max_chars=4000):
        if not text:
            return ""
        content = text.strip()
        if len(content) <= max_chars:
            return content
        return content[:max_chars] + "\n...(已截断)"

    def _parse_json_response(self, raw_text):
        if not raw_text:
            return None
        cleaned = raw_text.replace("```json", "").replace("```", "").strip()
        sanitized = self._sanitize_json(cleaned)
        try:
            return json.loads(sanitized)
        except Exception:
            return None

    def _sanitize_json(self, raw_text):
        sanitized = []
        in_string = False
        escape = False
        for ch in raw_text:
            if escape:
                sanitized.append(ch)
                escape = False
                continue
            if ch == "\\":
                sanitized.append(ch)
                escape = True
                continue
            if ch == '"':
                in_string = not in_string
                sanitized.append(ch)
                continue
            if in_string and ch in ("\n", "\r", "\t"):
                if ch == "\n":
                    sanitized.append("\\n")
                elif ch == "\r":
                    sanitized.append("\\r")
                else:
                    sanitized.append("\\t")
                continue
            sanitized.append(ch)
        return "".join(sanitized)

    def _normalize_analysis(self, analysis):
        normalized = dict(analysis)
        normalized.setdefault("problem_statement", "未提供")
        normalized.setdefault("target_users", "未提供")
        normalized.setdefault("solution_summary", "未提供")
        normalized.setdefault("tech_stack", [])
        normalized.setdefault("provided_metrics", [])
        normalized.setdefault("challenges_mentioned", [])
        normalized.setdefault("code_highlights", [])
        normalized.setdefault("missing_info", [])
        normalized.setdefault("evidence_level", "low")
        normalized.setdefault("raw_keywords", [])

        normalized["tech_stack"] = self._normalize_list_field(normalized.get("tech_stack"))
        normalized["provided_metrics"] = self._normalize_list_field(
            normalized.get("provided_metrics")
        )
        normalized["challenges_mentioned"] = self._normalize_list_field(
            normalized.get("challenges_mentioned")
        )
        normalized["code_highlights"] = self._normalize_list_field(
            normalized.get("code_highlights")
        )
        normalized["missing_info"] = self._normalize_list_field(
            normalized.get("missing_info")
        )
        normalized["raw_keywords"] = self._normalize_list_field(
            normalized.get("raw_keywords")
        )
        return normalized

    def _build_document_id(self, project_name_cn, system_type, completion_date, version):
        date_part = completion_date.strftime("%Y%m%d") if completion_date else "TBD"
        base = f"{project_name_cn}-{system_type}-{version or 'v1.0.0'}"
        digest = hashlib.sha1(base.encode("utf-8")).hexdigest()[:6]
        return f"EH-{system_type or 'GEN'}-{date_part}-{digest}"

    def _check_material_sufficiency(self, analysis):
        evidence_level = analysis.get("evidence_level", "low")
        missing_info = analysis.get("missing_info", [])
        feedback = {
            "level": evidence_level,
            "can_proceed": True,
            "warnings": [],
            "suggestions": [],
        }

        if evidence_level == "low":
            feedback["warnings"].append(
                "输入材料较为简略，生成的文档将包含较多[待补充]占位符。"
            )
            feedback["suggestions"] = [
                "建议补充：详细的项目说明文档",
                "建议补充：关键代码片段",
                "建议补充：测试数据和结果",
                "建议补充：项目过程中遇到的挑战和解决方案",
            ]
        elif evidence_level == "medium":
            feedback["warnings"].append("部分信息缺失，相关章节将使用占位符。")
            feedback["suggestions"] = [
                f"建议补充：{item}" for item in missing_info[:3] if item
            ]

        return feedback

    def _post_generation_check(self, content, system_type):
        issues = []
        if not content:
            return issues

        placeholder_count = content.count("[待补充")
        if placeholder_count > 20:
            issues.append(
                f"文档中有{placeholder_count}处待补充内容，建议补充更多素材后重新生成。"
            )

        if system_type == "HK-SG" and "```mermaid" not in content.lower():
            issues.append("HK-SG版本建议包含Mermaid架构图或数据流图。")

        suspicious_patterns = [
            r"github\.com/[A-Z][a-z]+[A-Z][a-z]+/",
            r"\d{2}\.\d%",
        ]
        for pattern in suspicious_patterns:
            if re.search(pattern, content):
                issues.append("检测到疑似虚构内容模式，请复核。")
                break

        return issues

    def _sanitize_markdown(self, content):
        if not content:
            return content
        bullet_symbols = r"[●○◆◇★☆►▸•·→⇒※]"
        sanitized_lines = []
        for line in content.splitlines():
            stripped = line.lstrip()
            indent = line[: len(line) - len(stripped)]

            if re.match(rf"^{bullet_symbols}\s*#{1,6}\s+", stripped):
                stripped = re.sub(rf"^{bullet_symbols}\s*", "", stripped, count=1)
            elif re.match(rf"^{bullet_symbols}\s*\d+[.)]\s+", stripped):
                stripped = re.sub(rf"^{bullet_symbols}\s*", "", stripped, count=1)
            elif re.match(rf"^{bullet_symbols}\s+", stripped):
                stripped = re.sub(rf"^{bullet_symbols}\s+", "- ", stripped, count=1)

            sanitized_lines.append(indent + stripped)

        return "\n".join(sanitized_lines).rstrip() + "\n"

    def _normalize_list_field(self, value):
        if not value:
            return []
        if isinstance(value, list):
            return [item for item in value if item]
        if isinstance(value, str):
            if value.strip() in {"未提供", "无"}:
                return []
            return [value]
        return []
