import asyncio
import os
import sys

sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from dotenv import load_dotenv

from browser_use import Agent, ChatGoogle

load_dotenv()

from lmnr import Laminar

Laminar.initialize()


api_key = os.getenv('GOOGLE_API_KEY')
if not api_key:
	raise ValueError('GOOGLE_API_KEY is not set')


async def run_search():
	llm = ChatGoogle(model='gemini-flash-latest', api_key=api_key)
	agent = Agent(
		llm=llm,
		# task='How many stars does the browser-use repo have?',
		task='go to google flights and search for 1 way flight from London to Paris on 2025-11-15',
		# task='Go and fill out https://browser-use.github.io/stress-tests/challenges/iframe-inception-level2.html with random data. Please do it 1 form field at a time IN 1 step. NEVER FILL MORE THAN 1 form field at 1 step!!',
		flash_mode=True,
		max_steps=10,
	)

	await agent.run()


if __name__ == '__main__':
	asyncio.run(run_search())
