import asyncio
import os
from dotenv import load_dotenv
from browser_use import Agent
from browser_use.llm.google import ChatGoogle

load_dotenv()

llm = ChatGoogle(model='gemini-2.5-flash', api_key=os.getenv('GOOGLE_API_KEY'), temperature=0.0)

async def test():
	agent = Agent(
		task='Go to google.com and search for "browser automation"',
		llm=llm,
		max_steps=5  # Run 5 steps to see parallel execution between steps
	)
	result = await agent.run()
	print(f'✅ DONE: {result}')

if __name__ == '__main__':
	asyncio.run(test())
