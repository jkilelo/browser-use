"""
Focused TTFT measurement for 40k chars + vision:
- gemini-flash-latest vs gemini-flash-lite-latest
- 5 runs each to get reliable averages
- Only measure TTFT, stop after first chunk
"""
import asyncio
import os
import time
import base64
from io import BytesIO
from dotenv import load_dotenv
from google import genai
from google.genai import types

load_dotenv()

def create_dummy_image(size: tuple = (800, 600)) -> bytes:
	"""Create a dummy image of specified size"""
	try:
		from PIL import Image
		import random

		img = Image.new('RGB', size, color='red')
		pixels = img.load()
		for i in range(size[0]):
			for j in range(size[1]):
				noise = random.randint(-20, 20)
				pixels[i, j] = (max(0, min(255, 200 + noise)), noise % 50, noise % 30)

		buffer = BytesIO()
		img.save(buffer, format='PNG')
		return buffer.getvalue()
	except ImportError:
		return base64.b64decode(
			'iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8z8DwHwAFBQIAX8jx0gAAAABJRU5ErkJggg=='
		)

def create_text(size_chars: int, run_number: int = 1) -> str:
	"""Create text of specified size with unique content per run to avoid caching"""
	import random

	# Add unique prefix per run to ensure no caching
	unique_prefix = f"<!-- Test Run #{run_number} | Random: {random.randint(10000, 99999)} -->\n"

	base_text = """
<element id="{i}" clickable="true">
	<tag>div</tag>
	<text>Product item #{i} - Gaming Laptop with RTX 4090, 32GB RAM, 1TB SSD, Ultra HD Display</text>
	<attributes>
		<class>product-card search-result-item featured-product</class>
		<data-product-id>PROD-{i:05d}</data-product-id>
		<aria-label>Product {i} Gaming Laptop</aria-label>
		<data-price>$1299.99</data-price>
		<data-rating>4.5</data-rating>
	</attributes>
	<bbox>{{x: {x}, y: {y}, width: 300, height: 150}}</bbox>
</element>
"""

	text = unique_prefix + "Current Page DOM:\n"
	i = 0
	while len(text) < size_chars:
		text += base_text.format(i=i, x=i*10, y=i*50)
		i += 1

	return text[:size_chars]

async def measure_ttft(
	model_name: str,
	run_number: int = 1,
) -> dict:
	"""Measure TTFT only"""

	client = genai.Client(api_key=os.getenv('GOOGLE_API_KEY'))

	# Create input with unique content per run to avoid caching
	text = create_text(40000, run_number)
	task = "Click on the first product and add to cart."

	prompt = f"""{text}

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

	# Build content with vision
	image_bytes = create_dummy_image((800, 600))
	parts = [
		types.Part(text=prompt),
		types.Part(
			inline_data=types.Blob(
				mime_type='image/png',
				data=image_bytes
			)
		)
	]

	content = types.Content(role='user', parts=parts)

	# Measure TTFT only
	start = time.time()

	stream = await client.aio.models.generate_content_stream(
		model=model_name,
		contents=[content],
		config=config,
	)

	first_chunk_time = None
	first_chunk_text = ""

	async for chunk in stream:
		if chunk.text and first_chunk_time is None:
			first_chunk_time = time.time() - start
			first_chunk_text = chunk.text[:50]
			break  # Stop after first chunk

	# Consume remaining chunks to close stream properly
	async for _ in stream:
		pass

	return {
		'model': model_name,
		'ttft': first_chunk_time,
		'first_chunk_preview': first_chunk_text,
		'run': run_number,
	}

async def main():
	"""Measure TTFT repeatedly"""

	print("="*100)
	print("TTFT Measurement - 40k chars + vision")
	print("="*100)
	print()
	print("Testing:")
	print("  - Fixed input: 40k chars + 800x600 image")
	print("  - Models: gemini-flash-latest, gemini-flash-lite-latest")
	print("  - Runs: 5 per model (unique content to avoid caching)")
	print("  - Measure: TTFT only")
	print()

	# Try to import PIL
	try:
		from PIL import Image
	except ImportError:
		print("⚠️  Installing Pillow...")
		import subprocess
		subprocess.run(['uv', 'add', 'pillow'], check=True, capture_output=True)

	print()

	# Test configurations
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
				result = await measure_ttft(model_name, run)
				results.append(result)
				print(f"TTFT: {result['ttft']:.3f}s")
			except Exception as e:
				print(f"ERROR: {e}")

			await asyncio.sleep(1.0)  # Pause to avoid rate limits

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
			print(f"  Runs: {len(model_results)}")
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
			print(f"✅ flash-lite is {pct:.1f}% faster!")
		else:
			print(f"⚠️  flash-latest is faster by {-pct:.1f}%")

	print()
	print("✅ Analysis complete!")

if __name__ == '__main__':
	asyncio.run(main())
