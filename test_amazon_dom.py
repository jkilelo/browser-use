"""Test script to verify DOM extraction on Amazon.in - diagnose why product elements are missing."""

import asyncio
import json
import os

import anyio

from browser_use.agent.service import Agent
from browser_use.browser import BrowserProfile, BrowserSession
from browser_use.browser.profile import ViewportSize
from browser_use.dom.service import DomService
from browser_use.dom.views import DEFAULT_INCLUDE_ATTRIBUTES


async def test_amazon_dom_extraction():
	"""
	Test what the code_use agent actually sees when scraping Amazon.in.
	This reproduces the exact failure: agent tries to extract products but gets 0 results.
	"""
	browser_session = BrowserSession(
		browser_profile=BrowserProfile(
			window_size=ViewportSize(width=1280, height=1024),
			disable_security=False,
			wait_for_network_idle_page_load_time=2,
			headless=False,
			args=['--incognito'],
			paint_order_filtering=True,
		),
	)

	await browser_session.start()
	dom_service = DomService(browser_session)

	url = 'https://www.amazon.in/s?k=watch+for+men'
	print(f'\n🌐 Navigating to: {url}')
	await browser_session._cdp_navigate(url)



	print('\n🔍 Getting DOM state (what the agent sees)...')
	all_elements_state = await browser_session.get_browser_state_summary(True)

	selector_map = all_elements_state.dom_state.selector_map
	total_elements = len(selector_map.keys())
	print(f'✅ Total interactive elements in selector_map: {total_elements}')

	print('\n📝 Getting eval serializer output...')
	dom_state = all_elements_state.dom_state
	serialized_state = dom_state.eval_representation()

	os.makedirs('./tmp', exist_ok=True)

	async with await anyio.open_file('./tmp/amazon_eval_serialized.txt', 'w', encoding='utf-8') as f:
		await f.write(serialized_state)
	print('💾 Saved eval serializer output to: ./tmp/amazon_eval_serialized.txt')

	print(f'\n📊 Eval serializer output length: {len(serialized_state)} chars')

	if all_elements_state.dom_state._root:
		async with await anyio.open_file('./tmp/amazon_simplified_tree.json', 'w', encoding='utf-8') as f:
			await f.write(json.dumps(all_elements_state.dom_state._root.__json__(), indent=2))
		print('💾 Saved simplified tree to: ./tmp/amazon_simplified_tree.json')

	print('\n🔎 Analyzing product-related elements in serialized DOM...')

	product_indicators = {
		'data-asin': serialized_state.count('data-asin'),
		's-result-item': serialized_state.count('s-result-item'),
		's-main-slot': serialized_state.count('s-main-slot'),
		'a-text-normal': serialized_state.count('a-text-normal'),
		'a-price': serialized_state.count('a-price'),
		'a-price-whole': serialized_state.count('a-price-whole'),
		'a-offscreen': serialized_state.count('a-offscreen'),
		'<h2': serialized_state.count('<h2'),
		'<div': serialized_state.count('<div'),
	}

	print('\n📋 Key Amazon selectors in eval serializer output:')
	for indicator, count in product_indicators.items():
		status = '✅' if count > 0 else '❌'
		print(f'  {status} {indicator:20s}: {count:4d} occurrences')

	if product_indicators['data-asin'] == 0:
		print('\n⚠️  CRITICAL: No data-asin attributes found!')
		print('   This means product containers are NOT in the serialized DOM.')
		print('   Agent will see 0 products when trying to extract.')
	else:
		print(f"\n✅ Found {product_indicators['data-asin']} data-asin attributes")

	product_containers = []
	product_titles = []
	product_prices = []

	for idx, node in selector_map.items():
		if node.attributes:
			if 'data-asin' in node.attributes and node.attributes.get('data-asin'):
				product_containers.append((idx, node.tag_name, node.attributes.get('data-asin')))

			classes = node.attributes.get('class', '').split()
			if 'a-text-normal' in classes:
				product_titles.append((idx, node.tag_name))

			if any(c in classes for c in ['a-price-whole', 'a-price', 'a-offscreen']):
				product_prices.append((idx, node.tag_name))

	print(f'\n📦 Interactive elements in selector_map:')
	print(f'  Product containers (data-asin): {len(product_containers)}')
	print(f'  Title elements (a-text-normal): {len(product_titles)}')
	print(f'  Price elements: {len(product_prices)}')

	if product_containers:
		print(f'\n📦 Sample product containers:')
		for idx, tag, asin in product_containers[:3]:
			print(f'  [{idx}] <{tag}> data-asin="{asin}"')

	print('\n📄 Sample of serialized DOM (first 3000 chars):')
	print(serialized_state[:3000])

	print('\n📄 Looking for product section in serialized DOM...')
	if 's-main-slot' in serialized_state:
		idx = serialized_state.find('s-main-slot')
		sample = serialized_state[max(0, idx-200):idx+2000]
		print(f'\nFound s-main-slot at position {idx}:')
		print(sample)
	elif 's-result-item' in serialized_state:
		idx = serialized_state.find('s-result-item')
		sample = serialized_state[max(0, idx-200):idx+2000]
		print(f'\nFound s-result-item at position {idx}:')
		print(sample)
	else:
		print('\n⚠️  Neither s-main-slot nor s-result-item found in serialized DOM!')
		print('   This confirms product elements are missing from agent\'s view.')

	print('\n' + '='*60)
	print('DIAGNOSIS SUMMARY:')
	print('='*60)
	if product_indicators['data-asin'] == 0 and len(product_containers) == 0:
		print('❌ CONFIRMED: Product elements are NOT in the serialized DOM')
		print('   The eval_serializer is missing the main product listing section')
		print('   This explains why the agent extracts 0 products')
	else:
		print('✅ Product elements ARE present in the DOM')
		print('   Issue must be with agent\'s extraction selectors')

	print('\n✅ Test complete! Check ./tmp/amazon_*.txt for full output.')

	await browser_session.close()


if __name__ == '__main__':
	asyncio.run(test_amazon_dom_extraction())
