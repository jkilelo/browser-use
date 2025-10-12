"""
Example demonstrating conversation history summarization.

This feature condenses the agent's conversation history every N steps to prevent
context overflow on long-running tasks.
"""

import asyncio

from browser_use import Agent
from browser_use.llm.models import get_llm_by_name


async def main():
	# Create an agent with conversation summarization enabled
	# Every 10 steps, the agent will condense the last 10 steps into a summary
	agent = Agent(
		task='Research the top 3 AI companies and their latest products',
		llm=get_llm_by_name('gpt-4o-mini'),
		summarize_every_n_steps=10,  # Summarize history every 10 steps
	)

	# Run the agent
	# After step 10: The first 10 steps will be condensed into summary_0
	# After step 20: Steps 11-20 will be condensed into summary_1
	# The history will then be: [init, summary_0, summary_1, steps 21+]
	history = await agent.run(max_steps=25)

	print(f'\nCompleted {len(history)} steps')
	print(f'Final result: {history.final_result()}')


if __name__ == '__main__':
	asyncio.run(main())
