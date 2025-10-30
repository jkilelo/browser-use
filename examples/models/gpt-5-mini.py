"""
Simple try of the agent.

@dev You need to add OPENAI_API_KEY to your environment variables.
"""

import asyncio

from dotenv import load_dotenv

from browser_use import Agent, ChatOpenAI

load_dotenv()

# All the models are type safe from OpenAI in case you need a list of supported models
llm = ChatOpenAI(model='gpt-4.1-mini')
agent = Agent(
	llm=llm,
	task='Go to google flights, find a one way flight from Zurich to London on 2025-10-30 and return the url of the cheapest flight',
)


async def main():
	history = await agent.run(max_steps=20)
	input('Press Enter to continue...')

	# save history to ./tmp/gpt-4.1-mini_history.json
	history.save_to_file('./tmp/gpt-4.1-mini_history.json')


asyncio.run(main())
