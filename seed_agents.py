from app import app, db
from models.models import Agent

def seed_agents():
    with app.app_context():
        # Check if Creative Agent exists
        creative_agent = Agent.query.filter_by(name='Creative Copilot').first()

        handbook_agent = Agent.query.filter_by(name='工程手册 Agent').first()
        
        if not creative_agent:
            print("Creating Creative Copilot Agent...")
            creative_agent = Agent(
                name='Creative Copilot',
                description='基于 AI 的创意生成与优化助手。它可以帮助您分析需求、生成创意方案、评估可行性，并输出完整的项目报告。',
                icon='lightbulb',  # Uses material icons
                status='active'
            )
            db.session.add(creative_agent)
            db.session.commit()
            print("Creative Copilot Agent created successfully!")
        else:
            print("Creative Copilot Agent already exists.")

        if not handbook_agent:
            print("Creating Engineering Handbook Agent...")
            handbook_agent = Agent(
                name='工程手册 Agent',
                description='面向留学申请的工程手册生成助手，支持多体系版本与结构化输出。',
                icon='menu_book',
                status='active'
            )
            db.session.add(handbook_agent)
            db.session.commit()
            print("Engineering Handbook Agent created successfully!")
        else:
            print("Engineering Handbook Agent already exists.")

if __name__ == '__main__':
    seed_agents()
