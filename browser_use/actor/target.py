"""Target class for target-level operations."""

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
	from cdp_use.cdp.dom.commands import (
		DescribeNodeParameters,
		QuerySelectorAllParameters,
	)
	from cdp_use.cdp.emulation.commands import SetDeviceMetricsOverrideParameters
	from cdp_use.cdp.input.commands import (
		DispatchKeyEventParameters,
		SynthesizeScrollGestureParameters,
	)
	from cdp_use.cdp.page.commands import CaptureScreenshotParameters
	from cdp_use.cdp.runtime.commands import EvaluateParameters
	from cdp_use.cdp.target.commands import (
		AttachToTargetParameters,
		GetTargetInfoParameters,
	)
	from cdp_use.cdp.target.types import TargetInfo
	from cdp_use.client import CDPClient

	from .element import Element
	from .mouse import Mouse


class Target:
	"""Target operations (tab or iframe)."""

	def __init__(self, client: 'CDPClient', target_id: str):
		self._client = client
		self._target_id = target_id
		self._session_id: str | None = None
		self._mouse: 'Mouse | None' = None

	async def _ensure_session(self) -> str:
		"""Ensure we have a session ID for this target."""
		if not self._session_id:
			params: 'AttachToTargetParameters' = {'targetId': self._target_id, 'flatten': True}
			result = await self._client.send.Target.attachToTarget(params)
			self._session_id = result['sessionId']

			# Enable necessary domains
			import asyncio

			await asyncio.gather(
				self._client.send.Page.enable(session_id=self._session_id),
				self._client.send.DOM.enable(session_id=self._session_id),
				self._client.send.Runtime.enable(session_id=self._session_id),
				self._client.send.Network.enable(session_id=self._session_id),
			)

		return self._session_id

	@property
	async def mouse(self) -> 'Mouse':
		"""Get the mouse interface for this target."""
		if not self._mouse:
			session_id = await self._ensure_session()
			from .mouse import Mouse

			self._mouse = Mouse(self._client, session_id)
		return self._mouse

	async def reload(self) -> None:
		"""Reload the target."""
		session_id = await self._ensure_session()
		await self._client.send.Page.reload(session_id=session_id)

	async def getElement(self, backend_node_id: int) -> 'Element':
		"""Get an element by its backend node ID."""
		session_id = await self._ensure_session()

		from .element import Element

		return Element(self._client, backend_node_id, session_id)

	async def evaluate(self, page_function: str, arg: Any = None) -> Any:
		"""Execute JavaScript in the target."""
		session_id = await self._ensure_session()

		if callable(page_function):
			# Convert function to string
			import inspect

			page_function = inspect.getsource(page_function)

		# Prepare the expression
		if arg is not None:
			# If we have arguments, we need to call the function
			expression = f'({page_function})({arg!r})'
		else:
			# Check if it's already a function call or just an expression
			if page_function.strip().startswith('(') and page_function.strip().endswith(')'):
				expression = page_function
			elif '(' in page_function and page_function.strip().endswith(')'):
				expression = page_function
			else:
				# It's just an expression
				expression = page_function

		params: 'EvaluateParameters' = {'expression': expression, 'returnByValue': True, 'awaitPromise': True}
		result = await self._client.send.Runtime.evaluate(
			params,
			session_id=session_id,
		)

		if 'exceptionDetails' in result:
			raise RuntimeError(f'JavaScript evaluation failed: {result["exceptionDetails"]}')

		return result.get('result', {}).get('value')

	async def screenshot(self, format: str = 'jpeg', quality: int | None = None) -> str:
		"""Take a screenshot and return base64 encoded image.

		Args:
		    format: Image format ('jpeg', 'png', 'webp')
		    quality: Quality 0-100 for JPEG format

		Returns:
		    Base64-encoded image data
		"""
		session_id = await self._ensure_session()

		params: 'CaptureScreenshotParameters' = {'format': format}

		if quality is not None and format.lower() == 'jpeg':
			params['quality'] = quality

		result = await self._client.send.Page.captureScreenshot(params, session_id=session_id)

		return result['data']

	async def press(self, key: str) -> None:
		"""Press a key on the page (sends keyboard input to the focused element or page)."""
		session_id = await self._ensure_session()

		# Handle key combinations like "Control+A"
		if '+' in key:
			parts = key.split('+')
			modifiers = parts[:-1]
			main_key = parts[-1]

			# Press modifier keys
			for mod in modifiers:
				params: 'DispatchKeyEventParameters' = {'type': 'keyDown', 'key': mod}
				await self._client.send.Input.dispatchKeyEvent(params, session_id=session_id)

			# Press main key
			main_down_params: 'DispatchKeyEventParameters' = {'type': 'keyDown', 'key': main_key}
			await self._client.send.Input.dispatchKeyEvent(main_down_params, session_id=session_id)

			main_up_params: 'DispatchKeyEventParameters' = {'type': 'keyUp', 'key': main_key}
			await self._client.send.Input.dispatchKeyEvent(main_up_params, session_id=session_id)

			# Release modifier keys
			for mod in reversed(modifiers):
				release_params: 'DispatchKeyEventParameters' = {'type': 'keyUp', 'key': mod}
				await self._client.send.Input.dispatchKeyEvent(release_params, session_id=session_id)
		else:
			# Simple key press
			key_down_params: 'DispatchKeyEventParameters' = {'type': 'keyDown', 'key': key}
			await self._client.send.Input.dispatchKeyEvent(key_down_params, session_id=session_id)

			key_up_params: 'DispatchKeyEventParameters' = {'type': 'keyUp', 'key': key}
			await self._client.send.Input.dispatchKeyEvent(key_up_params, session_id=session_id)

	async def setViewportSize(self, width: int, height: int) -> None:
		"""Set the viewport size."""
		session_id = await self._ensure_session()

		params: 'SetDeviceMetricsOverrideParameters' = {
			'width': width,
			'height': height,
			'deviceScaleFactor': 1.0,
			'mobile': False,
		}
		await self._client.send.Emulation.setDeviceMetricsOverride(
			params,
			session_id=session_id,
		)

	async def scroll(self, x: int = 0, y: int = 0, delta_x: int | None = None, delta_y: int | None = None) -> None:
		"""Scroll the page using robust CDP methods."""
		session_id = await self._ensure_session()

		# Activate the target first (critical for CDP calls to work)
		try:
			await self._client.send.Target.activateTarget(params={'targetId': self._target_id})
		except Exception:
			pass

		# Method 1: Try mouse wheel event (most reliable)
		try:
			# Get viewport dimensions
			layout_metrics = await self._client.send.Page.getLayoutMetrics(session_id=session_id)
			viewport_width = layout_metrics['layoutViewport']['clientWidth']
			viewport_height = layout_metrics['layoutViewport']['clientHeight']

			# Use provided coordinates or center of viewport
			scroll_x = x if x > 0 else viewport_width / 2
			scroll_y = y if y > 0 else viewport_height / 2

			# Calculate scroll deltas (positive = down/right)
			scroll_delta_x = delta_x or 0
			scroll_delta_y = delta_y or 0

			# Dispatch mouse wheel event
			await self._client.send.Input.dispatchMouseEvent(
				params={
					'type': 'mouseWheel',
					'x': scroll_x,
					'y': scroll_y,
					'deltaX': scroll_delta_x,
					'deltaY': scroll_delta_y,
				},
				session_id=session_id,
			)
			return

		except Exception:
			pass

		# Method 2: Fallback to synthesizeScrollGesture
		try:
			params: 'SynthesizeScrollGestureParameters' = {'x': x, 'y': y, 'xDistance': delta_x or 0, 'yDistance': delta_y or 0}
			await self._client.send.Input.synthesizeScrollGesture(
				params,
				session_id=session_id,
			)
		except Exception:
			# Method 3: JavaScript fallback
			scroll_js = f'window.scrollBy({delta_x or 0}, {delta_y or 0})'
			await self._client.send.Runtime.evaluate(
				params={'expression': scroll_js, 'returnByValue': True},
				session_id=session_id,
			)

	# Target properties (from CDP getTargetInfo)
	async def getTargetInfo(self) -> 'TargetInfo':
		"""Get target information."""
		params: 'GetTargetInfoParameters' = {'targetId': self._target_id}
		result = await self._client.send.Target.getTargetInfo(params)
		return result['targetInfo']

	async def getUrl(self) -> str:
		"""Get the current URL."""
		info = await self.getTargetInfo()
		return info.get('url', '')

	async def getTitle(self) -> str:
		"""Get the current title."""
		info = await self.getTargetInfo()
		return info.get('title', '')

	# Element finding methods (these would need to be implemented based on DOM queries)
	async def getElementsByCSSSelector(self, selector: str) -> list['Element']:
		"""Get elements by CSS selector."""
		session_id = await self._ensure_session()

		# Get document first
		doc_result = await self._client.send.DOM.getDocument(session_id=session_id)
		document_node_id = doc_result['root']['nodeId']

		# Query selector all
		query_params: 'QuerySelectorAllParameters' = {'nodeId': document_node_id, 'selector': selector}
		result = await self._client.send.DOM.querySelectorAll(query_params, session_id=session_id)

		elements = []
		from .element import Element

		# Convert node IDs to backend node IDs
		for node_id in result['nodeIds']:
			# Get backend node ID
			describe_params: 'DescribeNodeParameters' = {'nodeId': node_id}
			node_result = await self._client.send.DOM.describeNode(describe_params, session_id=session_id)
			backend_node_id = node_result['node']['backendNodeId']
			elements.append(Element(self._client, backend_node_id, session_id))

		return elements
