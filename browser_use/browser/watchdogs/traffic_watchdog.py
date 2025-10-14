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
	_page_enabled_sessions: set[SessionID] = PrivateAttr(default_factory=set)
	_cdp_handlers_registered: bool = PrivateAttr(default=False)
	_easylist_patterns: set[str] = PrivateAttr(default_factory=set)
	# Track document/frame loading state per target
	_frame_loading_state: dict[TargetID, dict[str, bool]] = PrivateAttr(
		default_factory=dict
	)  # {target_id: {frame_id: is_loading}}
	_document_loaded: dict[TargetID, bool] = PrivateAttr(default_factory=dict)  # Has DOMContentLoaded fired?
	_page_loaded: dict[TargetID, bool] = PrivateAttr(default_factory=dict)  # Has window.onload fired?
	_mutation_observer_injected: dict[TargetID, bool] = PrivateAttr(default_factory=dict)  # Mutation observer active?

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
		# Social media widgets and embeds
		'facebook.com/plugins',
		'platform.twitter',
		'linkedin.com/embed',
		'/embeds/',  # Generic embeds (LinkedIn native-document, etc)
		# Video and media streaming
		'dms.licdn.com/playlist',  # LinkedIn video playlists
		'/playlist/vid/',  # Video playlist endpoints
		'media.licdn.com/dms',  # LinkedIn media delivery
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
		self._page_enabled_sessions.clear()
		self._frame_loading_state.clear()
		self._document_loaded.clear()
		self._page_loaded.clear()
		self._mutation_observer_injected.clear()
		self._cdp_handlers_registered = False

	async def on_BrowserStoppedEvent(self, event: BrowserStoppedEvent) -> None:
		"""Clean up on browser stop."""
		self.logger.debug('[TrafficWatchdog] Browser stopped, cleaning up traffic monitoring')
		self._pending_requests.clear()
		self._last_activity.clear()
		self._session_to_target.clear()
		self._network_enabled_sessions.clear()
		self._page_enabled_sessions.clear()
		self._frame_loading_state.clear()
		self._document_loaded.clear()
		self._page_loaded.clear()
		self._mutation_observer_injected.clear()
		self._cdp_handlers_registered = False

	async def on_TabCreatedEvent(self, event: TabCreatedEvent) -> None:
		"""Enable Network and Page domains for new tabs."""
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
			if event.target_id not in self._frame_loading_state:
				self._frame_loading_state[event.target_id] = {}
			if event.target_id not in self._document_loaded:
				self._document_loaded[event.target_id] = False
			if event.target_id not in self._page_loaded:
				self._page_loaded[event.target_id] = False

			# Enable Network domain if not already enabled
			if cdp_session.session_id not in self._network_enabled_sessions:
				await cdp_session.cdp_client.send.Network.enable(session_id=cdp_session.session_id)
				self._network_enabled_sessions.add(cdp_session.session_id)
				self.logger.debug(f'[TrafficWatchdog] Enabled Network domain for tab {event.target_id[-4:]}')

			# Enable Page domain if not already enabled (for load events and frame tracking)
			if cdp_session.session_id not in self._page_enabled_sessions:
				await cdp_session.cdp_client.send.Page.enable(session_id=cdp_session.session_id)
				self._page_enabled_sessions.add(cdp_session.session_id)
				self.logger.debug(f'[TrafficWatchdog] Enabled Page domain for tab {event.target_id[-4:]}')

			# Register CDP handlers (only once globally)
			if not self._cdp_handlers_registered:
				self._register_cdp_handlers()
				self._cdp_handlers_registered = True
				self.logger.debug('[TrafficWatchdog] Registered CDP Network and Page event handlers')

		except Exception as e:
			self.logger.warning(f'[TrafficWatchdog] Failed to enable domains for tab {event.target_id[-4:]}: {e}')

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
		"""Reset pending requests and loading states on navigation start."""
		target_id = event.target_id
		if target_id in self._pending_requests:
			self.logger.debug(
				f'[TrafficWatchdog] Navigation started to {event.url}, resetting {len(self._pending_requests[target_id])} pending requests for target {target_id[-4:]}'
			)
			self._pending_requests[target_id].clear()
		else:
			self._pending_requests[target_id] = {}

		# Reset loading states
		self._frame_loading_state[target_id] = {}
		self._document_loaded[target_id] = False
		self._page_loaded[target_id] = False
		self._mutation_observer_injected[target_id] = False  # Need to re-inject on new page
		self._last_activity[target_id] = asyncio.get_event_loop().time()

	async def on_NavigationCompleteEvent(self, event: NavigationCompleteEvent) -> None:
		"""Navigation complete - could trigger network stability check here if needed."""
		target_id = event.target_id
		pending_count = len(self._pending_requests.get(target_id, {}))
		self.logger.debug(
			f'[TrafficWatchdog] Navigation complete to {event.url}, {pending_count} pending requests for target {target_id[-4:]}'
		)

	def _register_cdp_handlers(self) -> None:
		"""Register CDP Network and Page domain event handlers."""
		cdp_client = self.browser_session.cdp_client

		# Register Network event handlers using cdp-use's register API
		cdp_client.register.Network.requestWillBeSent(self._on_request_will_be_sent)  # type: ignore
		cdp_client.register.Network.responseReceived(self._on_response_received)  # type: ignore
		cdp_client.register.Network.loadingFinished(self._on_loading_finished)  # type: ignore
		cdp_client.register.Network.loadingFailed(self._on_loading_failed)  # type: ignore

		# Register Page event handlers for document/iframe loading states
		cdp_client.register.Page.domContentEventFired(self._on_dom_content_loaded)  # type: ignore
		cdp_client.register.Page.loadEventFired(self._on_page_load_complete)  # type: ignore
		cdp_client.register.Page.frameStoppedLoading(self._on_frame_stopped_loading)  # type: ignore

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

	async def _on_dom_content_loaded(self, event: dict, session_id: SessionID | None) -> None:
		"""Handle CDP Page.domContentEventFired - DOM parsing complete."""
		try:
			if not session_id or session_id not in self._session_to_target:
				return
			target_id = self._session_to_target[session_id]

			self._document_loaded[target_id] = True
			self._last_activity[target_id] = asyncio.get_event_loop().time()
			self.logger.debug(f'[TrafficWatchdog] DOMContentLoaded fired for target {target_id[-4:]}')

		except Exception as e:
			self.logger.debug(f'[TrafficWatchdog] Error in _on_dom_content_loaded: {e}')

	async def _on_page_load_complete(self, event: dict, session_id: SessionID | None) -> None:
		"""Handle CDP Page.loadEventFired - window.onload complete."""
		try:
			if not session_id or session_id not in self._session_to_target:
				return
			target_id = self._session_to_target[session_id]

			self._page_loaded[target_id] = True
			self._last_activity[target_id] = asyncio.get_event_loop().time()
			self.logger.debug(f'[TrafficWatchdog] Page load complete for target {target_id[-4:]}')

		except Exception as e:
			self.logger.debug(f'[TrafficWatchdog] Error in _on_page_load_complete: {e}')

	async def _on_frame_stopped_loading(self, event: dict, session_id: SessionID | None) -> None:
		"""Handle CDP Page.frameStoppedLoading - iframe finished loading."""
		try:
			if not session_id or session_id not in self._session_to_target:
				return
			target_id = self._session_to_target[session_id]

			frame_id = event.get('frameId', '')
			if frame_id and target_id in self._frame_loading_state:
				self._frame_loading_state[target_id][frame_id] = False
				self._last_activity[target_id] = asyncio.get_event_loop().time()
				# self.logger.debug(f'[TrafficWatchdog] Frame {frame_id[-8:]} stopped loading on target {target_id[-4:]}')

		except Exception as e:
			self.logger.debug(f'[TrafficWatchdog] Error in _on_frame_stopped_loading: {e}')

	async def _inject_mutation_observer(self, target_id: TargetID) -> bool:
		"""Inject DOM mutation observer to track when page stops updating.

		This is THE critical check - catches client-side rendering that happens
		after all network requests complete (React/Vue/etc).

		Returns:
			True if injection successful, False otherwise
		"""
		try:
			cdp_session = await self.browser_session.get_or_create_cdp_session(target_id, focus=False)

			# Inject mutation observer that tracks last DOM change time
			injection_script = """
			(function() {
				if (window.__browser_use_mutation_observer) return; // Already injected

				window.__browser_use_last_mutation = Date.now();
				window.__browser_use_mutation_observer = new MutationObserver(() => {
					window.__browser_use_last_mutation = Date.now();
				});

				// Observe all DOM changes
				window.__browser_use_mutation_observer.observe(document.body || document.documentElement, {
					childList: true,
					subtree: true,
					attributes: true,
					characterData: true,
					attributeOldValue: false,
					characterDataOldValue: false
				});
			})();
			"""

			await cdp_session.cdp_client.send.Runtime.evaluate(
				params={'expression': injection_script, 'awaitPromise': False}, session_id=cdp_session.session_id
			)

			self._mutation_observer_injected[target_id] = True
			self.logger.debug(f'[TrafficWatchdog] Injected mutation observer for target {target_id[-4:]}')
			return True

		except Exception as e:
			self.logger.debug(f'[TrafficWatchdog] Failed to inject mutation observer: {e}')
			return False

	async def _check_dom_stable(self, target_id: TargetID, stable_threshold_ms: float = 200) -> bool:
		"""Check if DOM has been stable (no mutations) for threshold duration.

		Args:
			target_id: Target to check
			stable_threshold_ms: Milliseconds without mutations to consider stable

		Returns:
			True if DOM stable, False if still mutating or check failed
		"""
		try:
			cdp_session = await self.browser_session.get_or_create_cdp_session(target_id, focus=False)

			# Check time since last mutation
			check_script = f"""
			(function() {{
				if (!window.__browser_use_last_mutation) return true; // No observer, assume stable
				const elapsed = Date.now() - window.__browser_use_last_mutation;
				return elapsed > {stable_threshold_ms};
			}})();
			"""

			result = await cdp_session.cdp_client.send.Runtime.evaluate(
				params={'expression': check_script, 'returnByValue': True}, session_id=cdp_session.session_id
			)

			is_stable = result.get('result', {}).get('value', False)
			return bool(is_stable)

		except Exception as e:
			self.logger.debug(f'[TrafficWatchdog] DOM stable check failed: {e}')
			return True  # Assume stable if check fails (don't block)

	async def _check_loading_indicators(self, target_id: TargetID) -> bool:
		"""Check if page has visible loading indicators (spinners, skeletons, etc).

		Returns:
			True if NO loading indicators found (ready), False if still loading
		"""
		try:
			cdp_session = await self.browser_session.get_or_create_cdp_session(target_id, focus=False)

			# Check for common loading patterns
			check_script = """
			(function() {
				// Check for ARIA busy states
				if (document.querySelector('[aria-busy="true"]')) return true;

				// Check for common loading class/id patterns
				const loadingSelectors = [
					'[class*="loading"]',
					'[class*="spinner"]',
					'[class*="skeleton"]',
					'[id*="loading"]',
					'[data-loading="true"]'
				];

				for (const selector of loadingSelectors) {
					const el = document.querySelector(selector);
					if (el && window.getComputedStyle(el).display !== 'none') {
						return true; // Found visible loading indicator
					}
				}

				// Check for loading text in body (case-insensitive)
				const bodyText = document.body?.textContent || '';
				if (/loading|please wait|cargando|chargement/i.test(bodyText.slice(0, 500))) {
					return true; // Found loading text
				}

				return false; // No loading indicators
			})();
			"""

			result = await cdp_session.cdp_client.send.Runtime.evaluate(
				params={'expression': check_script, 'returnByValue': True}, session_id=cdp_session.session_id
			)

			has_loaders = result.get('result', {}).get('value', False)
			return not has_loaders  # Return True if NO loaders (ready)

		except Exception as e:
			self.logger.debug(f'[TrafficWatchdog] Loading indicator check failed: {e}')
			return True  # Assume no loaders if check fails (don't block)

	async def wait_for_stable_network(
		self,
		target_id: TargetID,
		idle_time: float | None = None,
		safety_timeout: float = 3.0,  # Quick safety timeout - trust network/browser signals
	) -> NetworkStabilizedEvent:
		"""Wait for page to be fully stable and ready for interaction.

		Speed-optimized approach:
		- Phase 1 (required): Network idle + browser lifecycle complete
		- Phase 2 (optional): DOM stability + loading indicators (with aggressive timeout)

		Returns immediately when Phase 1 is satisfied, with Phase 2 as best-effort.

		Args:
			target_id: Target ID to wait for stability (required)
			idle_time: Seconds of no network activity to consider stable
			safety_timeout: Quick timeout for extra checks (default 3s)

		Returns:
			NetworkStabilizedEvent with stability status
		"""
		# Use browser profile defaults if not specified
		idle_time = idle_time or self.browser_session.browser_profile.wait_for_network_idle_page_load_time

		# Initialize target state if it doesn't exist
		if target_id not in self._pending_requests:
			self._pending_requests[target_id] = {}
		if target_id not in self._last_activity:
			self._last_activity[target_id] = asyncio.get_event_loop().time()

		start_time = asyncio.get_event_loop().time()
		timed_out = False

		# Inject mutation observer once (idempotent)
		if not self._mutation_observer_injected.get(target_id):
			await self._inject_mutation_observer(target_id)

		self.logger.debug(f'[TrafficWatchdog] Waiting for page stability on target {target_id[-4:]} (idle_time={idle_time}s)')

		# Track when Phase 1 was satisfied
		phase1_satisfied_at: float | None = None
		phase2_timeout = 1.5  # Max 1.5s to wait for Phase 2 after Phase 1 is satisfied

		try:
			while True:
				await asyncio.sleep(0.05)  # Fast polling
				now = asyncio.get_event_loop().time()

				# === Phase 1: Network & Browser State (REQUIRED) ===
				target_pending = self._pending_requests.get(target_id, {})
				target_last_activity = self._last_activity.get(target_id, start_time)

				doc_loaded = self._document_loaded.get(target_id, True)
				page_loaded = self._page_loaded.get(target_id, True)

				frames_loading = self._frame_loading_state.get(target_id, {})
				any_frame_loading = any(is_loading for is_loading in frames_loading.values())

				network_idle = len(target_pending) == 0
				time_idle = (now - target_last_activity) >= idle_time
				browser_loaded = doc_loaded and page_loaded and not any_frame_loading

				phase1_satisfied = network_idle and time_idle and browser_loaded

				# === Phase 2: DOM Stability (OPTIONAL - best effort) ===
				if phase1_satisfied:
					# Mark when Phase 1 was first satisfied
					if phase1_satisfied_at is None:
						phase1_satisfied_at = now
						self.logger.debug(
							f'[TrafficWatchdog] ✅ Phase 1 complete for {target_id[-4:]} at {now - start_time:.2f}s - checking Phase 2...'
						)

					# Try Phase 2 checks with aggressive timeout
					phase2_elapsed = now - phase1_satisfied_at
					if phase2_elapsed < phase2_timeout:
						# Quick checks for DOM stability and loading indicators
						no_loading_indicators = await self._check_loading_indicators(target_id)
						dom_stable = await self._check_dom_stable(target_id, stable_threshold_ms=200)

						# Perfect! Both phases satisfied
						if no_loading_indicators and dom_stable:
							self.logger.debug(
								f'[TrafficWatchdog] ✅ Phase 2 complete for {target_id[-4:]} at {now - start_time:.2f}s '
								f'(total: {now - start_time:.2f}s, phase2_elapsed: {phase2_elapsed:.2f}s)'
							)
							break
					else:
						# Phase 2 timeout - give up and return (Phase 1 was satisfied)
						self.logger.debug(
							f'[TrafficWatchdog] ⏱️ Phase 2 timeout for {target_id[-4:]} after {phase2_elapsed:.2f}s - returning anyway (Phase 1 satisfied)'
						)
						break

				# Overall safety timeout (should rarely hit)
				if now - start_time > safety_timeout:
					if not phase1_satisfied:
						# This is concerning - Phase 1 never satisfied
						pending_urls = [str(req.get('url', ''))[:50] for _, req in list(target_pending.items())[:3]]
						self.logger.warning(
							f'[TrafficWatchdog] ⚠️ Safety timeout at {safety_timeout}s - Phase 1 NOT satisfied! '
							f'(network_idle={network_idle}, time_idle={time_idle}, browser_loaded={browser_loaded}, pending={len(target_pending)}, urls={pending_urls})'
						)
					else:
						# Phase 1 satisfied but Phase 2 taking too long - this is OK
						self.logger.debug(
							f'[TrafficWatchdog] ⏱️ Safety timeout at {safety_timeout}s - Phase 1 satisfied, Phase 2 incomplete'
						)
					timed_out = not phase1_satisfied  # Only mark as timeout if Phase 1 failed
					break

		except Exception as e:
			self.logger.warning(f'[TrafficWatchdog] Error during stability check: {e}')
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
