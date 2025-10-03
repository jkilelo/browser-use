import asyncio
import time
from browser_use import Agent
from browser_use.browser.profile import BrowserProfile
from langchain_google_genai import ChatGoogleGenerativeAI

async def main():
	llm = ChatGoogleGenerativeAI(
		model='gemini-2.0-flash-exp',
		timeout=60,
	)
	
	agent = Agent(
		task='Go to example.com, click the "More information" link, then go back',
		llm=llm,
		browser_profile=BrowserProfile(headless=True),
		max_steps=3,
	)
	
	start = time.time()
	result = await agent.run()
	total = time.time() - start
	
	print(f'\n✅ DONE in {total:.2f}s: {result}')

if __name__ == '__main__':
	asyncio.run(main())
