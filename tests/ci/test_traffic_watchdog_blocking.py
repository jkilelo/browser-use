"""Test CDP-level URL blocking using TrafficWatchdog with EasyList patterns."""

import asyncio

import pytest


@pytest.mark.asyncio
async def test_easylist_patterns_loaded():
	"""Test that EasyList patterns are loaded correctly from the easylist file."""
	from browser_use.browser.watchdogs.traffic_watchdog import _load_easylist_patterns

	domains, url_patterns = _load_easylist_patterns()

	# Should load patterns from easylist file
	assert len(domains) > 0, 'Should load domain patterns from easylist file'
	assert len(url_patterns) > 0, 'Should generate CDP URL patterns'
	# Note: url_patterns may have more entries due to duplicates in easylist file
	assert len(url_patterns) >= len(domains), 'Should have at least as many URL patterns as domains'

	# Check format of URL patterns (should be *domain.com*)
	for pattern in list(url_patterns)[:5]:
		assert pattern.startswith('*'), 'URL patterns should start with *'
		assert pattern.endswith('*'), 'URL patterns should end with *'


@pytest.mark.asyncio
async def test_url_filtering_logic():
	"""Test that _should_track_request properly filters ad/tracking URLs."""
	from bubus import EventBus

	from browser_use.browser import BrowserProfile, BrowserSession
	from browser_use.browser.watchdogs.traffic_watchdog import TrafficWatchdog, _load_easylist_patterns

	# Create a browser session with TrafficWatchdog
	browser_profile = BrowserProfile(headless=True, user_data_dir=None)
	browser_session = BrowserSession(browser_profile=browser_profile)
	event_bus = EventBus()

	# Create watchdog and load patterns
	watchdog = TrafficWatchdog(browser_session=browser_session, event_bus=event_bus)
	watchdog._easylist_patterns, watchdog._blocked_url_patterns = _load_easylist_patterns()

	# Test that legitimate URLs are tracked
	assert watchdog._should_track_request('Document', 'https://example.com/page.html') is True
	assert watchdog._should_track_request('Script', 'https://example.com/app.js') is True
	assert watchdog._should_track_request('XHR', 'https://api.example.com/data') is True

	# Test that non-essential resource types are not tracked
	assert watchdog._should_track_request('Image', 'https://example.com/image.png') is False
	assert watchdog._should_track_request('Stylesheet', 'https://example.com/style.css') is False
	assert watchdog._should_track_request('Font', 'https://example.com/font.woff') is False

	# Test that data/blob URLs are not tracked
	assert watchdog._should_track_request('Script', 'data:text/javascript,console.log("test")') is False
	assert watchdog._should_track_request('Image', 'blob:https://example.com/image') is False

	# Test that known tracking patterns are filtered
	assert watchdog._should_track_request('Script', 'https://example.com/analytics.js') is False
	assert watchdog._should_track_request('Script', 'https://example.com/tracking/beacon') is False
	assert watchdog._should_track_request('XHR', 'https://doubleclick.net/ad') is False


@pytest.mark.asyncio
async def test_cdp_blocking_integration():
	"""Test that TrafficWatchdog loads patterns and initializes correctly."""
	from browser_use.browser import BrowserProfile, BrowserSession

	# Create browser session
	browser_profile = BrowserProfile(headless=True, user_data_dir=None)
	browser_session = BrowserSession(browser_profile=browser_profile)

	# Start browser
	await browser_session.start()

	try:
		# Get the traffic watchdog
		traffic_watchdog = browser_session._traffic_watchdog

		# Verify patterns were loaded during browser launch
		assert len(traffic_watchdog._easylist_patterns) > 0, 'EasyList patterns should be loaded'
		assert len(traffic_watchdog._blocked_url_patterns) > 0, 'CDP URL patterns should be generated'
		assert len(traffic_watchdog._blocked_url_patterns) >= len(
			traffic_watchdog._easylist_patterns
		), 'Should have at least as many URL patterns as domains'

		# Wait a moment for browser to fully initialize
		await asyncio.sleep(1.0)

		# After browser is running, check that watchdog is tracking the default tab
		assert len(traffic_watchdog._pending_requests) > 0, 'Should be tracking at least one tab'
		assert len(traffic_watchdog._last_activity) > 0, 'Should have activity tracking for at least one tab'

		# CDP handlers should be registered after first tab is created
		assert traffic_watchdog._cdp_handlers_registered is True, 'CDP handlers should be registered after browser starts'
		assert len(traffic_watchdog._network_enabled_sessions) > 0, 'Network domain should be enabled for at least one session'

		# Verify that for each tracked target, we have an empty pending request dict (no pending requests yet)
		for target_id, pending in traffic_watchdog._pending_requests.items():
			assert isinstance(pending, dict), f'Pending requests for {target_id} should be a dict'
			# The dict may be empty (no requests) or have some requests depending on timing

	finally:
		await browser_session.stop()
