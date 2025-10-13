import asyncio

from browser_use import Agent


async def main():
	agent = Agent(
		task='Research the top 3 AI companies and their latest products',
		# this compacts the conversation history every 5 steps similar to /compact in claude code
		summarize_every_n_steps=5,
	)

	await agent.run(max_steps=25)


if __name__ == '__main__':
	asyncio.run(main())
