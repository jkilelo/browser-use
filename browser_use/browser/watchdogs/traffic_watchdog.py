"""Traffic watchdog for monitoring network requests using CDP."""

import asyncio
from pathlib import Path
from typing import TYPE_CHECKING, ClassVar

from cdp_use.cdp.network import LoadingFailedEvent, LoadingFinishedEvent, RequestWillBeSentEvent, ResponseReceivedEvent
from cdp_use.cdp.target import SessionID, TargetID
from pydantic import PrivateAttr

from browser_use.browser.events import (
	BrowserLaunchEvent,
	BrowserStoppedEvent,
	NavigationCompleteEvent,
	NavigationStartedEvent,
	NetworkStabilizedEvent,
	TabClosedEvent,
	TabCreatedEvent,
)
from browser_use.browser.watchdog_base import BaseWatchdog

if TYPE_CHECKING:
	pass


# Type alias for request info dict
RequestInfo = dict[str, str | float]


def _load_easylist_patterns() -> set[str]:
	"""Load URL patterns from EasyList blocklist - called once per TrafficWatchdog instance."""
	patterns = set()
	easylist_path = Path(__file__).parent / 'easylist'

	if not easylist_path.exists():
		return patterns

	try:
		with open(easylist_path, encoding='utf-8') as f:
			for line in f:
				line = line.strip()
				# Skip comments and empty lines
				if not line or line.startswith('!') or line.startswith('['):
					continue
				# Extract domain patterns from ||domain.com^ format
				if line.startswith('||'):
					pattern = line[2:].split('^')[0].split('$')[0].split('/')[0].lower()
					if pattern:
						patterns.add(pattern)
	except Exception:
		pass  # Silently fail if file doesn't exist or can't be read

	return patterns


class TrafficWatchdog(BaseWatchdog):
	"""Monitors network traffic using CDP Network domain.

	Provides network stability detection for other watchdogs like DOMWatchdog.
	"""

	LISTENS_TO: ClassVar[list[type]] = [
		BrowserLaunchEvent,
		BrowserStoppedEvent,
		TabCreatedEvent,
		TabClosedEvent,
		NavigationStartedEvent,
		NavigationCompleteEvent,
	]
	EMITS: ClassVar[list[type]] = [NetworkStabilizedEvent]

	# Private state - track requests per target
	_pending_requests: dict[TargetID, dict[str, RequestInfo]] = PrivateAttr(default_factory=dict)
	_last_activity: dict[TargetID, float] = PrivateAttr(default_factory=dict)
	_session_to_target: dict[SessionID, TargetID] = PrivateAttr(default_factory=dict)
	_network_enabled_sessions: set[SessionID] = PrivateAttr(default_factory=set)
	_cdp_handlers_registered: bool = PrivateAttr(default=False)
	_easylist_patterns: set[str] = PrivateAttr(default_factory=set)

	# Filtering patterns - only track essential resources for page functionality
	RELEVANT_RESOURCE_TYPES: ClassVar[set[str]] = {
		'Document',  # Main HTML document
		'Script',  # JavaScript that may modify DOM
		'XHR',  # AJAX requests that load dynamic content
		'Fetch',  # Modern fetch API requests
	}

	IGNORED_URL_PATTERNS: ClassVar[set[str]] = {
		# Analytics and tracking
		'analytics',
		'tracking',
		'telemetry',
		'beacon',
		'metrics',
		# Ad-related
		'doubleclick',
		'adsystem',
		'adserver',
		'advertising',
		# Social media widgets
		'facebook.com/plugins',
		'platform.twitter',
		'linkedin.com/embed',
		# Live chat and support
		'livechat',
		'zendesk',
		'intercom',
		'crisp.chat',
		'hotjar',
		# Push notifications
		'push-notifications',
		'onesignal',
		'pushwoosh',
		# Background sync/heartbeat
		'heartbeat',
		'ping',
		'alive',
		# WebRTC and streaming
		'webrtc',
		'rtmp://',
		'wss://',
		# Common CDNs for dynamic content (commented out as these may be needed)
		# 'cloudfront.net',
		# 'fastly.net',
	}

	IGNORED_CONTENT_TYPES: ClassVar[set[str]] = {
		'streaming',
		'video',
		'audio',
		'webm',
		'mp4',
		'event-stream',
		'websocket',
		'protobuf',
	}

	async def on_BrowserLaunchEvent(self, event: BrowserLaunchEvent) -> None:
		"""Initialize traffic monitoring on browser launch."""
		# Load EasyList patterns once at startup
		if not self._easylist_patterns:
			self._easylist_patterns = _load_easylist_patterns()
			self.logger.debug(f'[TrafficWatchdog] Loaded {len(self._easylist_patterns)} EasyList patterns')

		self.logger.debug('[TrafficWatchdog] Browser launched, ready to monitor traffic')
		self._pending_requests.clear()
		self._last_activity.clear()
		self._session_to_target.clear()
		self._network_enabled_sessions.clear()
		self._cdp_handlers_registered = False

	async def on_BrowserStoppedEvent(self, event: BrowserStoppedEvent) -> None:
		"""Clean up on browser stop."""
		self.logger.debug('[TrafficWatchdog] Browser stopped, cleaning up traffic monitoring')
		self._pending_requests.clear()
		self._last_activity.clear()
		self._session_to_target.clear()
		self._network_enabled_sessions.clear()
		self._cdp_handlers_registered = False

	async def on_TabCreatedEvent(self, event: TabCreatedEvent) -> None:
		"""Enable Network domain for new tabs."""
		try:
			# Get or create CDP session for this target
			cdp_session = await self.browser_session.get_or_create_cdp_session(event.target_id, focus=False)

			# Map session to target for request tracking
			self._session_to_target[cdp_session.session_id] = event.target_id

			# Initialize target-specific state
			if event.target_id not in self._pending_requests:
				self._pending_requests[event.target_id] = {}
			if event.target_id not in self._last_activity:
				self._last_activity[event.target_id] = asyncio.get_event_loop().time()

			# Enable Network domain if not already enabled
			if cdp_session.session_id not in self._network_enabled_sessions:
				await cdp_session.cdp_client.send.Network.enable(session_id=cdp_session.session_id)
				self._network_enabled_sessions.add(cdp_session.session_id)
				self.logger.debug(f'[TrafficWatchdog] Enabled Network domain for tab {event.target_id[-4:]}')

			# Register CDP handlers (only once globally)
			if not self._cdp_handlers_registered:
				self._register_cdp_handlers()
				self._cdp_handlers_registered = True
				self.logger.debug('[TrafficWatchdog] Registered CDP Network event handlers')

		except Exception as e:
			self.logger.warning(f'[TrafficWatchdog] Failed to enable Network domain for tab {event.target_id[-4:]}: {e}')

	async def on_TabClosedEvent(self, event: TabClosedEvent) -> None:
		"""Clean up pending requests for closed tab."""
		if event.target_id in self._pending_requests:
			del self._pending_requests[event.target_id]
		if event.target_id in self._last_activity:
			del self._last_activity[event.target_id]
		# Clean up session mapping
		for session_id, target_id in list(self._session_to_target.items()):
			if target_id == event.target_id:
				del self._session_to_target[session_id]

	async def on_NavigationStartedEvent(self, event: NavigationStartedEvent) -> None:
		"""Reset pending requests on navigation start."""
		target_id = event.target_id
		if target_id in self._pending_requests:
			self.logger.debug(
				f'[TrafficWatchdog] Navigation started to {event.url}, resetting {len(self._pending_requests[target_id])} pending requests for target {target_id[-4:]}'
			)
			self._pending_requests[target_id].clear()
		else:
			self._pending_requests[target_id] = {}
		self._last_activity[target_id] = asyncio.get_event_loop().time()

	async def on_NavigationCompleteEvent(self, event: NavigationCompleteEvent) -> None:
		"""Navigation complete - could trigger network stability check here if needed."""
		target_id = event.target_id
		pending_count = len(self._pending_requests.get(target_id, {}))
		self.logger.debug(
			f'[TrafficWatchdog] Navigation complete to {event.url}, {pending_count} pending requests for target {target_id[-4:]}'
		)

	def _register_cdp_handlers(self) -> None:
		"""Register CDP Network domain event handlers."""
		cdp_client = self.browser_session.cdp_client

		# Register handlers using cdp-use's register API
		cdp_client.register.Network.requestWillBeSent(self._on_request_will_be_sent)  # type: ignore
		cdp_client.register.Network.responseReceived(self._on_response_received)  # type: ignore
		cdp_client.register.Network.loadingFinished(self._on_loading_finished)  # type: ignore
		cdp_client.register.Network.loadingFailed(self._on_loading_failed)  # type: ignore

	async def _on_request_will_be_sent(self, event: RequestWillBeSentEvent, session_id: SessionID | None) -> None:
		"""Handle CDP Network.requestWillBeSent event."""
		try:
			# Get target_id from session
			if not session_id or session_id not in self._session_to_target:
				return
			target_id = self._session_to_target[session_id]

			request_id = event.get('requestId', '')
			request = event.get('request', {})
			resource_type = event.get('type', '')
			url = request.get('url', '')

			# Apply filtering logic
			if not self._should_track_request(resource_type, url):
				return

			self.logger.debug(f'[TrafficWatchdog] Request will be sent: {url[:80]} ({resource_type}) on target {target_id[-4:]}')

			# Track this request for the specific target
			if target_id not in self._pending_requests:
				self._pending_requests[target_id] = {}

			self._pending_requests[target_id][request_id] = {
				'request_id': request_id,
				'url': url,
				'resource_type': resource_type,
				'timestamp': asyncio.get_event_loop().time(),
			}
			self._last_activity[target_id] = asyncio.get_event_loop().time()

		except Exception as e:
			self.logger.debug(f'[TrafficWatchdog] Error in _on_request_will_be_sent: {e}')

	async def _on_response_received(self, event: ResponseReceivedEvent, session_id: SessionID | None) -> None:
		"""Handle CDP Network.responseReceived event."""
		try:
			# Get target_id from session
			if not session_id or session_id not in self._session_to_target:
				return
			target_id = self._session_to_target[session_id]

			request_id = event.get('requestId', '')
			response = event.get('response', {})
			headers = response.get('headers', {})

			# Additional content-type filtering
			content_type = headers.get('content-type', '').lower()
			if any(ignored in content_type for ignored in self.IGNORED_CONTENT_TYPES):
				# Remove from pending if present
				if target_id in self._pending_requests and request_id in self._pending_requests[target_id]:
					del self._pending_requests[target_id][request_id]
				return

			# Filter out very large responses (likely not essential for page load)
			content_length = headers.get('content-length')
			if content_length and int(content_length) > 5 * 1024 * 1024:  # 5MB
				if target_id in self._pending_requests and request_id in self._pending_requests[target_id]:
					del self._pending_requests[target_id][request_id]
				return

		except Exception as e:
			self.logger.debug(f'[TrafficWatchdog] Error in _on_response_received: {e}')

	async def _on_loading_finished(self, event: LoadingFinishedEvent, session_id: SessionID | None) -> None:
		"""Handle CDP Network.loadingFinished event."""
		try:
			# Get target_id from session
			if not session_id or session_id not in self._session_to_target:
				return
			target_id = self._session_to_target[session_id]

			request_id = event.get('requestId', '')
			if target_id in self._pending_requests and request_id in self._pending_requests[target_id]:
				# url = self._pending_requests[target_id][request_id]['url']
				del self._pending_requests[target_id][request_id]
				self._last_activity[target_id] = asyncio.get_event_loop().time()
				# self.logger.debug(f'[TrafficWatchdog] Request finished: {url[:80]}')

		except Exception as e:
			self.logger.debug(f'[TrafficWatchdog] Error in _on_loading_finished: {e}')

	async def _on_loading_failed(self, event: LoadingFailedEvent, session_id: SessionID | None) -> None:
		"""Handle CDP Network.loadingFailed event."""
		try:
			# Get target_id from session
			if not session_id or session_id not in self._session_to_target:
				return
			target_id = self._session_to_target[session_id]

			request_id = event.get('requestId', '')
			if target_id in self._pending_requests and request_id in self._pending_requests[target_id]:
				# url = self._pending_requests[target_id][request_id]['url']
				del self._pending_requests[target_id][request_id]
				self._last_activity[target_id] = asyncio.get_event_loop().time()
				# self.logger.debug(f'[TrafficWatchdog] Request failed: {url[:80]}')

		except Exception as e:
			self.logger.debug(f'[TrafficWatchdog] Error in _on_loading_failed: {e}')

	def _should_track_request(self, resource_type: str, url: str) -> bool:
		"""Determine if a request should be tracked based on filtering rules."""
		# Filter by resource type
		if resource_type not in self.RELEVANT_RESOURCE_TYPES:
			return False

		# Filter out data: and blob: URLs
		url_lower = url.lower()
		if url_lower.startswith(('data:', 'blob:')):
			return False

		# Filter by manual URL patterns (fast substring check)
		if any(pattern in url_lower for pattern in self.IGNORED_URL_PATTERNS):
			return False

		# Filter by EasyList patterns - fast O(1) domain check
		if self._easylist_patterns:
			# Extract domain from URL (between :// and first /)
			try:
				# Fast domain extraction without full URL parsing
				if '://' in url_lower:
					domain_part = url_lower.split('://', 1)[1].split('/', 1)[0].split('?', 1)[0]
					# Check if domain or any subdomain is in blocklist
					# e.g., for "ads.example.com", check "ads.example.com", "example.com"
					if domain_part in self._easylist_patterns:
						return False
					# Check parent domains (e.g., "example.com" for "ads.example.com")
					parts = domain_part.split('.')
					for i in range(len(parts)):
						parent_domain = '.'.join(parts[i:])
						if parent_domain in self._easylist_patterns:
							return False
			except Exception:
				pass  # If URL parsing fails, don't filter

		return True

	async def wait_for_stable_network(
		self,
		target_id: TargetID,
		idle_time: float | None = None,
		max_wait: float | None = None,
	) -> NetworkStabilizedEvent:
		"""Wait for network to stabilize (no relevant pending requests for idle_time seconds).

		Args:
			target_id: Target ID to wait for network stability (required)
			idle_time: Seconds of no activity to consider network stable
			max_wait: Maximum seconds to wait before giving up

		Returns:
			NetworkStabilizedEvent with stability status
		"""
		# Use browser profile defaults if not specified
		idle_time = idle_time or self.browser_session.browser_profile.wait_for_network_idle_page_load_time
		max_wait = max_wait or 5.0  # Default max wait of 5 seconds

		# Initialize target state if it doesn't exist
		if target_id not in self._pending_requests:
			self._pending_requests[target_id] = {}
		if target_id not in self._last_activity:
			self._last_activity[target_id] = asyncio.get_event_loop().time()

		start_time = asyncio.get_event_loop().time()
		timed_out = False

		self.logger.debug(
			f'[TrafficWatchdog] Waiting for network stability on target {target_id[-4:]} (idle: {idle_time}s, max: {max_wait}s)'
		)

		try:
			while True:
				await asyncio.sleep(0.1)
				now = asyncio.get_event_loop().time()

				# Get pending requests for the specific target
				target_pending = self._pending_requests.get(target_id, {})
				target_last_activity = self._last_activity.get(target_id, start_time)

				# Check if network is idle
				if len(target_pending) == 0 and (now - target_last_activity) >= idle_time:
					self.logger.debug(
						f'[TrafficWatchdog] Network stabilized for target {target_id[-4:]} after {now - start_time:.2f}s '
						f'(idle for {now - target_last_activity:.2f}s)'
					)
					break

				# Check timeout
				if now - start_time > max_wait:
					# Build list of pending URLs safely
					pending_urls = []
					for _, req_info in list(target_pending.items())[:5]:
						url = str(req_info.get('url', ''))[:50] if isinstance(req_info, dict) else ''
						if url:
							pending_urls.append(url)

					self.logger.debug(
						f'[TrafficWatchdog] Network timeout for target {target_id[-4:]} after {max_wait}s with {len(target_pending)} '
						f'pending requests: {pending_urls}'
					)
					timed_out = True
					break

		except Exception as e:
			self.logger.warning(f'[TrafficWatchdog] Error waiting for network stability: {e}')
			timed_out = True

		elapsed = asyncio.get_event_loop().time() - start_time
		pending_count = len(self._pending_requests.get(target_id, {}))

		# Create and return the event
		event = NetworkStabilizedEvent(
			target_id=target_id,
			pending_requests=pending_count,
			elapsed_time=elapsed,
			timed_out=timed_out,
		)

		return event
