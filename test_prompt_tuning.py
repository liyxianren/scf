from utils.ai_nodes import CreativeAgent

def test_node_1():
    agent = CreativeAgent()
    
    # Demo Case
    keywords = "环保 + APP + AI + 新想法 + 社会意义"
    student_profile = "擅长编程的高中生，关注可持续发展"
    
    print("\n[TEST] Testing Node 1: Input Analysis")
    print(f"Keywords: {keywords}")
    print(f"Profile: {student_profile}")
    
    directions = agent.analyze_input(keywords, student_profile)
    
    print("\n[RESULT] Generated Directions:")
    for i, d in enumerate(directions, 1):
        print(f"{i}. {d}")

    print("\n[TEST] Testing Node 2: Brainstorming")
    ideas = agent.brainstorm(directions)
    
    print("\n[RESULT] Generated Ideas:")
    for i, idea in enumerate(ideas, 1):
        print(f"{i}. {idea}")

    print("\n[TEST] Testing Node 3: Feasibility Assessor")
    selected = agent.assess_feasibility(ideas)
    
    print("\n[RESULT] Selected Ideas (Top 3):")
    for i, s in enumerate(selected, 1):
        print(f"{i}. {s}")

    print("\n[TEST] Testing Node 4: Detailing")
    report = agent.generate_report(selected)
    
    print("\n[RESULT] Final Report:")
    print(report)

if __name__ == "__main__":
    test_node_1()
