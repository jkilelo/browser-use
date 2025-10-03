"""
Test with REAL browser-use data from Amazon:
1. Capture actual screenshot + DOM from browser-use
2. Test TTFT with real data
3. Compare flash-latest vs flash-lite-latest
"""
import asyncio
import os
import time
import base64
from dotenv import load_dotenv
from google import genai
from google.genai import types
from browser_use import Agent
from browser_use.llm.google import ChatGoogle

load_dotenv()

async def capture_real_data():
	"""Capture real screenshot and DOM from Amazon using browser-use"""
	print("🌐 Capturing real data from Amazon...")

	# Use flash-lite for the capture (faster)
	llm = ChatGoogle(
		model='gemini-flash-lite-latest',
		api_key=os.getenv('GOOGLE_API_KEY'),
		temperature=0.0
	)

	agent = Agent(
		task='Go to amazon.com',
		llm=llm,
		max_steps=1
	)

	# Run agent to get to Amazon
	await agent.run()

	# Get the browser session
	session = agent.browser_session

	if not session or not session.page:
		raise RuntimeError("Failed to get browser session")

	# Get screenshot (default format is jpeg)
	print("  📸 Taking screenshot...")
	screenshot_base64 = await session.page.screenshot(format='jpeg')

	# Get DOM content
	print("  📄 Extracting DOM...")
	dom_service = agent.dom_service
	dom_state = await dom_service.extract_dom_state()

	# Get text representation of DOM
	dom_text = str(dom_state)

	# Save for inspection
	with open('/tmp/amazon_screenshot.jpg', 'wb') as f:
		# Remove data URL prefix if present
		if screenshot_base64.startswith('data:'):
			screenshot_base64 = screenshot_base64.split(',', 1)[1]
		f.write(base64.b64decode(screenshot_base64))

	with open('/tmp/amazon_dom.txt', 'w') as f:
		f.write(dom_text)

	print(f"  ✅ Captured screenshot ({len(screenshot_base64)} chars) and DOM ({len(dom_text)} chars)")
	print(f"  💾 Saved to /tmp/amazon_screenshot.jpg and /tmp/amazon_dom.txt")

	await session.close()

	return screenshot_base64, dom_text

async def test_ttft_with_real_data(
	model_name: str,
	screenshot_base64: str,
	dom_text: str,
	run_number: int = 1,
) -> dict:
	"""Test TTFT with real browser-use data"""

	client = genai.Client(api_key=os.getenv('GOOGLE_API_KEY'))

	# Real browser-use task
	task = "Click on the search bar and search for 'laptop'"

	prompt = f"""{dom_text}

Task: {task}

Respond with JSON action array."""

	# Browser-use schema
	schema = {
		'type': 'object',
		'properties': {
			'action': {
				'type': 'array',
				'items': {
					'type': 'object',
					'properties': {
						'click': {
							'type': 'object',
							'properties': {
								'index': {'type': 'integer'}
							}
						},
						'input_text': {
							'type': 'object',
							'properties': {
								'index': {'type': 'integer'},
								'text': {'type': 'string'}
							}
						}
					}
				}
			}
		},
		'required': ['action']
	}

	config = types.GenerateContentConfig(
		temperature=0.0,
		response_mime_type='application/json',
		response_schema=schema,
		thinking_config={'thinking_budget': 0},
	)

	# Decode screenshot
	if screenshot_base64.startswith('data:'):
		screenshot_base64 = screenshot_base64.split(',', 1)[1]
	screenshot_bytes = base64.b64decode(screenshot_base64)

	# Build content with real screenshot
	parts = [
		types.Part(text=prompt),
		types.Part(
			inline_data=types.Blob(
				mime_type='image/jpeg',
				data=screenshot_bytes
			)
		)
	]

	content = types.Content(role='user', parts=parts)

	# Measure TTFT
	start = time.time()

	stream = await client.aio.models.generate_content_stream(
		model=model_name,
		contents=[content],
		config=config,
	)

	first_chunk_time = None

	async for chunk in stream:
		if chunk.text and first_chunk_time is None:
			first_chunk_time = time.time() - start
			break

	# Consume remaining chunks
	async for _ in stream:
		pass

	return {
		'model': model_name,
		'ttft': first_chunk_time,
		'run': run_number,
	}

async def main():
	"""Test with real browser-use data"""

	print("="*100)
	print("Real Browser-Use TTFT Test - Amazon.com")
	print("="*100)
	print()

	# Capture real data
	screenshot_base64, dom_text = await capture_real_data()

	print()
	print("Testing TTFT with real Amazon data:")
	print(f"  - Screenshot size: {len(screenshot_base64)} base64 chars ({len(base64.b64decode(screenshot_base64.split(',')[1] if screenshot_base64.startswith('data:') else screenshot_base64)) // 1024}KB)")
	print(f"  - DOM size: {len(dom_text)} chars")
	print(f"  - Models: gemini-flash-latest, gemini-flash-lite-latest")
	print(f"  - Runs: 5 per model")
	print()

	models = [
		'gemini-flash-latest',
		'gemini-flash-lite-latest',
	]
	runs_per_model = 5

	results = []
	total_tests = len(models) * runs_per_model
	test_num = 0

	for model_name in models:
		for run in range(1, runs_per_model + 1):
			test_num += 1

			print(f"[{test_num}/{total_tests}] {model_name}, run #{run}...", end=' ', flush=True)

			try:
				result = await test_ttft_with_real_data(model_name, screenshot_base64, dom_text, run)
				results.append(result)
				print(f"TTFT: {result['ttft']:.3f}s")
			except Exception as e:
				print(f"ERROR: {e}")

			await asyncio.sleep(1.0)

	# Analysis
	print()
	print("="*100)
	print("RESULTS")
	print("="*100)
	print()

	print(f"{'Model':<30} {'Run':<5} {'TTFT':<10}")
	print("-"*50)

	for result in results:
		print(
			f"{result['model']:<30} "
			f"#{result['run']:<4} "
			f"{result['ttft']:.3f}s"
		)

	print()
	print("="*100)
	print("ANALYSIS")
	print("="*100)
	print()

	for model_name in models:
		model_results = [r for r in results if r['model'] == model_name]
		if model_results:
			ttfts = [r['ttft'] for r in model_results]
			avg = sum(ttfts) / len(ttfts)
			min_ttft = min(ttfts)
			max_ttft = max(ttfts)
			stddev = (sum((x - avg) ** 2 for x in ttfts) / len(ttfts)) ** 0.5

			print(f"📊 {model_name}:")
			print(f"  Average TTFT: {avg:.3f}s")
			print(f"  Min TTFT: {min_ttft:.3f}s")
			print(f"  Max TTFT: {max_ttft:.3f}s")
			print(f"  Std Dev: {stddev:.3f}s")
			print()

	# Compare
	flash_latest = [r['ttft'] for r in results if r['model'] == 'gemini-flash-latest']
	flash_lite = [r['ttft'] for r in results if r['model'] == 'gemini-flash-lite-latest']

	if flash_latest and flash_lite:
		avg_latest = sum(flash_latest) / len(flash_latest)
		avg_lite = sum(flash_lite) / len(flash_lite)
		diff = avg_latest - avg_lite
		pct = (diff / avg_latest) * 100

		print(f"📊 Comparison:")
		print(f"  flash-latest: {avg_latest:.3f}s avg")
		print(f"  flash-lite: {avg_lite:.3f}s avg")
		print(f"  Difference: {diff:.3f}s ({pct:.1f}% faster)")
		print()

		if avg_lite < avg_latest:
			print(f"✅ flash-lite is {pct:.1f}% faster with REAL browser-use data!")
		else:
			print(f"⚠️  flash-latest is faster by {-pct:.1f}%")

	print()
	print("✅ Analysis complete!")

if __name__ == '__main__':
	asyncio.run(main())
