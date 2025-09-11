"""Browser class for high-level CDP operations."""

from typing import TYPE_CHECKING, Union

if TYPE_CHECKING:
	from cdp_use.cdp.page.commands import NavigateToHistoryEntryParameters
	from cdp_use.cdp.target.commands import (
		CloseTargetParameters,
		CreateTargetParameters,
	)
	from cdp_use.client import CDPClient

	from .target import Target


class Browser:
	"""High-level browser interface built on CDP."""

	def __init__(self, client: 'CDPClient'):
		self._client = client

	async def goto(self, url: str) -> 'Target':
		"""Navigate to a URL and return the target."""
		# Create a new target (tab)
		params: 'CreateTargetParameters' = {'url': url}
		result = await self._client.send.Target.createTarget(params)

		target_id = result['targetId']

		# Import here to avoid circular import
		from .target import Target

		return Target(self._client, target_id)

	async def goBack(self) -> None:
		"""Navigate back in history."""
		targets = await self.getTargets()
		if not targets:
			raise RuntimeError('No targets available for navigation')

		# Use the first target for navigation (typically the active one)
		target = targets[0]
		await target._ensure_session()

		try:
			# Get navigation history
			history = await self._client.send.Page.getNavigationHistory(session_id=target._session_id)
			current_index = history['currentIndex']
			entries = history['entries']

			# Check if we can go back
			if current_index <= 0:
				raise RuntimeError('Cannot go back - no previous entry in history')

			# Navigate to the previous entry
			previous_entry_id = entries[current_index - 1]['id']
			params: 'NavigateToHistoryEntryParameters' = {'entryId': previous_entry_id}
			await self._client.send.Page.navigateToHistoryEntry(params, session_id=target._session_id)

		except Exception as e:
			raise RuntimeError(f'Failed to navigate back: {e}')

	async def goForward(self) -> None:
		"""Navigate forward in history."""
		targets = await self.getTargets()
		if not targets:
			raise RuntimeError('No targets available for navigation')

		# Use the first target for navigation (typically the active one)
		target = targets[0]
		await target._ensure_session()

		try:
			# Get navigation history
			history = await self._client.send.Page.getNavigationHistory(session_id=target._session_id)
			current_index = history['currentIndex']
			entries = history['entries']

			# Check if we can go forward
			if current_index >= len(entries) - 1:
				raise RuntimeError('Cannot go forward - no next entry in history')

			# Navigate to the next entry
			next_entry_id = entries[current_index + 1]['id']
			params: 'NavigateToHistoryEntryParameters' = {'entryId': next_entry_id}
			await self._client.send.Page.navigateToHistoryEntry(params, session_id=target._session_id)

		except Exception as e:
			raise RuntimeError(f'Failed to navigate forward: {e}')

	async def newTarget(self) -> 'Target':
		"""Create a new target (tab)."""
		params: 'CreateTargetParameters' = {'url': 'about:blank'}
		result = await self._client.send.Target.createTarget(params)

		target_id = result['targetId']

		# Import here to avoid circular import
		from .target import Target

		return Target(self._client, target_id)

	async def getTargets(self) -> list['Target']:
		"""Get all available targets."""
		result = await self._client.send.Target.getTargets()

		targets = []
		# Import here to avoid circular import
		from .target import Target

		for target_info in result['targetInfos']:
			if target_info['type'] in ['page', 'iframe']:
				targets.append(Target(self._client, target_info['targetId']))

		return targets

	async def closeTarget(self, target: Union['Target', str]) -> None:
		"""Close a target by Target object or target ID."""
		# Import here to avoid circular import
		from .target import Target

		if isinstance(target, Target):
			target_id = target._target_id
		else:
			target_id = str(target)

		params: 'CloseTargetParameters' = {'targetId': target_id}
		await self._client.send.Target.closeTarget(params)

	# async def cookies(self, urls: list[str] | None = None) -> list[dict[str, Any]]:
	# 	"""Get cookies, optionally filtered by URLs."""
	# 	params = {}
	# 	if urls:
	# 		params['urls'] = urls

	# 	result = await self._client.send.Network.getCookies(params)
	# 	return result['cookies']

	# async def clearCookies(self) -> None:
	# 	"""Clear all cookies."""
	# 	await self._client.send.Network.clearBrowserCookies()
