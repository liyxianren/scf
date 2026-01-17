import json
import random
from utils.zhipu_client import ZhipuClient
from utils.deepseek_client import DeepSeekClient

# Pre-initialized clients (singleton pattern)
zhipu_client = ZhipuClient()
deepseek_client = DeepSeekClient()

class CreativeAgent:
    def __init__(self, model_provider="zhipu"):
        """
        Initialize CreativeAgent with a specific model provider.
        Args:
            model_provider: "zhipu" (default) or "deepseek"
        """
        # Always initialize both for mixed usage
        self.deepseek_client = deepseek_client
        self.zhipu_client = zhipu_client
        
        # Primary client for default actions
        if model_provider == "deepseek":
            self.client = deepseek_client
        else:
            self.client = zhipu_client
        
        self.model_provider = model_provider
        self.diversity_axes = [
            "技术手段（例如：语音交互/计算机视觉/推荐系统/知识图谱/IoT传感）",
            "应用场景（例如：校园/家庭/社区/城市/偏远地区）",
            "目标人群（例如：特殊教育/老年人/环保志愿者/青少年）",
            "商业模式（例如：订阅/公益/政府合作/企业SaaS）",
            "数据来源（例如：公开数据/传感器/用户生成内容/企业系统）",
            "交互方式（例如：移动端/桌面端/可穿戴设备/微信小程序）",
            "行业领域（例如：教育/环保/健康/金融/公益）",
        ]

    def analyze_input(
        self,
        keywords,
        student_profile,
        competition=None,
        extra_requirements=None,
        history_ideas=None,
        avoid_topics=None,
        feedback=None,
        enable_thinking=False,
    ):
        """
        Node 1: 需求拆解与扩充 (Input Analysis)
        Input: keywords (str), student_profile (str)
        Output: list of 3 directions (str)
        """
        diversity_seed = self._pick_diversity_seed()
        history_summary = self._format_history(history_ideas)
        avoid_summary = self._format_avoid_topics(avoid_topics)
        system_prompt = """
# Role
资深国际课程规划师，擅长将模糊的学生兴趣转化为具体的竞赛赛道。

# Task
用户提供了一些关键词和学生画像。
你的任务是扩展思路，不要局限于字面意思，给出 3 个**截然不同的赛道方向**（Direction）。
为了保证多样性，请严格按照以下三种形态进行拆解：
1. **工具类 (Tool/APP)**: 解决具体效率问题。
2. **平台/社区类 (Platform/Community)**: 解决连接与资源分配问题。
3. **硬件/IoT类 (Hardware/IoT)**: 解决物理世界交互问题（注意：需基于开源硬件，如Arduino/树莓派）。

# Constraints
- 方向必须具体，不能太宽泛。
- 三个方向的核心逻辑不能雷同（例如不能全是“拍照识别”）。
- 必须严格遵守用户的额外要求与目标赛事偏好。
- 必须显式体现关键词与学生画像中的特点。
- 避免与历史输出重复，如果发现高度相似必须替换为新方向。
- 必须避开以下主题或方向：{avoid_summary}
- 多样性锚点：{diversity_seed}
- 历史输出（避免重复）：{history_summary}
- 输出必须是合法的 JSON 格式。

# Output Format (JSON)
{{
  "directions": [
    "方向1 (工具类)：...",
    "方向2 (平台类)：...",
    "方向3 (硬件类)：..."
  ]
}}
"""
        user_content = (
            f"目标赛事：{competition or '未指定'}\n"
            f"关键词：{keywords}\n"
            f"学生画像：{student_profile}\n"
            f"额外要求：{extra_requirements or '无'}\n"
            f"用户修改建议：{feedback or '无'}"
        )
        
        try:
            print(f"--- Node 1 Agent Thinking (Deep Mode) ---\nInput: {user_content}")
        except Exception:
            pass # Ignore console print errors

        try:
            response = self.client.generate_chat(
                system_prompt.format(
                    diversity_seed=", ".join(diversity_seed),
                    history_summary=history_summary,
                    avoid_summary=avoid_summary,
                ),
                user_content,
                temperature=0.7,
                enable_thinking=enable_thinking,
            )
            
            if not response:
                print("Node 1: No response from LLM")
                return []
            
            # Robust JSON parsing
            cleaned_response = response.replace("```json", "").replace("```", "").strip()
            # Basic repair for common JSON errors if needed, but let's trust sanitize first
            sanitized = self._sanitize_json(cleaned_response)
            data = json.loads(sanitized)
            return data.get("directions", [])
            
        except Exception as e:
            try:
                print(f"Error in Node 1: {e}")
            except:
                pass
            return []

    def brainstorm(
        self,
        directions,
        keywords=None,
        student_profile=None,
        competition=None,
        extra_requirements=None,
        history_ideas=None,
        avoid_topics=None,
        feedback=None,
        enable_thinking=False,
    ):
        """
        Node 2: 头脑风暴 (Brainstorming) - Single Model Wrapper
        """
        return self._run_brainstorm_single(
            self.client, 
            directions, 
            keywords, 
            student_profile, 
            competition, 
            extra_requirements, 
            history_ideas, 
            avoid_topics, 
            feedback,
            enable_thinking
        )

    def brainstorm_dual(
        self,
        directions,
        keywords=None,
        student_profile=None,
        competition=None,
        extra_requirements=None,
        history_ideas=None,
        avoid_topics=None,
        feedback=None,
        enable_thinking=False,
    ):
        """
        Node 2: 头脑风暴 (Dual Model: DeepSeek + ChatGLM)
        Output: {'deepseek': [], 'chatglm': []}
        """
        print("--- Node 2 Dual Brainstorming ---")
        
        # Run DeepSeek
        print("Calling DeepSeek...")
        ds_ideas = self._run_brainstorm_single(
            self.deepseek_client,
            directions, keywords, student_profile, competition,
            extra_requirements, history_ideas, avoid_topics, feedback,
            enable_thinking
        )
        
        # Run ChatGLM
        print("Calling ChatGLM...")
        glm_ideas = self._run_brainstorm_single(
            self.zhipu_client,
            directions, keywords, student_profile, competition,
            extra_requirements, history_ideas, avoid_topics, feedback,
            enable_thinking
        )
        
        return {
            "deepseek": ds_ideas,
            "chatglm": glm_ideas
        }

    def brainstorm_dual_full(
        self,
        keywords,
        student_profile,
        competition=None,
        extra_requirements=None,
        history_ideas=None,
        avoid_topics=None,
        feedback=None,
        enable_thinking=False,
    ):
        """
        Full Pipeline: Node 1 + Node 2 for BOTH models.
        Output: {'chatglm': [6 projects], 'deepseek': [6 projects]}
        Each project is a dict: {name, slogan, pain_point, solution, tech_stack}
        """
        print("=== Dual-Model Full Pipeline ===")
        
        # ChatGLM Pipeline
        print("[ChatGLM] Running Node 1...")
        glm_directions = self._run_analyze(
            self.zhipu_client, keywords, student_profile, competition,
            extra_requirements, history_ideas, avoid_topics, feedback, enable_thinking
        )
        print(f"[ChatGLM] Directions: {len(glm_directions)}")
        
        print("[ChatGLM] Running Node 2...")
        glm_projects = self._run_brainstorm_structured(
            self.zhipu_client, glm_directions, keywords, student_profile, competition,
            extra_requirements, history_ideas, avoid_topics, feedback, enable_thinking
        )
        print(f"[ChatGLM] Projects: {len(glm_projects)}")
        
        # DeepSeek Pipeline
        print("[DeepSeek] Running Node 1...")
        ds_directions = self._run_analyze(
            self.deepseek_client, keywords, student_profile, competition,
            extra_requirements, history_ideas, avoid_topics, feedback, enable_thinking
        )
        print(f"[DeepSeek] Directions: {len(ds_directions)}")
        
        print("[DeepSeek] Running Node 2...")
        ds_projects = self._run_brainstorm_structured(
            self.deepseek_client, ds_directions, keywords, student_profile, competition,
            extra_requirements, history_ideas, avoid_topics, feedback, enable_thinking
        )
        print(f"[DeepSeek] Projects: {len(ds_projects)}")
        
        return {
            "chatglm": glm_projects,
            "deepseek": ds_projects
        }

    def _run_analyze(
        self, client, keywords, student_profile, competition,
        extra_requirements, history_ideas, avoid_topics, feedback, enable_thinking
    ):
        """Internal: Run Node 1 with a specific client."""
        diversity_seed = self._pick_diversity_seed()
        history_summary = self._format_history(history_ideas)
        avoid_summary = self._format_avoid_topics(avoid_topics)
        system_prompt = """
# Role
资深国际课程规划师，擅长将模糊的学生兴趣转化为具体的竞赛赛道。

# Task
给出 3 个**截然不同的赛道方向**（Direction）。
1. **工具类 (Tool/APP)**: 解决具体效率问题。
2. **平台/社区类 (Platform/Community)**: 解决连接与资源分配问题。
3. **硬件/IoT类 (Hardware/IoT)**: 解决物理世界交互问题。

# Constraints
- 方向必须具体。三个方向的核心逻辑不能雷同。
- 避开: {avoid_summary}
- 多样性锚点: {diversity_seed}
- 历史: {history_summary}

# Output Format (JSON)
{{ "directions": ["方向1: ...", "方向2: ...", "方向3: ..."] }}
"""
        user_content = (
            f"目标赛事：{competition or '未指定'}\n"
            f"关键词：{keywords}\n"
            f"学生画像：{student_profile}\n"
            f"额外要求：{extra_requirements or '无'}\n"
            f"用户修改建议：{feedback or '无'}"
        )
        try:
            response = client.generate_chat(
                system_prompt.format(
                    diversity_seed=", ".join(diversity_seed),
                    history_summary=history_summary,
                    avoid_summary=avoid_summary,
                ),
                user_content, temperature=0.7, enable_thinking=enable_thinking,
            )
            if not response: return []
            cleaned = response.replace("```json", "").replace("```", "").strip()
            data = json.loads(self._sanitize_json(cleaned))
            return data.get("directions", [])
        except Exception as e:
            print(f"Error in _run_analyze: {e}")
            return []

    def _run_brainstorm_structured(
        self, client, directions, keywords, student_profile, competition,
        extra_requirements, history_ideas, avoid_topics, feedback, enable_thinking
    ):
        """
        Structured Brainstorming: Outputs list of project dicts.
        Each project: {name, slogan, pain_point, solution, tech_stack}
        """
        if not directions:
            return []
        diversity_seed = self._pick_diversity_seed()
        history_summary = self._format_history(history_ideas)
        avoid_summary = self._format_avoid_topics(avoid_topics)
        system_prompt = """
# Role
专为竞赛学生服务的创意策划师，深知学生时间和资源有限，专注于可落地的创新项目。

# Task
基于给定的赛道方向，生成 6 个具体的项目创意。

# 核心约束 (必须严格遵守)
1. **学生可独立完成**: 项目必须是 1-3 个学生在 3-6 个月内可以独立完成的。禁止输出需要政府合作、企业API权限、特殊数据源的项目。
2. **严格遵循用户关键词**: 如果用户说"APP"，则只能输出手机APP或Web应用，禁止IoT硬件、嵌入式、传感器网络类项目。如果用户说"不做运营类"，则禁止论坛、社区、内容平台类项目。
3. **技术可行性**: 只使用公开API、开源库和学生可用的免费/低成本资源。禁止依赖卫星遥感、政府数据库等难以获取的数据源。
4. **多样性**: 6 个项目应使用不同的技术栈和解决不同的具体痛点。

# Guidelines
- 鼓励"微创新": 用现成的AI API（如ChatGPT API、视觉识别API）解决具体小问题。
- 避开: {avoid_summary}
- 多样性锚点: {diversity_seed}
- 历史: {history_summary}

# Output Format (JSON)
{{
  "projects": [
    {{
      "name": "项目名称 (商业化、朗朗上口)",
      "slogan": "一句打动评委的口号 (<15字)",
      "pain_point": "痛点描述 (为什么现在需要这个？)",
      "solution": "解决方案概述 (具体产品形态和核心功能，必须是学生可实现的，50-100字)",
      "tech_stack": "技术栈 (如：计算机视觉, Python, Flutter，必须是学生可用的)"
    }},
    ...共6个...
  ]
}}
"""
        user_content = (
            f"目标赛事：{competition or '未指定'}\n"
            f"关键词：{keywords or '未提供'}\n"
            f"学生画像：{student_profile or '未提供'}\n"
            f"额外要求：{extra_requirements or '无'}\n"
            f"用户修改建议：{feedback or '无'}\n"
            f"赛道方向列表：\n" + "\n".join(directions)
        )
        try:
            response = client.generate_chat(
                system_prompt.format(
                    diversity_seed=", ".join(diversity_seed),
                    history_summary=history_summary,
                    avoid_summary=avoid_summary,
                ),
                user_content, temperature=1.0, enable_thinking=enable_thinking,
            )
            if not response:
                print("[Brainstorm] Empty response from client")
                return []
            
            import re
            
            # Step 1: Basic cleanup
            cleaned = response.replace("```json", "").replace("```", "").strip()
            
            # Step 2: Try to find JSON object pattern
            json_match = re.search(r'\{[\s\S]*"projects"[\s\S]*\}', cleaned)
            if json_match:
                cleaned = json_match.group(0)
            
            # Step 3: Inline JSON sanitization
            # Remove trailing commas before ] or }
            cleaned = re.sub(r',\s*([}\]])', r'\1', cleaned)
            # Fix common issues: newlines in strings
            cleaned = re.sub(r'(?<!\\)\n', ' ', cleaned)
            # Remove control characters except newlines and tabs
            cleaned = re.sub(r'[\x00-\x08\x0b\x0c\x0e-\x1f\x7f-\x9f]', '', cleaned)
            
            # Step 4: Try to parse
            try:
                data = json.loads(cleaned)
                return data.get("projects", [])
            except json.JSONDecodeError as je:
                print(f"[Brainstorm] First parse attempt failed: {je}")
                
                # Step 5: Fallback - try to extract projects array directly
                projects_match = re.search(r'"projects"\s*:\s*\[[\s\S]*?\](?=\s*})', cleaned)
                if projects_match:
                    try:
                        projects_json = '{' + projects_match.group(0) + '}'
                        data = json.loads(projects_json)
                        return data.get("projects", [])
                    except:
                        pass
                
                print(f"[Brainstorm] All parse attempts failed")
                print(f"[Brainstorm] Cleaned JSON (first 1000 chars): {cleaned[:1000]}")
                return []
        except Exception as e:
            print(f"Error in _run_brainstorm_structured: {e}")
            import traceback
            traceback.print_exc()
            return []

    def _run_brainstorm_single(
        self,
        client,
        directions,
        keywords,
        student_profile,
        competition,
        extra_requirements,
        history_ideas,
        avoid_topics,
        feedback,
        enable_thinking,
    ):
        diversity_seed = self._pick_diversity_seed()
        history_summary = self._format_history(history_ideas)
        avoid_summary = self._format_avoid_topics(avoid_topics)
        system_prompt = """
# Role
硅谷创业公司的创意总监，思维活跃，擅长提出颠覆性的点子。

# Task
基于给定的 3 个赛道方向，分别生成 3 个具体的项目创意（共 9 个）。

# Guidelines
- 鼓励“微创新”，将现有技术应用在非传统领域。
- **强制多样性**: 绝对禁止所有创意都使用相同的技术（如“拍照识别”）。如果方向1用了图像识别，方向2和方向3必须使用其他技术（如语音交互、IoT传感、区块链、大数据分析等）。
- 每个创意必须包含：[项目名称] + 一句话描述（<20字）。
- 描述要吸引人，体现"新想法"。
- 必须与用户关键词、学生画像和额外要求强相关。
- 避免与历史输出重复，如果相似必须换成新创意。
- 必须避开以下主题或方向：{avoid_summary}
- 多样性锚点：{diversity_seed}
- 历史输出（避免重复）：{history_summary}

# Output Format (JSON)
{{
  "ideas": [
    "方向1-创意A: [名称] 描述...",
    "方向1-创意B: ...",
    ...
  ]
}}
"""
        user_content = (
            f"目标赛事：{competition or '未指定'}\n"
            f"关键词：{keywords or '未提供'}\n"
            f"学生画像：{student_profile or '未提供'}\n"
            f"额外要求：{extra_requirements or '无'}\n"
            f"用户修改建议：{feedback or '无'}\n"
            f"赛道方向列表：\n" + "\n".join(directions)
        )
        
        try:
            response = client.generate_chat(
                system_prompt.format(
                    diversity_seed=", ".join(diversity_seed),
                    history_summary=history_summary,
                    avoid_summary=avoid_summary,
                ),
                user_content,
                temperature=1.0,
                enable_thinking=enable_thinking,
            )
            
            if not response:
                return []

            cleaned_response = response.replace("```json", "").replace("```", "").strip()
            data = json.loads(self._sanitize_json(cleaned_response))
            return data.get("ideas", [])
        except Exception as e:
            try:
                print(f"Error in Brainstorm Single: {e}")
            except:
                pass
            return []

    def assess_feasibility(self, raw_ideas):
        """
        Node 3: 可行性评估 (Feasibility Assessor)
        Input: list of ideas (str)
        Output: list of selected ideas (str, Top 3)
        """
        system_prompt = """
# Role
SCF 公司的技术总监，负责评估高中生项目的落地可行性。

# Context
我们公司可以提供软件开发支持（APP/Web），但无法提供生物/化学湿实验环境。硬件开发仅限于开源硬件（Arduino/树莓派）。

# Task
对以下创意列表进行打分和筛选，选出 Top 3。

# Scoring Rules (CRITICAL)
1. **软件类 (纯APP/网站/数据分析)**: 
   - 可行性得分: 9-10分。
   - 评语: "开发可控，AI可辅助"。
2. **轻量级硬件类 (基于现有传感器/模块)**: 
   - 可行性得分: 6-8分。
   - 评语: "需评估硬件成本和调试难度"。
3. **重型硬件/工业制造 (如水下潜航器、大型无人机)**: 
   - 可行性得分: 0-4分。
   - 评语: "超出高中生能力，需工厂配合，不可行"。
4. **生物/化学/医学实验 (需实验室)**: 
   - 可行性得分: 0分。
   - 评语: "REJECT: 公司无实验室环境"。

# Constraints
- 必须严格遵守上述规则。
- 如果是纯软件创意，优先保留。

# Output Format (JSON)
{
  "selected_ideas": [
    "创意名1 (理由...)",
    "创意名2 (理由...)",
    "创意名3 (理由...)"
  ]
}
"""
        user_content = f"待评估创意列表：\n" + "\n".join(raw_ideas)
        
        try:
            print(f"--- Node 3 Agent Thinking ---\nInput Ideas: {len(raw_ideas)}")
        except:
            pass

        try:
            response = self.client.generate_chat(system_prompt, user_content, temperature=0.1) # Low temp for strict logic
            
            if not response:
                print("Node 3: No response from LLM")
                return []

            cleaned_response = response.replace("```json", "").replace("```", "").strip()
            data = json.loads(self._sanitize_json(cleaned_response))
            return data.get("selected_ideas", [])
        except Exception as e:
            try:
                print(f"Error in Node 3: {e}")
            except:
                pass
            return []

    def generate_report(
        self,
        selected_ideas,
        keywords=None,
        student_profile=None,
        competition=None,
        extra_requirements=None,
        history_ideas=None,
        avoid_topics=None,
        feedback=None,
        stream=False,
        enable_thinking=True, # Configurable
    ):
        """
        Node 4: 方案细化 (Detailing)
        Input: list of selected ideas (str)
        Output: Full Markdown Report (str)
        """
        history_summary = self._format_history(history_ideas)
        avoid_summary = self._format_avoid_topics(avoid_topics)
        system_prompt = """
# Role
专业的商业计划书撰写专家，擅长为学生竞赛项目撰写详细方案。

# Task
为用户选中的单个项目创意生成一份完整、详细的项目计划书。

# Requirement
生成以下内容（Markdown格式）：

## 1. 项目概述
- **项目名称**: 保持用户选中的名称
- **Slogan**: 简洁有力的口号
- **核心理念**: 一句话概括项目愿景

## 2. 问题与机遇
- **痛点分析 (Why Now)**: 详细描述目标用户面临的具体问题
- **市场机会**: 为什么现在是解决这个问题的好时机

## 3. 解决方案
- **产品形态**: APP/小程序/网页应用等
- **核心功能 (3-5 个)**: 每个功能的具体描述
- **技术创新点**: 与现有产品的差异化

## 4. 技术方案
- **技术栈**: 前端、后端、AI 等具体技术
- **AI 能力**: 如何使用 AI（如 API 调用、模型应用）
- **开发周期预估**: 3-6 个月的里程碑

## 5. 目标用户
- **用户画像**: 具体描述目标用户特征
- **使用场景**: 用户如何使用产品

## 6. 商业价值
- **价值主张**: 用户为什么会选择这个产品
- **可持续性**: 如何产生社会影响或商业价值

## 7. 竞赛优势
- **创新性**: 项目的创新亮点
- **可行性**: 学生团队可实现的理由
- **评委视角**: 为什么评委会喜欢这个项目

# Constraints
- 必须显式体现用户关键词、学生画像和额外要求
- 方案必须是学生可独立完成的（3-6 个月）
- 不得与历史输出重复
- 避开以下主题：{avoid_summary}
- 历史输出（避免重复）：{history_summary}

# Output Format
Direct Markdown. No JSON wrapping.
Start with title: "# 🚀 项目计划书: [项目名称]"
"""
        user_content = (
            f"目标赛事：{competition or '未指定'}\n"
            f"关键词：{keywords or '未提供'}\n"
            f"学生画像：{student_profile or '未提供'}\n"
            f"额外要求：{extra_requirements or '无'}\n"
            f"用户修改建议：{feedback or '无'}\n"
            f"入选创意列表：\n" + "\n".join(selected_ideas)
        )
        
        print(f"--- Node 4 Agent Thinking ---\nGenerating Report for {len(selected_ideas)} ideas")
        formatted_prompt = system_prompt.format(
            history_summary=history_summary,
            avoid_summary=avoid_summary,
        )
        if stream:
            return self.client.generate_chat_stream(
                formatted_prompt,
                user_content,
                temperature=0.7,
                enable_thinking=enable_thinking, 
            )

        return self.client.generate_chat(
            formatted_prompt,
            user_content,
            temperature=0.7,
            enable_thinking=enable_thinking,
        )

    def _pick_diversity_seed(self):
        return random.sample(self.diversity_axes, k=3)

    def _format_history(self, history_ideas):
        if not history_ideas:
            return "无"
        trimmed = history_ideas[:10]
        return "\n".join(f"- {idea}" for idea in trimmed)

    def _format_avoid_topics(self, avoid_topics):
        if not avoid_topics:
            return "无"
        trimmed = avoid_topics[:8]
        return "、".join(trimmed)

    def summarize_report(self, report, feedback=None):
        system_prompt = """
# Role
资深商业评审与课程顾问。

# Task
对给定的项目报告进行精炼总结，并提取应避免的主题方向。

# Requirements
- 输出 JSON，包含 summary 与 avoid_topics。
- summary 需包含整体主题和常见重复点。
- avoid_topics 要列出需要避开的方向（例如具体方案名称、核心机制、核心关键词）。
- 如果用户反馈中明确表达“不喜欢/要避免”的内容，必须加入 avoid_topics。

# Output Format (JSON)
{
  "summary": "简短总结...",
  "avoid_topics": ["主题A", "主题B", "主题C"]
}
"""
        user_content = (
            f"用户反馈：{feedback or '无'}\n"
            f"报告内容：\n{report}"
        )
        response = self.client.generate_chat(
            system_prompt,
            user_content,
            temperature=0.3,
        )
        try:
            cleaned_response = response.replace("```json", "").replace("```", "").strip()
            data = json.loads(self._sanitize_json(cleaned_response))
            return {
                "summary": data.get("summary", ""),
                "avoid_topics": data.get("avoid_topics", []),
            }
        except Exception as e:
            print(f"JSON Parse Error in Summary: {e}\nRaw Response: {response}")
            return {"summary": "", "avoid_topics": []}

    def _sanitize_json(self, raw_text):
        if not raw_text:
            return raw_text
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
