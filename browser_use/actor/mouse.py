"""Mouse class for mouse operations."""

from typing import TYPE_CHECKING

if TYPE_CHECKING:
	from cdp_use.cdp.input.commands import DispatchMouseEventParameters
	from cdp_use.cdp.input.types import MouseButton
	from cdp_use.client import CDPClient


class Mouse:
	"""Mouse operations for a target."""

	def __init__(self, client: 'CDPClient', session_id: str | None = None):
		self._client = client
		self._session_id = session_id

	async def click(self, x: int, y: int, button: 'MouseButton' = 'left', click_count: int = 1) -> None:
		"""Click at the specified coordinates."""
		# Mouse press
		press_params: 'DispatchMouseEventParameters' = {
			'type': 'mousePressed',
			'x': x,
			'y': y,
			'button': button,
			'clickCount': click_count,
		}
		await self._client.send.Input.dispatchMouseEvent(
			press_params,
			session_id=self._session_id,
		)

		# Mouse release
		release_params: 'DispatchMouseEventParameters' = {
			'type': 'mouseReleased',
			'x': x,
			'y': y,
			'button': button,
			'clickCount': click_count,
		}
		await self._client.send.Input.dispatchMouseEvent(
			release_params,
			session_id=self._session_id,
		)

	async def down(self, button: 'MouseButton' = 'left', click_count: int = 1) -> None:
		"""Press mouse button down."""
		params: 'DispatchMouseEventParameters' = {
			'type': 'mousePressed',
			'x': 0,  # Will use last mouse position
			'y': 0,
			'button': button,
			'clickCount': click_count,
		}
		await self._client.send.Input.dispatchMouseEvent(
			params,
			session_id=self._session_id,
		)

	async def up(self, button: 'MouseButton' = 'left', click_count: int = 1) -> None:
		"""Release mouse button."""
		params: 'DispatchMouseEventParameters' = {
			'type': 'mouseReleased',
			'x': 0,  # Will use last mouse position
			'y': 0,
			'button': button,
			'clickCount': click_count,
		}
		await self._client.send.Input.dispatchMouseEvent(
			params,
			session_id=self._session_id,
		)

	async def move(self, x: int, y: int, steps: int = 1) -> None:
		"""Move mouse to the specified coordinates."""
		# TODO: Implement smooth movement with multiple steps if needed
		_ = steps  # Acknowledge parameter for future use

		params: 'DispatchMouseEventParameters' = {'type': 'mouseMoved', 'x': x, 'y': y}
		await self._client.send.Input.dispatchMouseEvent(params, session_id=self._session_id)
