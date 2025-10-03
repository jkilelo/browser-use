"""
Systematic test to understand Gemini TTFT bottlenecks:
1. Input size: 1k, 5k, 10k, 20k, 50k chars
2. Vision vs No vision
3. Measure TTFT for each combination
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
		# Fallback: create minimal PNG without PIL
		# This is a 1x1 red pixel PNG
		return base64.b64decode(
			'iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8z8DwHwAFBQIAX8jx0gAAAABJRU5ErkJggg=='
		)

def create_text(size_chars: int) -> str:
	"""Create text of specified size"""
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

	text = "Current Page DOM:\n"
	i = 0
	while len(text) < size_chars:
		text += base_text.format(i=i, x=i*10, y=i*50)
		i += 1

	return text[:size_chars]

async def test_single_config(
	input_size: int,
	with_vision: bool,
	run_number: int = 1
) -> dict:
	"""Test a single configuration"""

	client = genai.Client(api_key=os.getenv('GOOGLE_API_KEY'))

	# Create input
	text = create_text(input_size)

	# Simple task
	task = "Click on the first product and add to cart."

	prompt = f"""{text}

Task: {task}

Respond with JSON action array."""

	# Schema
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

	# Measure
	start = time.time()

	stream = await client.aio.models.generate_content_stream(
		model='gemini-2.0-flash-exp',
		contents=[content],
		config=config,
	)

	stream_create_time = time.time() - start

	# Get TTFT
	chunk_count = 0
	first_chunk_time = None

	async for chunk in stream:
		chunk_count += 1
		if chunk_count == 1 and chunk.text:
			first_chunk_time = time.time() - start
			break  # We only need TTFT

	# Consume remaining chunks
	async for _ in stream:
		pass

	return {
		'input_size': input_size,
		'with_vision': with_vision,
		'stream_create_time': stream_create_time,
		'ttft': first_chunk_time,
		'run': run_number
	}

async def main():
	"""Run systematic tests"""

	print("="*100)
	print("Systematic Gemini TTFT Analysis")
	print("="*100)
	print()
	print("Testing variables:")
	print("  - Input size: 1k, 5k, 10k, 20k, 50k characters")
	print("  - Vision: with/without image")
	print("  - Model: gemini-2.0-flash-exp")
	print("  - Runs: 2 per configuration")
	print()

	# Try to import PIL
	try:
		from PIL import Image
		print("✅ Pillow available for image generation")
	except ImportError:
		print("⚠️  Pillow not available, using fallback minimal image")
		import subprocess
		print("   Installing Pillow...")
		subprocess.run(['uv', 'add', 'pillow'], check=True, capture_output=True)
		print("✅ Pillow installed")

	print()

	# Test configurations
	input_sizes = [1000, 5000, 10000, 20000, 50000]
	vision_options = [False, True]
	runs_per_config = 2

	results = []
	total_tests = len(input_sizes) * len(vision_options) * runs_per_config
	test_num = 0

	for input_size in input_sizes:
		for with_vision in vision_options:
			for run in range(1, runs_per_config + 1):
				test_num += 1

				vision_str = "WITH vision" if with_vision else "NO vision"
				print(f"[{test_num}/{total_tests}] Testing {input_size//1000}k chars, {vision_str}, run #{run}...", end=' ', flush=True)

				try:
					result = await test_single_config(input_size, with_vision, run)
					results.append(result)
					print(f"TTFT: {result['ttft']:.3f}s")
				except Exception as e:
					print(f"ERROR: {e}")

				await asyncio.sleep(0.5)  # Brief pause between tests

	# Analysis
	print()
	print("="*100)
	print("RESULTS")
	print("="*100)
	print()

	# Group by configuration
	print(f"{'Input Size':<12} {'Vision':<10} {'Run':<5} {'TTFT':<10}")
	print("-"*100)

	for result in results:
		vision_str = "Yes" if result['with_vision'] else "No"
		print(f"{result['input_size']//1000}k{'':<9} {vision_str:<10} #{result['run']:<4} {result['ttft']:.3f}s")

	print()
	print("="*100)
	print("ANALYSIS")
	print("="*100)
	print()

	# Average by input size (no vision)
	print("📊 Impact of INPUT SIZE (no vision):")
	print(f"{'Input Size':<15} {'Avg TTFT':<12} {'Samples':<10}")
	print("-"*50)
	for size in input_sizes:
		matching = [r for r in results if r['input_size'] == size and not r['with_vision']]
		if matching:
			avg_ttft = sum(r['ttft'] for r in matching) / len(matching)
			print(f"{size//1000}k chars{'':<6} {avg_ttft:.3f}s{'':<6} n={len(matching)}")

	print()
	print("📊 Impact of VISION (20k input):")
	print(f"{'Vision':<15} {'Avg TTFT':<12} {'Samples':<10}")
	print("-"*50)
	for has_vision in [False, True]:
		matching = [r for r in results if r['input_size'] == 20000 and r['with_vision'] == has_vision]
		if matching:
			avg_ttft = sum(r['ttft'] for r in matching) / len(matching)
			vision_label = "With vision" if has_vision else "No vision"
			print(f"{vision_label:<15} {avg_ttft:.3f}s{'':<6} n={len(matching)}")

	print()
	print("📊 COMPARISON:")

	# No vision comparison
	no_vision_1k = [r for r in results if r['input_size'] == 1000 and not r['with_vision']]
	no_vision_50k = [r for r in results if r['input_size'] == 50000 and not r['with_vision']]

	if no_vision_1k and no_vision_50k:
		avg_1k = sum(r['ttft'] for r in no_vision_1k) / len(no_vision_1k)
		avg_50k = sum(r['ttft'] for r in no_vision_50k) / len(no_vision_50k)
		diff = avg_50k - avg_1k
		pct = (diff / avg_1k) * 100
		print(f"  Input size impact: 1k→50k chars adds {diff:.3f}s ({pct:.1f}% increase)")

	# Vision comparison at 20k
	no_vision_20k = [r for r in results if r['input_size'] == 20000 and not r['with_vision']]
	with_vision_20k = [r for r in results if r['input_size'] == 20000 and r['with_vision']]

	if no_vision_20k and with_vision_20k:
		avg_no_vis = sum(r['ttft'] for r in no_vision_20k) / len(no_vision_20k)
		avg_with_vis = sum(r['ttft'] for r in with_vision_20k) / len(with_vision_20k)
		diff = avg_with_vis - avg_no_vis
		pct = (diff / avg_no_vis) * 100
		print(f"  Vision impact: Adding image adds {diff:.3f}s ({pct:.1f}% increase)")

	print()
	print("✅ Analysis complete!")

if __name__ == '__main__':
	asyncio.run(main())
