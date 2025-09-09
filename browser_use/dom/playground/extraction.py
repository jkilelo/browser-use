import asyncio
import time

import anyio
import tiktoken

from browser_use.browser import BrowserProfile, BrowserSession
from browser_use.browser.profile import ViewportSize
from browser_use.dom.html_prettifier import HTMLPrettifier
from browser_use.dom.service import DomService

TIMEOUT = 60


async def test_focus_vs_all_elements():
	browser_session = BrowserSession(
		browser_profile=BrowserProfile(
			# executable_path='/Applications/Google Chrome.app/Contents/MacOS/Google Chrome',
			window_size=ViewportSize(width=1100, height=1000),
			disable_security=False,
			wait_for_network_idle_page_load_time=1,
			headless=False,
			args=['--incognito'],
			paint_order_filtering=True,
		),
	)

	# 10 Sample websites with various interactive elements
	sample_websites = [
		'https://www.google.com/travel/flights',
		'https://v0-simple-ui-test-site.vercel.app',
		'https://browser-use.github.io/stress-tests/challenges/iframe-inception-level1.html',
		'https://browser-use.github.io/stress-tests/challenges/angular-form.html',
		'https://www.google.com/travel/flights',
		'https://www.amazon.com/s?k=laptop',
		'https://github.com/trending',
		'https://www.reddit.com',
		'https://www.ycombinator.com/companies',
		'https://www.kayak.com/flights',
		'https://www.booking.com',
		'https://www.airbnb.com',
		'https://www.linkedin.com/jobs',
		'https://stackoverflow.com/questions',
	]

	# 5 Difficult websites with complex elements (iframes, canvas, dropdowns, etc.)
	difficult_websites = [
		'https://www.w3schools.com/html/tryit.asp?filename=tryhtml_iframe',  # Nested iframes
		'https://semantic-ui.com/modules/dropdown.html',  # Complex dropdowns
		'https://www.dezlearn.com/nested-iframes-example/',  # Cross-origin nested iframes
		'https://codepen.io/towc/pen/mJzOWJ',  # Canvas elements with interactions
		'https://jqueryui.com/accordion/',  # Complex accordion/dropdown widgets
		'https://v0-simple-landing-page-seven-xi.vercel.app/',  # Simple landing page with iframe
		'https://www.unesco.org/en',
	]

	# Descriptions for difficult websites
	difficult_descriptions = {
		'https://www.w3schools.com/html/tryit.asp?filename=tryhtml_iframe': '🔸 NESTED IFRAMES: Multiple iframe layers',
		'https://semantic-ui.com/modules/dropdown.html': '🔸 COMPLEX DROPDOWNS: Custom dropdown components',
		'https://www.dezlearn.com/nested-iframes-example/': '🔸 CROSS-ORIGIN IFRAMES: Different domain iframes',
		'https://codepen.io/towc/pen/mJzOWJ': '🔸 CANVAS ELEMENTS: Interactive canvas graphics',
		'https://jqueryui.com/accordion/': '🔸 ACCORDION WIDGETS: Collapsible content sections',
	}

	websites = sample_websites + difficult_websites
	current_website_index = 0

	def get_website_list_for_prompt() -> str:
		"""Get a compact website list for the input prompt."""
		lines = []
		lines.append('📋 Websites:')

		# Sample websites (1-10)
		for i, site in enumerate(sample_websites, 1):
			current_marker = ' ←' if (i - 1) == current_website_index else ''
			domain = site.replace('https://', '').split('/')[0]
			lines.append(f'  {i:2d}.{domain[:15]:<15}{current_marker}')

		# Difficult websites (11-15)
		for i, site in enumerate(difficult_websites, len(sample_websites) + 1):
			current_marker = ' ←' if (i - 1) == current_website_index else ''
			domain = site.replace('https://', '').split('/')[0]
			desc = difficult_descriptions.get(site, '')
			challenge = desc.split(': ')[1][:15] if ': ' in desc else ''
			lines.append(f'  {i:2d}.{domain[:15]:<15} ({challenge}){current_marker}')

		return '\n'.join(lines)

	await browser_session.start()

	# Show startup info
	print('\n🌐 BROWSER-USE DOM EXTRACTION TESTER')
	print(f'📊 {len(websites)} websites total: {len(sample_websites)} standard + {len(difficult_websites)} complex')
	print('🔧 Controls: Type 1-15 to jump | Enter to re-run | "n" next | "q" quit')
	print('💾 Outputs: tmp/user_message.txt & tmp/element_tree.json\n')

	dom_service = DomService(browser_session)

	while True:
		# Cycle through websites
		if current_website_index >= len(websites):
			current_website_index = 0
			print('Cycled back to first website!')

		website = websites[current_website_index]
		# sleep 2
		await browser_session._cdp_navigate(website)
		await asyncio.sleep(1)

		last_clicked_index = None  # Track the index for text input
		while True:
			try:
				# 	all_elements_state = await dom_service.get_serialized_dom_tree()

				website_type = 'DIFFICULT' if website in difficult_websites else 'SAMPLE'
				print(f'\n{"=" * 60}')
				print(f'[{current_website_index + 1}/{len(websites)}] [{website_type}] Testing: {website}')
				if website in difficult_descriptions:
					print(f'{difficult_descriptions[website]}')
				print(f'{"=" * 60}')

				# Get/refresh the state (includes removing old highlights)
				print('\nGetting page state...')

				start_time = time.time()
				all_elements_state = await browser_session.get_browser_state_summary(True)
				end_time = time.time()
				get_state_time = end_time - start_time
				print(f'get_state_summary took {get_state_time:.2f} seconds')

				# Get detailed timing info from DOM service
				print('\nGetting detailed DOM timing...')
				serialized_state, _, timing_info = await dom_service.get_serialized_dom_tree()

				llm_representation = serialized_state.llm_representation()

				# token count
				encoding = tiktoken.encoding_for_model('gpt-4o')
				token_count = len(encoding.encode(llm_representation))
				print(f'Token count: {token_count}')

				async with await anyio.open_file('tmp/dom_state.html', 'w', encoding='utf-8') as f:
					await f.write(llm_representation)

				# save formatted html as well
				async with await anyio.open_file('tmp/dom_state_formatted.html', 'w', encoding='utf-8') as f:
					await f.write(HTMLPrettifier().prettify(llm_representation))

				if input('Continue? (y/n)').lower() == 'n':
					break

			except Exception as e:
				print(f'Error in loop: {e}')
				# Optionally add a small delay before retrying
				await asyncio.sleep(1)


if __name__ == '__main__':
	asyncio.run(test_focus_vs_all_elements())
	# asyncio.run(test_process_html_file()) # Commented out the other test
