from flask import render_template, jsonify, request, Response, stream_with_context, send_file, current_app
import json
from datetime import datetime, timedelta
from concurrent.futures import ThreadPoolExecutor, as_completed
from extensions import db
from modules.agents.models import Agent, CreativeProject, ProjectPlan
from modules.agents.services import CreativeAgent
from core.tasks import TaskRunner
import io

from modules.agents import agent_bp

def _ensure_default_agents():
    defaults = [
        {
            "name": "工程手册 Agent",
            "description": "面向留学申请的工程手册生成助手，支持多体系版本与结构化输出。",
            "icon": "menu_book",
            "status": "active",
        }
    ]
    created = False
    for data in defaults:
        if not Agent.query.filter_by(name=data["name"]).first():
            db.session.add(Agent(**data))
            created = True
    if created:
        db.session.commit()

@agent_bp.route('/agents')
def list_agents():
    """Agent 展示大厅"""
    _ensure_default_agents()
    agents = Agent.query.all()
    return render_template('agents/agents.html', agents=agents)

@agent_bp.route('/agents/<int:agent_id>')
def agent_detail(agent_id):
    """Agent 详情页"""
    agent = Agent.query.get_or_404(agent_id)
    return render_template('agents/agent_detail.html', agent=agent)

@agent_bp.route('/api/agents')
def api_agents():
    """内部 API: 获取所有 Agent 数据"""
    _ensure_default_agents()
    agents = Agent.query.all()
    return jsonify([agent.to_dict() for agent in agents])

@agent_bp.route('/creative')
def creative_page():
    """创意生成器页面"""
    return render_template('agents/creative_agent.html')

@agent_bp.route('/projects')
def project_gallery():
    """项目收藏夹"""
    projects = CreativeProject.query.order_by(CreativeProject.created_at.desc()).all()
    return render_template('agents/creative_gallery.html', projects=projects)

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

@agent_bp.route('/creative/stage1', methods=['POST'])
def creative_stage1():
    """Stage 1: Full Pipeline (Node 1 + Node 2) for BOTH models. Returns 12 structured projects."""
    data = request.json
    keywords = data.get('keywords')
    student_profile = data.get('studentProfile')
    competition = data.get('competition')
    extra_requirements = data.get('extraReq')
    history_ideas = data.get('historyIdeas', [])
    avoid_topics = data.get('avoidTopics', [])
    feedback = data.get('feedback')

    if not keywords:
        return jsonify({'error': 'Keywords are required'}), 400

    agent = CreativeAgent()

    # Run Full Pipeline for BOTH Models
    projects_map = agent.brainstorm_dual_full(
        keywords, student_profile, competition,
        extra_requirements, history_ideas, avoid_topics, feedback,
        enable_thinking=False
    )

    return jsonify({
        'projects': projects_map  # {'chatglm': [...], 'deepseek': [...]}
    })

@agent_bp.route('/creative/stage2', methods=['POST'])
def creative_stage2():
    """Stage 2: Feasibility + Detailing (Stream, with Thinking)"""
    data = request.json
    selected_ideas = data.get('selectedIdeas', []) # List of strings
    keywords = data.get('keywords')
    student_profile = data.get('studentProfile')
    competition = data.get('competition')
    extra_requirements = data.get('extraReq')
    history_ideas = data.get('historyIdeas', [])
    avoid_topics = data.get('avoidTopics', [])
    feedback = data.get('feedback')
    model_provider = data.get('modelProvider', 'zhipu')

    if not selected_ideas:
        return jsonify({'error': 'Selected ideas are required'}), 400

    def generate():
        agent = CreativeAgent(model_provider=model_provider)

        # Step 3: Feasibility Check (Thinking=False, usually fast)
        yield json.dumps({"type": "status", "message": "⚖️ 正在评估技术可行性 & 筛选 Top 3..."}) + "\n"
        final_selected = agent.assess_feasibility(selected_ideas)

        if not final_selected:
            yield json.dumps({"type": "error", "message": "❌ 可行性评估失败，请稍后重试。"}) + "\n"
            return

        # Step 4: Detailing (Thinking=True, DeepSeek-R1)
        yield json.dumps({"type": "status", "message": "📝 正在深度思考并撰写方案 (DeepSeek-R1)..."}) + "\n"
        report_stream = agent.generate_report(
            final_selected,
            keywords, student_profile, competition,
            extra_requirements, history_ideas, avoid_topics, feedback,
            stream=True,
            enable_thinking=True # Enable Deep Thinking here
        )

        if report_stream is None:
             yield json.dumps({"type": "error", "message": "❌ 报告生成服务无响应。"}) + "\n"
             return

        for chunk in report_stream:
            if chunk:
                if isinstance(chunk, dict):
                    if chunk.get("type") == "thinking":
                        yield json.dumps({"type": "thinking_delta", "content": chunk["content"]}) + "\n"
                    elif chunk.get("type") == "content":
                        yield json.dumps({"type": "delta", "content": chunk["content"]}) + "\n"
                else:
                    yield json.dumps({"type": "delta", "content": str(chunk)}) + "\n"

    headers = {
        'Cache-Control': 'no-cache',
        'X-Accel-Buffering': 'no',
        'Content-Type': 'application/x-ndjson'
    }
    return Response(stream_with_context(generate()), headers=headers)


# ========== 后台计划书生成系统 ==========

def _generate_plan_background(plan_id, project_data, request_context):
    """后台线程：为单个计划书生成内容"""
    plan = ProjectPlan.query.get(plan_id)
    if not plan:
        return

    try:
        plan.status = 'generating'
        db.session.commit()

        agent = CreativeAgent(model_provider='deepseek')

        # Format project info for generate_report
        project_info = f"""项目名称: {project_data.get('name', 'Unknown')}
口号: {project_data.get('slogan', '')}
痛点: {project_data.get('pain_point', '')}
解决方案: {project_data.get('solution', '')}
技术栈: {project_data.get('tech_stack', '')}"""

        content = agent.generate_report(
            [project_info],
            keywords=request_context.get('keywords'),
            student_profile=request_context.get('studentProfile'),
            competition=request_context.get('competition'),
            extra_requirements=request_context.get('extraReq'),
            stream=False,
            enable_thinking=True
        )

        plan.content = content
        plan.status = 'completed'
        plan.completed_at = datetime.utcnow()
        db.session.commit()
        print(f"[Background] Plan {plan_id} generated successfully")

    except Exception as e:
        plan.status = 'failed'
        plan.error_message = str(e)
        db.session.commit()
        print(f"[Background] Plan {plan_id} failed: {e}")


@agent_bp.route('/creative/generate_plans', methods=['POST'])
def generate_multiple_plans():
    """提交后台计划书生成任务，立即返回"""
    data = request.json
    selected_projects = data.get('selectedProjects', [])

    if not selected_projects:
        return jsonify({'error': 'No projects selected'}), 400

    # 保存请求上下文
    request_context = {
        'keywords': data.get('keywords'),
        'studentProfile': data.get('studentProfile'),
        'competition': data.get('competition'),
        'extraReq': data.get('extraReq')
    }

    created_plans = []

    for project in selected_projects:
        # 创建待处理的计划书记录
        plan = ProjectPlan(
            project_name=project.get('name', '未命名项目'),
            slogan=project.get('slogan', ''),
            status='pending',
            source_project_data=json.dumps(project),
            request_context=json.dumps(request_context),
            expires_at=datetime.utcnow() + timedelta(days=3)
        )
        db.session.add(plan)
        db.session.commit()

        created_plans.append({
            'id': plan.id,
            'project_name': plan.project_name
        })

        # 启动后台任务
        TaskRunner.run_async(_generate_plan_background, plan.id, project, request_context)

    return jsonify({
        'message': f'已开始生成 {len(created_plans)} 个计划书',
        'plans': created_plans
    })


@agent_bp.route('/plans')
def plans_page():
    """计划书管理页面"""
    return render_template('agents/plans.html')


@agent_bp.route('/api/plans')
def api_list_plans():
    """API: 获取所有计划书"""
    plans = ProjectPlan.query.order_by(ProjectPlan.created_at.desc()).all()
    return jsonify([p.to_dict() for p in plans])


@agent_bp.route('/api/plans/<int:plan_id>')
def api_get_plan(plan_id):
    """API: 获取单个计划书详情"""
    plan = ProjectPlan.query.get_or_404(plan_id)
    return jsonify(plan.to_dict())


@agent_bp.route('/api/plans/<int:plan_id>', methods=['PUT'])
def api_update_plan(plan_id):
    """API: 更新计划书内容"""
    plan = ProjectPlan.query.get_or_404(plan_id)
    data = request.json

    if 'content' in data:
        plan.content = data['content']
    if 'project_name' in data:
        plan.project_name = data['project_name']

    db.session.commit()
    return jsonify({'message': 'Updated successfully', 'plan': plan.to_dict()})


@agent_bp.route('/api/plans/<int:plan_id>', methods=['DELETE'])
def api_delete_plan(plan_id):
    """API: 删除计划书"""
    plan = ProjectPlan.query.get_or_404(plan_id)
    db.session.delete(plan)
    db.session.commit()
    return jsonify({'message': 'Deleted successfully'})


@agent_bp.route('/api/plans/<int:plan_id>/favorite', methods=['POST'])
def api_toggle_favorite(plan_id):
    """API: 切换收藏状态"""
    plan = ProjectPlan.query.get_or_404(plan_id)
    plan.is_favorited = not plan.is_favorited

    # 收藏后取消过期时间，取消收藏后重新设置3天过期
    if plan.is_favorited:
        plan.expires_at = None
    else:
        plan.expires_at = datetime.utcnow() + timedelta(days=3)

    db.session.commit()
    return jsonify({
        'message': '已收藏' if plan.is_favorited else '已取消收藏',
        'is_favorited': plan.is_favorited
    })


@agent_bp.route('/api/plans/<int:plan_id>/download')
def api_download_plan(plan_id):
    """API: 下载计划书为 Markdown 文件"""
    plan = ProjectPlan.query.get_or_404(plan_id)

    if not plan.content:
        return jsonify({'error': 'Plan has no content'}), 400

    # 创建内存文件
    output = io.BytesIO()
    output.write(plan.content.encode('utf-8'))
    output.seek(0)

    filename = f"{plan.project_name}_计划书.md"

    return send_file(
        output,
        mimetype='text/markdown',
        as_attachment=True,
        download_name=filename
    )


@agent_bp.route('/api/plans/<int:plan_id>/regenerate', methods=['POST'])
def api_regenerate_plan(plan_id):
    """API: 重新生成计划书"""
    plan = ProjectPlan.query.get_or_404(plan_id)

    if plan.status == 'generating':
        return jsonify({'error': 'Plan is already being generated'}), 400

    # 重置状态
    plan.status = 'pending'
    plan.content = None
    plan.error_message = None
    plan.completed_at = None
    db.session.commit()

    # 重新启动生成任务
    project_data = json.loads(plan.source_project_data) if plan.source_project_data else {}
    request_context = json.loads(plan.request_context) if plan.request_context else {}

    TaskRunner.run_async(_generate_plan_background, plan.id, project_data, request_context)

    return jsonify({'message': '已开始重新生成', 'plan': plan.to_dict()})


# 保留旧路由以兼容
@agent_bp.route('/creative/plan_viewer')
def plan_viewer():
    """Redirect to new plans page."""
    from flask import redirect
    return redirect('/company/plans')




@agent_bp.route('/creative/generate', methods=['POST'])
def generate_creative_project():
    """(Legacy) 处理创意生成请求 - Updated to disable thinking by default"""
    data = request.json
    keywords = data.get('keywords')
    student_profile = data.get('studentProfile')
    competition = data.get('competition')
    extra_requirements = data.get('extraReq')
    history_ideas = data.get('historyIdeas', [])
    avoid_topics = data.get('avoidTopics', [])
    feedback = data.get('feedback')
    model_provider = data.get('modelProvider', 'zhipu')  # Default to zhipu

    if not keywords:
        return jsonify({'error': 'Keywords are required'}), 400

    agent = CreativeAgent(model_provider=model_provider)

    # Step 1: Input Analysis
    directions = agent.analyze_input(
        keywords,
        student_profile,
        competition=competition,
        extra_requirements=extra_requirements,
        history_ideas=history_ideas,
        avoid_topics=avoid_topics,
        feedback=feedback,
        enable_thinking=False
    )

    # Step 2: Brainstorming
    ideas = agent.brainstorm(
        directions,
        keywords=keywords,
        student_profile=student_profile,
        competition=competition,
        extra_requirements=extra_requirements,
        history_ideas=history_ideas,
        avoid_topics=avoid_topics,
        feedback=feedback,
        enable_thinking=False
    )

    # Step 3: Feasibility Check
    selected_ideas = agent.assess_feasibility(ideas)


    # Step 4: Detailing (Final Report)
    report = agent.generate_report(
        selected_ideas,
        keywords=keywords,
        student_profile=student_profile,
        competition=competition,
        extra_requirements=extra_requirements,
        history_ideas=history_ideas,
        avoid_topics=avoid_topics,
        feedback=feedback,
        enable_thinking=False # Disable for legacy fast mode
    )

    return jsonify({'report': report})

@agent_bp.route('/creative/generate/stream', methods=['POST'])
def generate_creative_project_stream():
    """流式输出创意生成报告 (NDJSON 格式: {type: 'status'|'delta', ...})"""
    data = request.json
    keywords = data.get('keywords')
    student_profile = data.get('studentProfile')
    competition = data.get('competition')
    extra_requirements = data.get('extraReq')
    history_ideas = data.get('historyIdeas', [])
    avoid_topics = data.get('avoidTopics', [])
    feedback = data.get('feedback')
    model_provider = data.get('modelProvider', 'zhipu')  # Default to zhipu

    if not keywords:
        return jsonify({'error': 'Keywords are required'}), 400

    def generate():
        agent = CreativeAgent(model_provider=model_provider)

        # --- Node 1: Input Analysis ---
        yield json.dumps({"type": "status", "message": "🔍 正在分析用户需求与画像..."}) + "\n"
        directions = agent.analyze_input(
            keywords,
            student_profile,
            competition=competition,
            extra_requirements=extra_requirements,
            history_ideas=history_ideas,
            avoid_topics=avoid_topics,
            feedback=feedback,
        )
        if not directions:
            yield json.dumps({"type": "error", "message": "❌ 需求分析失败，请稍后重试。"}) + "\n"
            return

        # --- Node 2: Brainstorming ---
        yield json.dumps({"type": "status", "message": "🧠 正在进行发散性头脑风暴..."}) + "\n"
        ideas = agent.brainstorm(
            directions,
            keywords=keywords,
            student_profile=student_profile,
            competition=competition,
            extra_requirements=extra_requirements,
            history_ideas=history_ideas,
            avoid_topics=avoid_topics,
            feedback=feedback,
        )
        if not ideas:
             yield json.dumps({"type": "error", "message": "❌ 创意生成失败，请稍后重试。"}) + "\n"
             return

        # --- Node 3: Feasibility Check ---
        yield json.dumps({"type": "status", "message": "⚖️ visible 正在评估技术可行性 & 筛选 Top 3..."}) + "\n"
        selected_ideas = agent.assess_feasibility(ideas)
        if not selected_ideas:
             yield json.dumps({"type": "error", "message": "❌ 可行性评估失败，请稍后重试。"}) + "\n"
             return

        # --- Node 4: Detailing (Streamed) ---
        yield json.dumps({"type": "status", "message": "📝 正在撰写最终商业方案..."}) + "\n"
        report_stream = agent.generate_report(
            selected_ideas,
            keywords=keywords,
            student_profile=student_profile,
            competition=competition,
            extra_requirements=extra_requirements,
            history_ideas=history_ideas,
            avoid_topics=avoid_topics,
            feedback=feedback,
            stream=True,
        )

        if report_stream is None:
             yield json.dumps({"type": "error", "message": "❌ 报告生成服务无响应。"}) + "\n"
             return

        for chunk in report_stream:
            if chunk:
                # Chunk is now a dict: {"type": "thinking"|"content", "content": "..."}
                if isinstance(chunk, dict):
                    if chunk.get("type") == "thinking":
                        yield json.dumps({"type": "thinking_delta", "content": chunk["content"]}) + "\n"
                    elif chunk.get("type") == "content":
                        yield json.dumps({"type": "delta", "content": chunk["content"]}) + "\n"
                else:
                    # Fallback for legacy string chunks if any mixed usage
                    yield json.dumps({"type": "delta", "content": str(chunk)}) + "\n"

    headers = {
        'Cache-Control': 'no-cache',
        'X-Accel-Buffering': 'no',
        'Content-Type': 'application/x-ndjson'
    }
    return Response(stream_with_context(generate()), headers=headers)

@agent_bp.route('/creative/brainstorm', methods=['POST'])
def brainstorm_cycle():
    """处理头脑风暴循环请求 (流式输出)"""
    data = request.json
    keywords = data.get('keywords')
    student_profile = data.get('studentProfile')
    competition = data.get('competition')
    extra_requirements = data.get('extraReq')
    history_ideas = data.get('historyIdeas', [])
    feedback = data.get('feedback')
    previous_report = data.get('previousReport')
    avoid_topics = data.get('avoidTopics', [])
    model_provider = data.get('modelProvider', 'zhipu')  # Default to zhipu

    if not keywords:
        return jsonify({'error': 'Keywords are required'}), 400

    def generate():
        agent = CreativeAgent(model_provider=model_provider)
        summary_payload = None

        # Step 0: Summarize previous report if exists
        if previous_report:
            yield json.dumps({"type": "status", "message": "📝 正在总结上一轮报告..."}) + "\n"
            summary_payload = agent.summarize_report(previous_report, feedback=feedback)
            if summary_payload:
                nonlocal avoid_topics
                avoid_topics = list({*avoid_topics, *summary_payload.get('avoid_topics', [])})

        # Step 1: Input Analysis
        yield json.dumps({"type": "status", "message": "🔍 正在分析用户需求与画像..."}) + "\n"
        directions = agent.analyze_input(
            keywords,
            student_profile,
            competition=competition,
            extra_requirements=extra_requirements,
            history_ideas=history_ideas,
            avoid_topics=avoid_topics,
            feedback=feedback,
        )
        if not directions:
            yield json.dumps({"type": "error", "message": "需求分析失败，请稍后重试。"}) + "\n"
            return

        # Step 2: Brainstorming
        yield json.dumps({"type": "status", "message": "🧠 正在进行发散性头脑风暴..."}) + "\n"
        ideas = agent.brainstorm(
            directions,
            keywords=keywords,
            student_profile=student_profile,
            competition=competition,
            extra_requirements=extra_requirements,
            history_ideas=history_ideas,
            avoid_topics=avoid_topics,
            feedback=feedback,
        )
        if not ideas:
            yield json.dumps({"type": "error", "message": "头脑风暴失败，请稍后重试。"}) + "\n"
            return

        # Step 3: Feasibility Check
        yield json.dumps({"type": "status", "message": "⚖️ 正在评估技术可行性 & 筛选 Top 3..."}) + "\n"
        selected_ideas = agent.assess_feasibility(ideas)
        if not selected_ideas:
            yield json.dumps({"type": "error", "message": "可行性评估失败，请稍后重试。"}) + "\n"
            return

        # Step 4: Generate Report (Streaming)
        yield json.dumps({"type": "status", "message": "📝 正在生成详细报告..."}) + "\n"
        report_stream = agent.generate_report(
            selected_ideas,
            keywords=keywords,
            student_profile=student_profile,
            competition=competition,
            extra_requirements=extra_requirements,
            history_ideas=history_ideas,
            avoid_topics=avoid_topics,
            feedback=feedback,
            stream=True,
        )

        if report_stream is None:
            yield json.dumps({"type": "error", "message": "报告生成失败。"}) + "\n"
            return

        for chunk in report_stream:
            if chunk:
                if isinstance(chunk, dict):
                    if chunk.get("type") == "content":
                        yield json.dumps({"type": "delta", "content": chunk["content"]}) + "\n"
                else:
                    yield json.dumps({"type": "delta", "content": str(chunk)}) + "\n"

        # Send metadata at the end
        yield json.dumps({
            "type": "complete",
            "summary": summary_payload.get('summary') if summary_payload else '',
            "avoidTopics": avoid_topics,
        }) + "\n"

    headers = {
        'Cache-Control': 'no-cache',
        'X-Accel-Buffering': 'no',
        'Content-Type': 'application/x-ndjson'
    }
    return Response(stream_with_context(generate()), headers=headers)

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

    if response:
        return jsonify({'reply': response})
    else:
        return jsonify({'error': 'Failed to generate response'}), 500

@agent_bp.route('/projects/<int:project_id>', methods=['DELETE'])
def delete_project(project_id):
    """删除项目"""
    project = CreativeProject.query.get_or_404(project_id)
    db.session.delete(project)
    db.session.commit()
    return jsonify({'message': 'Deleted successfully'})
