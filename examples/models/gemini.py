import asyncio
import os
import sys

sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from dotenv import load_dotenv

from browser_use import Agent, ChatGoogle

load_dotenv()

api_key = os.getenv('GOOGLE_API_KEY')
if not api_key:
	raise ValueError('GOOGLE_API_KEY is not set')

from lmnr import Laminar

Laminar.initialize()


async def run_search():
	llm = ChatGoogle(model='gemini-flash-latest', api_key=api_key)
	agent = Agent(
		llm=llm,
		task="""Read webpage https://lqqg2rlxn1.space.minimax.io and follow the prompt: Test the current ethical dilemma resolver website comprehensively to identify remaining issues. Please:

1. Enter test dilemma: "I discovered my colleague is falsifying expense reports but they have a sick family member and need the money"
2. Test Steps 1-3 navigation and AI processing
3. Test Step 4 auto-population of objective facts
4. Test Step 5 auto-population and regenerate function 
5. Test Step 6 text visibility and navigation
6. Test Steps 7-8 for AI contextual solutions
7. Test Step 9 interactive recommendation features
8. Test Steps 10-12 including PDF download
9. Note any crashes, errors, or missing functionality

Provide a detailed report of what's working vs what still needs to be fixed.""",
		flash_mode=True,
	)

	await agent.run()


if __name__ == '__main__':
	asyncio.run(run_search())
