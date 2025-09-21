"""
Example demonstrating configurable download timeout functionality.

This example shows how to configure download timeouts for different scenarios:
- Default timeout (30 seconds)
- Short timeout for quick downloads
- Long timeout for large files

Run with: uv run python examples/download_timeout_demo.py
"""

import asyncio
import tempfile

from browser_use.agent.service import Agent
from browser_use.browser.profile import BrowserProfile


async def demo_download_timeouts():
	"""Demonstrate different download timeout configurations."""

	# Example 1: Default timeout (30 seconds)
	print('🔧 Creating browser session with default download timeout...')
	default_profile = BrowserProfile(
		headless=True,
		# download_timeout not specified = 30.0 seconds default
	)
	print(f'   Default timeout: {default_profile.download_timeout} seconds')

	# Example 2: Short timeout for quick downloads
	print('\n🔧 Creating browser session with short download timeout...')
	with tempfile.TemporaryDirectory() as tmpdir:
		short_timeout_profile = BrowserProfile(
			headless=True,
			downloads_path=str(tmpdir),
			download_timeout=5.0,  # 5 seconds for quick downloads
		)
		print(f'   Short timeout: {short_timeout_profile.download_timeout} seconds')

		# Example 3: Long timeout for large files
		print('\n🔧 Creating browser session with long download timeout...')
		long_timeout_profile = BrowserProfile(
			headless=True,
			downloads_path=str(tmpdir),
			download_timeout=120.0,  # 2 minutes for large files
		)
		print(f'   Long timeout: {long_timeout_profile.download_timeout} seconds')

		# Example 4: Using with Agent
		print('\n🤖 Using custom timeout with Agent...')

		# Create an agent with custom download timeout
		agent = Agent(
			task='Download files from websites',
			browser_profile=BrowserProfile(
				headless=True,
				downloads_path=str(tmpdir),
				download_timeout=60.0,  # 1 minute timeout
				auto_download_pdfs=True,  # Enable PDF auto-download
			),
		)

		print(f'   Agent download timeout: {agent.browser_session.browser_profile.download_timeout} seconds')
		print(f'   PDF auto-download: {agent.browser_session.browser_profile.auto_download_pdfs}')

		# Note: In real usage, you would call agent.run() here
		print('\n✅ Configuration examples complete!')
		print('\n💡 Tips:')
		print('   - Use shorter timeouts (5-10s) for small files or fast connections')
		print('   - Use longer timeouts (60-300s) for large files or slow connections')
		print('   - The timeout applies to both regular downloads and PDF auto-downloads')
		print('   - Downloads that exceed the timeout will be cancelled')


if __name__ == '__main__':
	asyncio.run(demo_download_timeouts())
