"""
Compare TTFT across Gemini models with browser-use-like scenario:
- 40k character DOM text + 800x600 image
- Models: gemini-2.0-flash-exp, gemini-flash-latest, gemini-flash-lite-latest
- 2 runs per model to avoid rate limits
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

async def test_model(
	model_name: str,
	input_size: int,
	with_vision: bool,
	run_number: int = 1
) -> dict:
	"""Test a single model configuration"""

	client = genai.Client(api_key=os.getenv('GOOGLE_API_KEY'))

	# Create input
	text = create_text(input_size)

	# Realistic browser-use task
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

	# Measure
	start = time.time()

	stream = await client.aio.models.generate_content_stream(
		model=model_name,
		contents=[content],
		config=config,
	)

	stream_create_time = time.time() - start

	# Get TTFT and collect response
	chunk_count = 0
	first_chunk_time = None
	total_text = ""

	async for chunk in stream:
		chunk_count += 1
		if chunk_count == 1 and chunk.text:
			first_chunk_time = time.time() - start
		if chunk.text:
			total_text += chunk.text

	total_time = time.time() - start

	return {
		'model': model_name,
		'input_size': input_size,
		'with_vision': with_vision,
		'stream_create_time': stream_create_time,
		'ttft': first_chunk_time,
		'total_time': total_time,
		'response_len': len(total_text),
		'run': run_number
	}

async def main():
	"""Compare models with browser-use scenario"""

	print("="*100)
	print("Gemini Model TTFT Comparison - Browser-Use Scenario")
	print("="*100)
	print()
	print("Scenario:")
	print("  - Input: 40k chars DOM + 800x600 screenshot")
	print("  - Models: gemini-2.0-flash-exp, gemini-flash-latest, gemini-flash-lite-latest")
	print("  - Runs: 2 per model")
	print("  - Thinking budget: 0")
	print()

	# Try to import PIL
	try:
		from PIL import Image
		print("✅ Pillow available")
	except ImportError:
		print("⚠️  Installing Pillow...")
		import subprocess
		subprocess.run(['uv', 'add', 'pillow'], check=True, capture_output=True)
		print("✅ Pillow installed")

	print()

	# Test configurations
	models = [
		'gemini-2.0-flash-exp',
		'gemini-flash-latest',
		'gemini-flash-lite-latest',
	]
	input_size = 40000
	with_vision = True
	runs_per_model = 2

	results = []
	total_tests = len(models) * runs_per_model
	test_num = 0

	for model_name in models:
		for run in range(1, runs_per_model + 1):
			test_num += 1

			print(f"[{test_num}/{total_tests}] Testing {model_name}, run #{run}...", end=' ', flush=True)

			try:
				result = await test_model(model_name, input_size, with_vision, run)
				results.append(result)
				print(f"TTFT: {result['ttft']:.3f}s, Total: {result['total_time']:.3f}s")
			except Exception as e:
				print(f"ERROR: {e}")

			await asyncio.sleep(1.0)  # Longer pause to avoid rate limits

	# Analysis
	print()
	print("="*100)
	print("RESULTS")
	print("="*100)
	print()

	# Group by model
	print(f"{'Model':<30} {'Run':<5} {'TTFT':<10} {'Total Time':<12} {'Response Len':<15}")
	print("-"*100)

	for result in results:
		print(f"{result['model']:<30} #{result['run']:<4} {result['ttft']:.3f}s{'':<4} {result['total_time']:.3f}s{'':<6} {result['response_len']} chars")

	print()
	print("="*100)
	print("ANALYSIS")
	print("="*100)
	print()

	# Average by model
	print("📊 Average TTFT by Model:")
	print(f"{'Model':<30} {'Avg TTFT':<12} {'Avg Total':<12} {'Samples':<10}")
	print("-"*80)
	for model_name in models:
		matching = [r for r in results if r['model'] == model_name]
		if matching:
			avg_ttft = sum(r['ttft'] for r in matching) / len(matching)
			avg_total = sum(r['total_time'] for r in matching) / len(matching)
			print(f"{model_name:<30} {avg_ttft:.3f}s{'':<6} {avg_total:.3f}s{'':<6} n={len(matching)}")

	print()
	print("📊 COMPARISON:")

	# Find fastest model
	if results:
		by_model = {}
		for result in results:
			if result['model'] not in by_model:
				by_model[result['model']] = []
			by_model[result['model']].append(result['ttft'])

		for model_name, ttfts in by_model.items():
			avg_ttft = sum(ttfts) / len(ttfts)
			print(f"  {model_name}: {avg_ttft:.3f}s average TTFT")

		# Find best
		best_model = min(by_model.items(), key=lambda x: sum(x[1]) / len(x[1]))
		print()
		print(f"✅ Fastest model: {best_model[0]} ({sum(best_model[1]) / len(best_model[1]):.3f}s average TTFT)")

	print()
	print("✅ Analysis complete!")

if __name__ == '__main__':
	asyncio.run(main())
