from flask import Blueprint, render_template, jsonify, request
from models import db, Agent, CreativeProject
from utils.ai_nodes import CreativeAgent

agent_bp = Blueprint('agent', __name__)

@agent_bp.route('/agents')
def list_agents():
    """Agent 展示大厅"""
    agents = Agent.query.all()
    return render_template('agents.html', agents=agents)

@agent_bp.route('/agents/<int:agent_id>')
def agent_detail(agent_id):
    """Agent 详情页"""
    agent = Agent.query.get_or_404(agent_id)
    return render_template('agent_detail.html', agent=agent)

@agent_bp.route('/api/agents')
def api_agents():
    """内部 API: 获取所有 Agent 数据"""
    agents = Agent.query.all()
    return jsonify([agent.to_dict() for agent in agents])

@agent_bp.route('/creative')
def creative_page():
    """创意生成器页面"""
    return render_template('creative_agent.html')

@agent_bp.route('/projects')
def project_gallery():
    """项目收藏夹"""
    projects = CreativeProject.query.order_by(CreativeProject.created_at.desc()).all()
    return render_template('creative_gallery.html', projects=projects)

@agent_bp.route('/projects', methods=['POST'])
def save_project():
    """保存项目"""
    data = request.json
    title = data.get('title', '未命名项目')
    content = data.get('content')
    slogan = data.get('slogan')
    tags = data.get('tags')
    
    if not content:
        return jsonify({'error': 'Content is required'}), 400
        
    project = CreativeProject(
        title=title,
        full_content=content,
        slogan=slogan,
        tags=tags
    )
    db.session.add(project)
    db.session.commit()
    
    return jsonify({'message': 'Saved successfully', 'id': project.id})

@agent_bp.route('/creative/generate', methods=['POST'])
def generate_creative_project():
    """处理创意生成请求"""
    data = request.json
    keywords = data.get('keywords')
    student_profile = data.get('studentProfile')
    
    if not keywords:
        return jsonify({'error': 'Keywords are required'}), 400
        
    agent = CreativeAgent()
    
    # Step 1: Input Analysis
    directions = agent.analyze_input(keywords, student_profile)
    
    # Step 2: Brainstorming
    ideas = agent.brainstorm(directions)
    
    # Step 3: Feasibility Check
    selected_ideas = agent.assess_feasibility(ideas)
    
    
    # Step 4: Detailing (Final Report)
    report = agent.generate_report(selected_ideas)
    
    return jsonify({'report': report})

@agent_bp.route('/creative/chat', methods=['POST'])
def chat_refinement():
    """处理后续对话/优化请求"""
    data = request.json
    user_message = data.get('message')
    context_report = data.get('context') # The full generated report
    
    if not user_message:
        return jsonify({'error': 'Message is required'}), 400
        
    client = CreativeAgent().client
    
    system_prompt = """
# Role
即兴创意顾问 & 商业分析师。

# Context
你之前已经为用户生成了一份包含 3 个项目的方案报告（见下文）。
用户现在对方案有反馈，或者希望深入探讨其中某个项目。

# Task
根据用户的反馈进行回答。
- 如果用户要求**修改**、**变动**或**重写**某个项目的具体内容，请务必输出**完整的、修改后的 Markdown 报告**，以便用户直接保存。不要只输出修改的部分。
- 如果用户只是询问问题，正常回答即可。
- 保持专业、鼓励性和建设性。

# Previous Report Content
{context}
    """.format(context=context_report)
    
    # Enable Thinking for chat as well to ensure high quality replies
    response = client.generate_chat(system_prompt, user_message, temperature=0.8, enable_thinking=True)
    
@agent_bp.route('/projects/<int:project_id>', methods=['DELETE'])
def delete_project(project_id):
    """删除项目"""
    project = CreativeProject.query.get_or_404(project_id)
    db.session.delete(project)
    db.session.commit()
    return jsonify({'message': 'Deleted successfully'})


