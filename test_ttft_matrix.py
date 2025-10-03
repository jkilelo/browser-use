"""
TTFT matrix test:
- Models: gemini-flash-latest, gemini-flash-lite-latest
- Input sizes: 10k, 40k chars
- Vision: with/without
- 5 runs per configuration
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

def create_text(size_chars: int, unique_id: int = 1) -> str:
	"""Create text of specified size with unique content per run to avoid caching"""
	import random
	import time

	# Add multiple unique elements per run to ensure no caching
	timestamp = int(time.time() * 1000000)  # microsecond precision
	random_val = random.randint(100000, 999999)
	unique_prefix = f"<!-- Test ID: {unique_id} | Timestamp: {timestamp} | Random: {random_val} -->\n"

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
	input_size: int,
	with_vision: bool,
	run_number: int = 1,
	unique_id: int = 1,
) -> dict:
	"""Measure TTFT only"""

	client = genai.Client(api_key=os.getenv('GOOGLE_API_KEY'))

	# Create input with unique content per run to avoid caching
	text = create_text(input_size, unique_id)
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

	# Build content
	parts = [types.Part(text=prompt)]

	if with_vision:
		image_bytes = create_dummy_image((800, 600))
		parts.append(types.Part(
			inline_data=types.Blob(
				mime_type='image/png',
				data=image_bytes
			)
		))

	content = types.Content(role='user', parts=parts)

	# Measure TTFT only
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
			break  # Stop after first chunk

	# Consume remaining chunks to close stream properly
	async for _ in stream:
		pass

	return {
		'model': model_name,
		'input_size': input_size,
		'with_vision': with_vision,
		'ttft': first_chunk_time,
		'run': run_number,
	}

async def main():
	"""Measure TTFT matrix"""

	print("="*100)
	print("TTFT Matrix Measurement")
	print("="*100)
	print()
	print("Testing:")
	print("  - Models: gemini-flash-latest, gemini-flash-lite-latest")
	print("  - Input sizes: 10k, 40k chars")
	print("  - Vision: with/without 800x600 image")
	print("  - Runs: 5 per configuration (unique content to avoid caching)")
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
	input_sizes = [10000, 40000]
	vision_options = [False, True]
	runs_per_config = 5

	results = []
	total_tests = len(models) * len(input_sizes) * len(vision_options) * runs_per_config
	test_num = 0
	unique_id = 0  # Global counter to ensure unique input for every test

	for model_name in models:
		for input_size in input_sizes:
			for with_vision in vision_options:
				for run in range(1, runs_per_config + 1):
					test_num += 1
					unique_id += 1  # Increment for each test

					vision_str = "WITH vision" if with_vision else "NO vision"
					print(f"[{test_num}/{total_tests}] {model_name}, {input_size//1000}k, {vision_str}, run #{run} (ID:{unique_id})...", end=' ', flush=True)

					try:
						result = await measure_ttft(model_name, input_size, with_vision, run, unique_id)
						results.append(result)
						print(f"{result['ttft']:.3f}s")
					except Exception as e:
						print(f"ERROR: {e}")

					await asyncio.sleep(1.0)  # Pause to avoid rate limits

	# Analysis
	print()
	print("="*100)
	print("RESULTS")
	print("="*100)
	print()

	print(f"{'Model':<30} {'Input':<8} {'Vision':<10} {'Run':<5} {'TTFT':<10}")
	print("-"*70)

	for result in results:
		vision_str = "Yes" if result['with_vision'] else "No"
		print(
			f"{result['model']:<30} "
			f"{result['input_size']//1000}k{'':<6} "
			f"{vision_str:<10} "
			f"#{result['run']:<4} "
			f"{result['ttft']:.3f}s"
		)

	print()
	print("="*100)
	print("ANALYSIS")
	print("="*100)
	print()

	# Analyze by configuration
	for model_name in models:
		print(f"📊 {model_name}:")
		model_results = [r for r in results if r['model'] == model_name]

		for input_size in input_sizes:
			for with_vision in vision_options:
				matching = [
					r for r in model_results
					if r['input_size'] == input_size and r['with_vision'] == with_vision
				]

				if matching:
					ttfts = [r['ttft'] for r in matching]
					avg = sum(ttfts) / len(ttfts)
					min_ttft = min(ttfts)
					max_ttft = max(ttfts)
					stddev = (sum((x - avg) ** 2 for x in ttfts) / len(ttfts)) ** 0.5

					vision_label = "with vision" if with_vision else "no vision"
					print(f"  {input_size//1000}k chars, {vision_label}:")
					print(f"    Avg: {avg:.3f}s | Min: {min_ttft:.3f}s | Max: {max_ttft:.3f}s | StdDev: {stddev:.3f}s")

		print()

	# Cross-model comparisons
	print("="*100)
	print("CROSS-MODEL COMPARISON")
	print("="*100)
	print()

	for input_size in input_sizes:
		for with_vision in vision_options:
			vision_label = "with vision" if with_vision else "no vision"
			print(f"📊 {input_size//1000}k chars, {vision_label}:")

			for model_name in models:
				matching = [
					r for r in results
					if r['model'] == model_name and r['input_size'] == input_size and r['with_vision'] == with_vision
				]

				if matching:
					ttfts = [r['ttft'] for r in matching]
					avg = sum(ttfts) / len(ttfts)
					print(f"  {model_name}: {avg:.3f}s avg")

			# Calculate difference
			flash_latest = [
				r['ttft'] for r in results
				if r['model'] == 'gemini-flash-latest' and r['input_size'] == input_size and r['with_vision'] == with_vision
			]
			flash_lite = [
				r['ttft'] for r in results
				if r['model'] == 'gemini-flash-lite-latest' and r['input_size'] == input_size and r['with_vision'] == with_vision
			]

			if flash_latest and flash_lite:
				avg_latest = sum(flash_latest) / len(flash_latest)
				avg_lite = sum(flash_lite) / len(flash_lite)
				diff = avg_latest - avg_lite
				pct = (diff / avg_latest) * 100

				if avg_lite < avg_latest:
					print(f"  → flash-lite is {pct:.1f}% faster ({diff:.3f}s improvement)")
				else:
					print(f"  → flash-latest is {-pct:.1f}% faster ({-diff:.3f}s improvement)")

			print()

	print("✅ Analysis complete!")

if __name__ == '__main__':
	asyncio.run(main())
