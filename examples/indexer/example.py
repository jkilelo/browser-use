"""Example showing how to use the IndexerService with Agent.

The IndexerService provides hints on how to interact with websites based on the task and URL.
By default, it returns an empty list, but you can easily mock or extend it.
"""

import asyncio

from browser_use import Agent, Browser
from browser_use.indexer.service import IndexerService


class CustomIndexerService(IndexerService):
	"""Custom indexer that provides specific hints based on URL and task."""

	async def get_hints(self, task: str, current_url: str) -> list[str]:
		"""Override to provide custom hints based on task and URL."""
		hints = []

		# Example: Provide hints for Google searches
		if 'google.com' in current_url:
			if 'search' in task.lower():
				hints = [
					'Use the search input field at the top of the page',
					'Click the "Google Search" button to submit',
					'Review the search results list',
				]

		# Example: Provide hints for GitHub
		elif 'github.com' in current_url:
			if 'repository' in task.lower() or 'repo' in task.lower():
				hints = [
					'Look for the repository name in the header',
					'Check the README.md file for project information',
					'Review the file tree on the left side',
				]

		# Example: General shopping hints
		elif any(shop in current_url for shop in ['amazon.com', 'ebay.com', 'etsy.com']):
			if 'buy' in task.lower() or 'purchase' in task.lower():
				hints = [
					'Use the search bar to find products',
					'Filter results by price, rating, or category',
					'Add items to cart before checkout',
				]

		return hints


async def main():
	# Create custom indexer
	custom_indexer = CustomIndexerService()

	# Create agent with custom indexer
	agent = Agent(
		task='Search for "browser automation tools" on Google',
		browser=Browser(headless=False),
		indexer_service=custom_indexer,
	)

	# The agent will automatically call the indexer service during execution
	# and include the hints in the message that goes to the LLM
	result = await agent.run(max_steps=5)

	print(f'Agent completed: {result.is_successful()}')
	if result.final_result():
		print(f'Final result: {result.final_result()}')


if __name__ == '__main__':
	asyncio.run(main())
