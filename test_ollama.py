import asyncio
import os
from dotenv import load_dotenv
from backend.services.agent_service import AgentService

async def test_ollama_agent():
    load_dotenv()
    agent = AgentService()
    
    sample_email = """
    Subject: Project Deadline
    The final project is due next Friday, May 22, 2026, at 5:00 PM.
    Please submit it to the online portal.
    """
    
    print("Analyzing email with local Ollama...")
    try:
        result = await agent.analyze_email(sample_email)
        print("\nExtraction Result:")
        print(f"Is Event: {result.is_event}")
        print(f"Title: {result.title}")
        print(f"Start Time: {result.start_time}")
        print(f"Reasoning: {result.reasoning}")
    except Exception as e:
        print(f"Ollama test failed: {e}")

if __name__ == "__main__":
    asyncio.run(test_ollama_agent())
