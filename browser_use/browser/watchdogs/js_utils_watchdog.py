"""
JavaScript Utils Watchdog - Injects robust interaction utilities into all pages.
This prevents JavaScript execution errors and provides reliable form interaction methods.
"""

from typing import ClassVar

from bubus import BaseEvent
from pydantic import PrivateAttr

from browser_use.browser.events import BrowserConnectedEvent
from browser_use.browser.js_utils import JS_UTILS
from browser_use.browser.watchdog_base import BaseWatchdog


class JSUtilsWatchdog(BaseWatchdog):
	"""Injects JavaScript utility functions into all pages for robust interactions."""

	# Event contracts
	LISTENS_TO: ClassVar[list[type[BaseEvent]]] = [BrowserConnectedEvent]
	EMITS: ClassVar[list[type[BaseEvent]]] = []

	# Private state
	_script_identifier: str | None = PrivateAttr(default=None)

	async def on_BrowserConnectedEvent(self, event: BrowserConnectedEvent) -> None:
		"""Inject JavaScript utilities when browser connects."""
		try:
			self.logger.debug('🔧 Injecting JavaScript utility functions for robust interactions...')

			# Inject utilities into all new pages
			self._script_identifier = await self.browser_session._cdp_add_init_script(JS_UTILS)

			self.logger.debug('✅ JavaScript utilities injected successfully')

		except Exception as e:
			self.logger.warning(f'Failed to inject JavaScript utilities: {e}')

	async def cleanup(self) -> None:
		"""Remove injected scripts on cleanup."""
		if self._script_identifier:
			try:
				await self.browser_session._cdp_remove_init_script(self._script_identifier)
				self.logger.debug('🧹 JavaScript utilities cleanup completed')
			except Exception as e:
				self.logger.warning(f'Failed to cleanup JavaScript utilities: {e}')
