"""
Test TTFT with different screenshot sizes to understand vision processing impact:
- Test multiple screenshot sizes: 100KB, 500KB, 1MB, 2MB (like real browser-use)
- Compare flash-latest vs flash-lite-latest
- Measure TTFT and count input tokens
- Fixed 40k char DOM
"""
import asyncio
import os
import time
import base64
from io import BytesIO
from dotenv import load_dotenv
from google import genai
from google.genai import types
from PIL import Image, ImageDraw
import random

load_dotenv()

def create_image_of_size(target_size_kb: int) -> bytes:
	"""Create a realistic-looking image of approximately target_size_kb"""
	# Start with a reasonable resolution
	# PNG size scales with image complexity and resolution
	# Approximate: 1920x1080 PNG with some content ≈ 500KB-1MB

	if target_size_kb <= 100:
		width, height = 800, 600
		quality = 6  # Higher compression
	elif target_size_kb <= 500:
		width, height = 1280, 720
		quality = 6
	elif target_size_kb <= 1000:
		width, height = 1512, 857  # browser-use default
		quality = 6
	else:  # 2MB
		width, height = 1920, 1080
		quality = 6

	# Create image with random content (simulates real webpage)
	img = Image.new('RGB', (width, height), color=(255, 255, 255))
	pixels = img.load()
	draw = ImageDraw.Draw(img)

	# Add random colored blocks (simulates webpage elements)
	for _ in range(100):
		x1, y1 = random.randint(0, width), random.randint(0, height)
		x2, y2 = x1 + random.randint(50, 200), y1 + random.randint(50, 200)
		color = (random.randint(0, 255), random.randint(0, 255), random.randint(0, 255))
		draw.rectangle([x1, y1, x2, y2], fill=color)

	# Add some text (simulates webpage text)
	for _ in range(50):
		x, y = random.randint(0, width - 100), random.randint(0, height - 20)
		draw.text((x, y), f"Text {random.randint(0, 1000)}", fill=(0, 0, 0))

	# Add noise to increase file size
	for i in range(0, width, 2):
		for j in range(0, height, 2):
			if random.random() > 0.95:
				noise = random.randint(-10, 10)
				r, g, b = pixels[i, j]
				pixels[i, j] = (
					max(0, min(255, r + noise)),
					max(0, min(255, g + noise)),
					max(0, min(255, b + noise))
				)

	# Save to buffer
	buffer = BytesIO()
	img.save(buffer, format='PNG', compress_level=quality)
	image_bytes = buffer.getvalue()

	actual_size_kb = len(image_bytes) // 1024
	print(f"    Created {width}x{height} PNG: target={target_size_kb}KB, actual={actual_size_kb}KB")

	return image_bytes

def create_text(size_chars: int, unique_id: int = 1) -> str:
	"""Create text of specified size with unique content"""
	import random
	import time

	timestamp = int(time.time() * 1000000)
	random_val = random.randint(100000, 999999)
	unique_prefix = f"<!-- ID: {unique_id} | TS: {timestamp} | R: {random_val} -->\n"

	base_text = """
<element id="{i}" clickable="true">
	<tag>div</tag>
	<text>Product #{i} - Laptop RTX 4090 32GB RAM 1TB SSD</text>
	<attributes>
		<class>product-card</class>
		<data-id>PROD-{i:05d}</data-id>
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

async def test_screenshot_size(
	model_name: str,
	screenshot_size_kb: int,
	image_bytes: bytes,
	dom_text: str,
	run_number: int = 1,
) -> dict:
	"""Test TTFT with specific screenshot size"""

	client = genai.Client(api_key=os.getenv('GOOGLE_API_KEY'))

	task = "Click on the first product and add to cart."

	prompt = f"""{dom_text}

Task: {task}

Respond with JSON action array."""

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

	# Measure TTFT
	start = time.time()

	stream = await client.aio.models.generate_content_stream(
		model=model_name,
		contents=[content],
		config=config,
	)

	first_chunk_time = None
	usage_metadata = None

	async for chunk in stream:
		if chunk.text and first_chunk_time is None:
			first_chunk_time = time.time() - start

		# Try to get usage metadata from chunk
		if hasattr(chunk, 'usage_metadata') and chunk.usage_metadata:
			usage_metadata = chunk.usage_metadata

	total_time = time.time() - start

	# Extract token counts
	prompt_tokens = usage_metadata.prompt_token_count if usage_metadata else None
	completion_tokens = usage_metadata.candidates_token_count if usage_metadata else None
	total_tokens = usage_metadata.total_token_count if usage_metadata else None

	return {
		'model': model_name,
		'screenshot_size_kb': screenshot_size_kb,
		'ttft': first_chunk_time,
		'total_time': total_time,
		'prompt_tokens': prompt_tokens,
		'completion_tokens': completion_tokens,
		'total_tokens': total_tokens,
		'run': run_number,
	}

async def main():
	"""Test different screenshot sizes"""

	print("="*100)
	print("Screenshot Size Impact on TTFT")
	print("="*100)
	print()
	print("Testing:")
	print("  - Screenshot sizes: 100KB, 500KB, 1MB, 2MB")
	print("  - Models: gemini-flash-latest, gemini-flash-lite-latest")
	print("  - Fixed DOM: 40k chars")
	print("  - Runs: 3 per configuration")
	print("  - Measuring: TTFT, tokens")
	print()

	# Generate images once
	print("📸 Generating test images...")
	screenshot_sizes = [100, 500, 1000, 2000]  # KB
	images = {}

	for size_kb in screenshot_sizes:
		print(f"  Creating {size_kb}KB image...")
		images[size_kb] = create_image_of_size(size_kb)

	print()

	# Generate DOM once
	print("📄 Generating 40k char DOM...")
	dom_text = create_text(40000, unique_id=1)
	print(f"  DOM size: {len(dom_text)} chars")
	print()

	models = [
		'gemini-flash-latest',
		'gemini-flash-lite-latest',
	]
	runs_per_config = 3

	results = []
	total_tests = len(models) * len(screenshot_sizes) * runs_per_config
	test_num = 0
	unique_id = 0

	for model_name in models:
		for size_kb in screenshot_sizes:
			for run in range(1, runs_per_config + 1):
				test_num += 1
				unique_id += 1

				# Create unique DOM for each test to avoid caching
				dom_text_unique = create_text(40000, unique_id)

				print(f"[{test_num}/{total_tests}] {model_name}, {size_kb}KB screenshot, run #{run}...", end=' ', flush=True)

				try:
					result = await test_screenshot_size(
						model_name,
						size_kb,
						images[size_kb],
						dom_text_unique,
						run
					)
					results.append(result)
					tokens_str = f"{result['prompt_tokens']} tokens" if result['prompt_tokens'] else "N/A"
					print(f"TTFT: {result['ttft']:.3f}s, {tokens_str}")
				except Exception as e:
					print(f"ERROR: {e}")

				await asyncio.sleep(1.0)

	# Analysis
	print()
	print("="*100)
	print("RESULTS")
	print("="*100)
	print()

	print(f"{'Model':<30} {'Size':<8} {'Run':<5} {'TTFT':<10} {'Prompt Tok':<12} {'Total Tok':<10}")
	print("-"*100)

	for result in results:
		print(
			f"{result['model']:<30} "
			f"{result['screenshot_size_kb']}KB{'':<4} "
			f"#{result['run']:<4} "
			f"{result['ttft']:.3f}s{'':<4} "
			f"{result['prompt_tokens'] or 'N/A':<12} "
			f"{result['total_tokens'] or 'N/A':<10}"
		)

	print()
	print("="*100)
	print("ANALYSIS")
	print("="*100)
	print()

	# Analyze by model and screenshot size
	for model_name in models:
		print(f"📊 {model_name}:")
		model_results = [r for r in results if r['model'] == model_name]

		for size_kb in screenshot_sizes:
			matching = [r for r in model_results if r['screenshot_size_kb'] == size_kb]

			if matching:
				ttfts = [r['ttft'] for r in matching]
				avg_ttft = sum(ttfts) / len(ttfts)
				min_ttft = min(ttfts)
				max_ttft = max(ttfts)

				# Get average tokens (should be same for all runs)
				prompt_tokens_list = [r['prompt_tokens'] for r in matching if r['prompt_tokens']]
				avg_prompt_tokens = sum(prompt_tokens_list) / len(prompt_tokens_list) if prompt_tokens_list else None

				tokens_str = f"{int(avg_prompt_tokens)} tokens" if avg_prompt_tokens else "N/A"
				print(f"  {size_kb}KB: TTFT {avg_ttft:.3f}s (range: {min_ttft:.3f}-{max_ttft:.3f}s), {tokens_str}")

		print()

	# Cross-model comparison by screenshot size
	print("="*100)
	print("CROSS-MODEL COMPARISON BY SCREENSHOT SIZE")
	print("="*100)
	print()

	for size_kb in screenshot_sizes:
		print(f"📊 {size_kb}KB screenshot:")

		for model_name in models:
			matching = [r for r in results if r['model'] == model_name and r['screenshot_size_kb'] == size_kb]

			if matching:
				ttfts = [r['ttft'] for r in matching]
				avg_ttft = sum(ttfts) / len(ttfts)
				print(f"  {model_name}: {avg_ttft:.3f}s avg")

		# Calculate difference
		flash_latest = [r['ttft'] for r in results if r['model'] == 'gemini-flash-latest' and r['screenshot_size_kb'] == size_kb]
		flash_lite = [r['ttft'] for r in results if r['model'] == 'gemini-flash-lite-latest' and r['screenshot_size_kb'] == size_kb]

		if flash_latest and flash_lite:
			avg_latest = sum(flash_latest) / len(flash_latest)
			avg_lite = sum(flash_lite) / len(flash_lite)
			diff = avg_latest - avg_lite
			pct = (diff / avg_latest) * 100

			if avg_lite < avg_latest:
				print(f"  → flash-lite is {pct:.1f}% faster ({diff:.3f}s)")
			else:
				print(f"  → flash-latest is {-pct:.1f}% faster ({-diff:.3f}s)")

		print()

	# Screenshot size impact within each model
	print("="*100)
	print("SCREENSHOT SIZE IMPACT WITHIN EACH MODEL")
	print("="*100)
	print()

	for model_name in models:
		print(f"📊 {model_name} - Screenshot size impact:")

		model_results = [r for r in results if r['model'] == model_name]

		size_avgs = {}
		for size_kb in screenshot_sizes:
			matching = [r for r in model_results if r['screenshot_size_kb'] == size_kb]
			if matching:
				ttfts = [r['ttft'] for r in matching]
				size_avgs[size_kb] = sum(ttfts) / len(ttfts)

		if len(size_avgs) >= 2:
			smallest = min(size_avgs.keys())
			largest = max(size_avgs.keys())
			diff = size_avgs[largest] - size_avgs[smallest]
			pct = (diff / size_avgs[smallest]) * 100

			print(f"  {smallest}KB → {largest}KB: +{diff:.3f}s ({pct:.1f}% increase)")

			for size_kb in sorted(size_avgs.keys()):
				print(f"    {size_kb}KB: {size_avgs[size_kb]:.3f}s")

		print()

	print("✅ Analysis complete!")

if __name__ == '__main__':
	asyncio.run(main())
