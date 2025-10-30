"""Indexer service that provides interaction hints based on task and URL."""

from browser_use.indexer.views import IndexerInput, IndexerResult


class IndexerService:
	"""Service that analyzes task and URL to provide interaction hints.

	This is a simple stub implementation that returns an empty list of hints.
	The actual implementation should be mocked or overridden on the user's side.
	"""

	async def get_hints(self, task: str, current_url: str) -> list[str]:
		"""Get interaction hints for the given task and URL.

		Args:
			task: The task the agent is trying to accomplish
			current_url: The current URL the agent is on

		Returns:
			List of string hints on how to interact with the website
		"""
		# Stub implementation - returns empty list
		# Users should mock or override this method with their own implementation
		return []

	async def get_hints_structured(self, input_data: IndexerInput) -> IndexerResult:
		"""Get interaction hints using structured input/output.

		Args:
			input_data: IndexerInput containing task and current_url

		Returns:
			IndexerResult containing list of hints
		"""
		hints = await self.get_hints(input_data.task, input_data.current_url)
		return IndexerResult(hints=hints)
