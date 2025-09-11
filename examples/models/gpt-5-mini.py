"""
Simple try of the agent.

@dev You need to add OPENAI_API_KEY to your environment variables.
"""

import asyncio

from dotenv import load_dotenv
from lmnr import Laminar

from browser_use import Agent, ChatOpenAI

load_dotenv()

Laminar.initialize()


# All the models are type safe from OpenAI in case you need a list of supported models
llm = ChatOpenAI(model='gpt-5-mini')
agent = Agent(
	llm=llm,
	task='Go to google flights, find the cheapest 1 way flight from New York to Paris on 2025-10-15',
	flash_mode=True,
)


async def main():
	await agent.run()
	input('Press Enter to continue...')


asyncio.run(main())
