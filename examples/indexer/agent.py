"""Example showing IndexerService with Gemini model.

This example demonstrates how to use a custom IndexerService with Google's Gemini model
to provide contextual hints for flight search tasks.
"""

import asyncio
import os
import sys

sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from dotenv import load_dotenv

from browser_use import Agent, ChatBrowserUse
from browser_use.indexer.service import IndexerService

load_dotenv()


class FlightSearchIndexer(IndexerService):
	"""Custom indexer that provides hints for flight search websites."""

	async def get_hints(self, task: str, current_url: str) -> list[str]:
		"""Provide helpful hints based on the current website and task."""
		hints = []

		# Google Flights specific hints
		if 'google.com/travel/flights' in current_url:
			if 'flight' in task.lower():
				hints = [
					'after input from/to destination, a dropdown appears, where you have to select an option from the dropdown before continuing',
					"please don't use scroll",
				]

		return hints


async def run_search():
	# Create custom indexer for flight searches
	flight_indexer = FlightSearchIndexer()

	# Create Gemini LLM
	# llm = ChatOpenAI(model='gpt-4.1-mini')
	llm = ChatBrowserUse()

	# Create agent with custom indexer
	agent = Agent(
		llm=llm,
		task='Go to google flights, find a one way flight from Zurich to London on 2025-11-05 and return the url of the cheapest flight',
		flash_mode=True,
		indexer_service=flight_indexer,
	)

	# Run the agent - indexer hints will be automatically included in the LLM prompts
	history = await agent.run()

	# Save history to file
	# history.save_to_file('./tmp/gemini_indexer_history.json')

	print(f'Agent completed: {history.is_successful()}')
	if history.final_result():
		print(f'Final result: {history.final_result()}')


if __name__ == '__main__':
	asyncio.run(run_search())
