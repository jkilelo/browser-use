import asyncio
import os
from dotenv import load_dotenv
from browser_use import Agent
from browser_use.llm.google import ChatGoogle

load_dotenv()

llm = ChatGoogle(model='gemini-2.5-flash', api_key=os.getenv('GOOGLE_API_KEY'), temperature=0.0)

async def test():
	agent = Agent(
		task='Go to example.com',
		llm=llm,
		max_steps=2
	)
	result = await agent.run()
	print(f'✅ DONE')

if __name__ == '__main__':
	asyncio.run(test())
