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


async def run_search():
	llm = ChatGoogle(model='gemini-2.0-flash', api_key=api_key)
	agent = Agent(
		llm=llm,
		# task='How many stars does the browser-use repo have?',
		task='Go to google flights, find a one way flight from Zurich to London on 2025-10-30 and return the url of the cheapest flight',
		flash_mode=True,
	)

	history = await agent.run()
	# save history to ./tmp/gemini_history.json
	history.save_to_file('./tmp/gemini_history.json')


if __name__ == '__main__':
	asyncio.run(run_search())
