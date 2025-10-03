"""
Detailed comparison of gemini-flash-latest and gemini-flash-lite-latest:
- Input sizes: 10k, 40k chars
- Vision: with/without 800x600 image
- Measure both TTFT and total generation time
- 1 run per config to avoid rate limits (8 total tests)
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

async def test_config(
	model_name: str,
	input_size: int,
	with_vision: bool,
	run_number: int = 1,
) -> dict:
	"""Test a single configuration"""

	client = genai.Client(api_key=os.getenv('GOOGLE_API_KEY'))

	# Create input with unique content per run to avoid caching
	text = create_text(input_size, run_number)
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
		model=model_name,
		contents=[content],
		config=config,
	)

	# Get TTFT and full response
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
		'ttft': first_chunk_time,
		'total_time': total_time,
		'generation_time': total_time - first_chunk_time if first_chunk_time else 0,
		'response_len': len(total_text),
		'chunk_count': chunk_count,
		'run': run_number,
	}

async def main():
	"""Run detailed comparison"""

	print("="*100)
	print("Detailed Flash Models Comparison")
	print("="*100)
	print()
	print("Testing:")
	print("  - Models: gemini-flash-latest, gemini-flash-lite-latest")
	print("  - Input sizes: 10k, 40k chars")
	print("  - Vision: with/without 800x600 image")
	print("  - Runs: 3 per configuration (unique content to avoid caching)")
	print("  - Metrics: TTFT, generation time, total time")
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
	runs_per_config = 3

	results = []
	total_tests = len(models) * len(input_sizes) * len(vision_options) * runs_per_config
	test_num = 0

	for model_name in models:
		for input_size in input_sizes:
			for with_vision in vision_options:
				for run in range(1, runs_per_config + 1):
					test_num += 1

					vision_str = "WITH vision" if with_vision else "NO vision"
					print(f"[{test_num}/{total_tests}] {model_name}, {input_size//1000}k chars, {vision_str}, run #{run}...", end=' ', flush=True)

					try:
						result = await test_config(model_name, input_size, with_vision, run)
						results.append(result)
						print(f"TTFT: {result['ttft']:.3f}s, Total: {result['total_time']:.3f}s")
					except Exception as e:
						print(f"ERROR: {e}")

					await asyncio.sleep(1.0)  # Pause to avoid rate limits

	# Analysis
	print()
	print("="*100)
	print("DETAILED RESULTS")
	print("="*100)
	print()

	print(f"{'Model':<30} {'Input':<8} {'Vision':<10} {'Run':<5} {'TTFT':<10} {'Gen Time':<10} {'Total':<10} {'Chunks':<8}")
	print("-"*100)

	for result in results:
		vision_str = "Yes" if result['with_vision'] else "No"
		print(
			f"{result['model']:<30} "
			f"{result['input_size']//1000}k{'':<6} "
			f"{vision_str:<10} "
			f"#{result['run']:<4} "
			f"{result['ttft']:.3f}s{'':<4} "
			f"{result['generation_time']:.3f}s{'':<4} "
			f"{result['total_time']:.3f}s{'':<4} "
			f"{result['chunk_count']}"
		)

	print()
	print("="*100)
	print("ANALYSIS")
	print("="*100)
	print()

	# Compare by model with averages
	for model_name in models:
		print(f"📊 {model_name}:")
		model_results = [r for r in results if r['model'] == model_name]

		# No vision comparison (average across runs)
		no_vis_10k = [r for r in model_results if r['input_size'] == 10000 and not r['with_vision']]
		no_vis_40k = [r for r in model_results if r['input_size'] == 40000 and not r['with_vision']]

		if no_vis_10k and no_vis_40k:
			avg_ttft_10k = sum(r['ttft'] for r in no_vis_10k) / len(no_vis_10k)
			avg_ttft_40k = sum(r['ttft'] for r in no_vis_40k) / len(no_vis_40k)
			diff = avg_ttft_40k - avg_ttft_10k
			pct = (diff / avg_ttft_10k) * 100 if avg_ttft_10k > 0 else 0
			print(f"  Input size impact (no vision): 10k→40k adds {diff:.3f}s ({pct:.1f}% increase)")
			print(f"    10k: {avg_ttft_10k:.3f}s avg (n={len(no_vis_10k)})")
			print(f"    40k: {avg_ttft_40k:.3f}s avg (n={len(no_vis_40k)})")

		# Vision comparison at 40k (average across runs)
		no_vis_40k = [r for r in model_results if r['input_size'] == 40000 and not r['with_vision']]
		with_vis_40k = [r for r in model_results if r['input_size'] == 40000 and r['with_vision']]

		if no_vis_40k and with_vis_40k:
			avg_ttft_no_vis = sum(r['ttft'] for r in no_vis_40k) / len(no_vis_40k)
			avg_ttft_with_vis = sum(r['ttft'] for r in with_vis_40k) / len(with_vis_40k)
			diff = avg_ttft_with_vis - avg_ttft_no_vis
			pct = (diff / avg_ttft_no_vis) * 100 if avg_ttft_no_vis > 0 else 0
			print(f"  Vision impact (40k): Adding image adds {diff:.3f}s ({pct:.1f}% increase)")
			print(f"    No vision: {avg_ttft_no_vis:.3f}s avg (n={len(no_vis_40k)})")
			print(f"    With vision: {avg_ttft_with_vis:.3f}s avg (n={len(with_vis_40k)})")

		print()

	# Compare models at 40k + vision (browser-use scenario)
	print("📊 Model comparison at 40k + vision (browser-use scenario):")
	for model_name in models:
		matching = [r for r in results if r['model'] == model_name and r['input_size'] == 40000 and r['with_vision']]
		if matching:
			avg_ttft = sum(r['ttft'] for r in matching) / len(matching)
			avg_gen = sum(r['generation_time'] for r in matching) / len(matching)
			avg_total = sum(r['total_time'] for r in matching) / len(matching)
			print(f"  {model_name}:")
			print(f"    TTFT: {avg_ttft:.3f}s avg (n={len(matching)})")
			print(f"    Generation time: {avg_gen:.3f}s avg")
			print(f"    Total time: {avg_total:.3f}s avg")

	print()
	print("✅ Analysis complete!")

if __name__ == '__main__':
	asyncio.run(main())
