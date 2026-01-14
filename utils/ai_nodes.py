import json
import random
from utils.zhipu_client import ZhipuClient

client = ZhipuClient()

class CreativeAgent:
    def __init__(self):
        self.client = client
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
        
        print(f"--- Node 1 Agent Thinking (Deep Mode) ---\nInput: {user_content}")
        response = self.client.generate_chat(
            system_prompt.format(
                diversity_seed=", ".join(diversity_seed),
                history_summary=history_summary,
                avoid_summary=avoid_summary,
            ),
            user_content,
            enable_thinking=True,
            temperature=0.9,
        )
        
        # Simple JSON parsing (robustness can be improved later)
        try:
            # Handle potential markdown code blocks in response
            cleaned_response = response.replace("```json", "").replace("```", "").strip()
            data = json.loads(cleaned_response)
            return data.get("directions", [])
        except Exception as e:
            print(f"JSON Parse Error in Node 1: {e}\nRaw Response: {response}")
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
    ):
        """
        Node 2: 头脑风暴 (Brainstorming)
        Input: list of directions (str)
        Output: list of ideas (str)
        """
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
        
        print(f"--- Node 2 Agent Thinking (Deep Mode) ---\nInput Directions: {len(directions)} directions")
        response = self.client.generate_chat(
            system_prompt.format(
                diversity_seed=", ".join(diversity_seed),
                history_summary=history_summary,
                avoid_summary=avoid_summary,
            ),
            user_content,
            temperature=1.0,
            enable_thinking=True,
        )
        
        try:
            cleaned_response = response.replace("```json", "").replace("```", "").strip()
            data = json.loads(cleaned_response)
            return data.get("ideas", [])
        except Exception as e:
            print(f"JSON Parse Error in Node 2: {e}\nRaw Response: {response}")
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
        
        print(f"--- Node 3 Agent Thinking ---\nInput Ideas: {len(raw_ideas)}")
        response = self.client.generate_chat(system_prompt, user_content, temperature=0.1) # Low temp for strict logic
        
        try:
            cleaned_response = response.replace("```json", "").replace("```", "").strip()
            data = json.loads(cleaned_response)
            return data.get("selected_ideas", [])
        except Exception as e:
            print(f"JSON Parse Error in Node 3: {e}\nRaw Response: {response}")
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
商业计划书撰写专家。

# Task
将以下 3 个入选创意包装成专业的项目提案。

# Requirement
针对每个创意，生成以下内容（Markdown格式）：
1. **项目名称**: 商业化、朗朗上口的名字。
2. **Slogan**: 一句打动评委的口号。
3. **痛点 (Why Now)**: 为什么现在需要这个东西？
4. **解决方案 (Product)**: 具体是个APP还是什么？核心功能有哪3点？
5. **技术栈 (Tech)**: 比如 "Python + Flutter + ChatGLM API"。
6. **商业价值**: 怎么赚钱或产生社会影响力？
- 必须显式体现用户关键词、学生画像和额外要求。
- 不得与历史输出重复；如相似必须改写为全新方案。
- 必须避开以下主题或方向：{avoid_summary}
- 历史输出（避免重复）：{history_summary}

# Output Format
Direct Markdown. No JSON wrapping.
Start with a title: "# 🚀 推荐项目方案"
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
                enable_thinking=True,
            )

        return self.client.generate_chat(
            formatted_prompt,
            user_content,
            temperature=0.7,
            enable_thinking=True,
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
            data = json.loads(cleaned_response)
            return {
                "summary": data.get("summary", ""),
                "avoid_topics": data.get("avoid_topics", []),
            }
        except Exception as e:
            print(f"JSON Parse Error in Summary: {e}\nRaw Response: {response}")
            return {"summary": "", "avoid_topics": []}
