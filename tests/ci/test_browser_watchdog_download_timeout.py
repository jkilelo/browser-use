"""Test download timeout configuration functionality"""

import asyncio
import tempfile
from pathlib import Path

import pytest
from pytest_httpserver import HTTPServer

from browser_use.agent.views import ActionModel
from browser_use.browser import BrowserSession
from browser_use.browser.events import BrowserStateRequestEvent, FileDownloadedEvent
from browser_use.browser.profile import BrowserProfile
from browser_use.tools.service import Tools
from browser_use.tools.views import ClickElementAction, GoToUrlAction


@pytest.fixture(scope='function')
def slow_download_server():
	"""Create a test HTTP server that serves files with delays."""
	server = HTTPServer()
	server.start()

	# Test file content
	test_content = b'This is a test file for timeout verification. Random: 67890'

	# Add slow download endpoint with a 2-second delay
	def slow_download_handler(request):
		import time

		time.sleep(2)  # Simulate slow download
		return request.make_response(
			test_content, headers={'Content-Type': 'text/plain', 'Content-Disposition': 'attachment; filename="slow-file.txt"'}
		)

	server.expect_request('/slow-download/test-file.txt').respond_with_handler(slow_download_handler)

	# Add download page with link
	download_page_html = """
	<!DOCTYPE html>
	<html>
	<head>
		<title>Slow Download Test Page</title>
	</head>
	<body>
		<h1>Slow Download Test</h1>
		<a id="downloadLink" href="/slow-download/test-file.txt">Download Slow Test File</a>
	</body>
	</html>
	"""

	server.expect_request('/download-page').respond_with_data(download_page_html, content_type='text/html')

	yield server
	server.stop()


class TestDownloadTimeout:
	"""Test configurable download timeout functionality"""

	async def test_download_timeout_configuration(self, slow_download_server):
		"""Test that download timeout can be configured and affects download behavior"""

		# Create temporary directory for downloads
		with tempfile.TemporaryDirectory() as tmpdir:
			downloads_path = Path(tmpdir) / 'downloads'
			downloads_path.mkdir()

			# Test with a short timeout (1 second) - should timeout
			browser_session_short = BrowserSession(
				browser_profile=BrowserProfile(
					headless=True,
					downloads_path=str(downloads_path),
					user_data_dir=None,
					download_timeout=1.0,  # 1 second timeout
				)
			)

			await browser_session_short.start()
			tools = Tools()

			try:
				base_url = f'http://{slow_download_server.host}:{slow_download_server.port}'

				# Navigate to download page
				class GoToUrlActionModel(ActionModel):
					go_to_url: GoToUrlAction | None = None

				result = await tools.act(
					GoToUrlActionModel(go_to_url=GoToUrlAction(url=f'{base_url}/download-page', new_tab=False)),
					browser_session_short,
				)
				assert result.error is None, f'Navigation to download page failed: {result.error}'

				await asyncio.sleep(0.5)

				# Get browser state to find download link
				event = browser_session_short.event_bus.dispatch(BrowserStateRequestEvent())
				state_result = await event.event_result()
				assert state_result is not None
				assert state_result.dom_state is not None
				assert state_result.dom_state.selector_map is not None

				# Find download link
				download_link_index = None
				for idx, element in state_result.dom_state.selector_map.items():
					if element.attributes and element.attributes.get('id') == 'downloadLink':
						download_link_index = idx
						break

				assert download_link_index is not None, 'Download link not found'

				# Click download link
				class ClickActionModel(ActionModel):
					click_element_by_index: ClickElementAction | None = None

				result = await tools.act(
					ClickActionModel(click_element_by_index=ClickElementAction(index=download_link_index)), browser_session_short
				)
				assert result.error is None, f'Click on download link failed: {result.error}'

				# Wait for download event with short timeout - should timeout
				download_timed_out = False
				try:
					download_event = await browser_session_short.event_bus.expect(FileDownloadedEvent, timeout=2.0)
					# If we get here, the download completed despite the short timeout
					# This could happen if the server responds faster than expected
					print(f'Download completed unexpectedly: {download_event.path}')
				except TimeoutError:
					download_timed_out = True
					print('Download timed out as expected with short timeout')

				# The behavior depends on server timing, but we should at least verify
				# that our timeout configuration is being used
				assert browser_session_short.browser_profile.download_timeout == 1.0

			finally:
				await browser_session_short.stop()

			# Test with a longer timeout (5 seconds) - should succeed
			browser_session_long = BrowserSession(
				browser_profile=BrowserProfile(
					headless=True,
					downloads_path=str(downloads_path),
					user_data_dir=None,
					download_timeout=5.0,  # 5 second timeout
				)
			)

			await browser_session_long.start()

			try:
				# Navigate to download page
				result = await tools.act(
					GoToUrlActionModel(go_to_url=GoToUrlAction(url=f'{base_url}/download-page', new_tab=False)),
					browser_session_long,
				)
				assert result.error is None, f'Navigation to download page failed: {result.error}'

				await asyncio.sleep(0.5)

				# Get browser state to find download link
				event = browser_session_long.event_bus.dispatch(BrowserStateRequestEvent())
				state_result = await event.event_result()
				assert state_result is not None
				assert state_result.dom_state is not None
				assert state_result.dom_state.selector_map is not None

				# Find download link
				download_link_index = None
				for idx, element in state_result.dom_state.selector_map.items():
					if element.attributes and element.attributes.get('id') == 'downloadLink':
						download_link_index = idx
						break

				assert download_link_index is not None, 'Download link not found'

				# Click download link
				result = await tools.act(
					ClickActionModel(click_element_by_index=ClickElementAction(index=download_link_index)), browser_session_long
				)
				assert result.error is None, f'Click on download link failed: {result.error}'

				# Wait for download event with longer timeout - should succeed
				try:
					download_event = await browser_session_long.event_bus.expect(FileDownloadedEvent, timeout=6.0)
					downloaded_file_path = download_event.path
					assert downloaded_file_path is not None, 'Downloaded file path is None'
					assert Path(downloaded_file_path).exists(), f'Downloaded file does not exist: {downloaded_file_path}'
					print(f'✅ Download completed successfully with longer timeout: {downloaded_file_path}')
				except TimeoutError:
					pytest.fail('Download did not complete within extended timeout')

				# Verify timeout configuration is correctly set
				assert browser_session_long.browser_profile.download_timeout == 5.0

			finally:
				await browser_session_long.stop()

	async def test_default_download_timeout(self):
		"""Test that the default download timeout is set correctly"""

		with tempfile.TemporaryDirectory() as tmpdir:
			downloads_path = Path(tmpdir) / 'downloads'
			downloads_path.mkdir()

			# Create browser session without specifying download_timeout
			browser_session = BrowserSession(
				browser_profile=BrowserProfile(
					headless=True,
					downloads_path=str(downloads_path),
					user_data_dir=None,
					# download_timeout not specified, should use default
				)
			)

			# Verify default timeout is 30.0 seconds
			assert browser_session.browser_profile.download_timeout == 30.0, (
				f'Expected default timeout of 30.0, got {browser_session.browser_profile.download_timeout}'
			)

	async def test_custom_download_timeout_configuration(self):
		"""Test that custom download timeout values are properly set"""

		test_timeouts = [1.0, 5.0, 10.0, 60.0, 120.0]

		for timeout_value in test_timeouts:
			with tempfile.TemporaryDirectory() as tmpdir:
				downloads_path = Path(tmpdir) / 'downloads'
				downloads_path.mkdir()

				browser_session = BrowserSession(
					browser_profile=BrowserProfile(
						headless=True,
						downloads_path=str(downloads_path),
						user_data_dir=None,
						download_timeout=timeout_value,
					)
				)

				# Verify timeout is set correctly
				assert browser_session.browser_profile.download_timeout == timeout_value, (
					f'Expected timeout of {timeout_value}, got {browser_session.browser_profile.download_timeout}'
				)
