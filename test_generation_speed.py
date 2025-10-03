"""
Test generation speed at different token counts for both models:
- Fixed: 40k chars + vision
- Measure time to generate: 1 token, 100 tokens, 500 tokens
- Compare gemini-flash-latest vs gemini-flash-lite-latest
- 3 runs per configuration
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

async def test_generation_speed(
	model_name: str,
	target_tokens: int,
	run_number: int = 1,
) -> dict:
	"""Test generation speed up to target_tokens"""

	client = genai.Client(api_key=os.getenv('GOOGLE_API_KEY'))

	# Create input with unique content per run to avoid caching
	text = create_text(40000, run_number)

	# Task that generates multiple tokens
	if target_tokens == 1:
		task = "Click element 5"
	elif target_tokens <= 100:
		task = "List the first 10 product names you see on the page."
	else:  # 500 tokens
		task = "Analyze all products on the page and provide detailed recommendations about which ones are best value, including pros/cons for each product, pricing analysis, and final recommendations."

	prompt = f"""{text}

Task: {task}

Respond with detailed analysis."""

	config = types.GenerateContentConfig(
		temperature=0.0,
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

	# Measure
	start = time.time()

	stream = await client.aio.models.generate_content_stream(
		model=model_name,
		contents=[content],
		config=config,
	)

	# Track timing at different token counts
	chunk_count = 0
	first_chunk_time = None
	total_text = ""
	time_at_1_token = None
	time_at_100_tokens = None
	time_at_500_tokens = None

	# Rough estimate: 1 token ~= 4 chars
	async for chunk in stream:
		chunk_count += 1

		if chunk.text:
			total_text += chunk.text
			current_time = time.time() - start

			if chunk_count == 1:
				first_chunk_time = current_time

			# Track milestones (rough token estimation)
			approx_tokens = len(total_text) // 4

			if time_at_1_token is None and approx_tokens >= 1:
				time_at_1_token = current_time

			if time_at_100_tokens is None and approx_tokens >= 100:
				time_at_100_tokens = current_time

			if time_at_500_tokens is None and approx_tokens >= 500:
				time_at_500_tokens = current_time

	total_time = time.time() - start
	final_tokens = len(total_text) // 4

	return {
		'model': model_name,
		'target_tokens': target_tokens,
		'ttft': first_chunk_time,
		'time_at_1_token': time_at_1_token,
		'time_at_100_tokens': time_at_100_tokens,
		'time_at_500_tokens': time_at_500_tokens,
		'total_time': total_time,
		'final_tokens': final_tokens,
		'response_len': len(total_text),
		'chunk_count': chunk_count,
		'run': run_number,
	}

async def main():
	"""Test generation speed"""

	print("="*100)
	print("Generation Speed Analysis - 40k chars + vision")
	print("="*100)
	print()
	print("Testing:")
	print("  - Fixed input: 40k chars + 800x600 image")
	print("  - Models: gemini-flash-latest, gemini-flash-lite-latest")
	print("  - Target outputs: 1 token, 100 tokens, 500 tokens")
	print("  - Runs: 3 per configuration (unique content to avoid caching)")
	print("  - Measure: TTFT, time to 1 token, time to 100 tokens, time to 500 tokens")
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
	target_tokens_list = [1, 100, 500]
	runs_per_config = 3

	results = []
	total_tests = len(models) * len(target_tokens_list) * runs_per_config
	test_num = 0

	for model_name in models:
		for target_tokens in target_tokens_list:
			for run in range(1, runs_per_config + 1):
				test_num += 1

				print(f"[{test_num}/{total_tests}] {model_name}, target {target_tokens} tokens, run #{run}...", end=' ', flush=True)

				try:
					result = await test_generation_speed(model_name, target_tokens, run)
					results.append(result)
					print(f"TTFT: {result['ttft']:.3f}s, Total: {result['total_time']:.3f}s, Got {result['final_tokens']} tokens")
				except Exception as e:
					print(f"ERROR: {e}")

				await asyncio.sleep(1.0)  # Pause to avoid rate limits

	# Analysis
	print()
	print("="*100)
	print("DETAILED RESULTS")
	print("="*100)
	print()

	print(f"{'Model':<30} {'Target':<8} {'Run':<5} {'TTFT':<10} {'@1tok':<10} {'@100tok':<10} {'@500tok':<10} {'Total':<10} {'Got':<8}")
	print("-"*100)

	for result in results:
		t1 = f"{result['time_at_1_token']:.3f}s" if result['time_at_1_token'] else "N/A"
		t100 = f"{result['time_at_100_tokens']:.3f}s" if result['time_at_100_tokens'] else "N/A"
		t500 = f"{result['time_at_500_tokens']:.3f}s" if result['time_at_500_tokens'] else "N/A"

		print(
			f"{result['model']:<30} "
			f"{result['target_tokens']:<8} "
			f"#{result['run']:<4} "
			f"{result['ttft']:.3f}s{'':<4} "
			f"{t1:<10} "
			f"{t100:<10} "
			f"{t500:<10} "
			f"{result['total_time']:.3f}s{'':<4} "
			f"{result['final_tokens']} tok"
		)

	print()
	print("="*100)
	print("ANALYSIS")
	print("="*100)
	print()

	# Compare models at each milestone
	for model_name in models:
		print(f"📊 {model_name}:")
		model_results = [r for r in results if r['model'] == model_name]

		if model_results:
			# Average TTFT
			avg_ttft = sum(r['ttft'] for r in model_results) / len(model_results)
			print(f"  Average TTFT: {avg_ttft:.3f}s (n={len(model_results)})")

			# Time to 1 token
			with_1tok = [r for r in model_results if r['time_at_1_token']]
			if with_1tok:
				avg_1tok = sum(r['time_at_1_token'] for r in with_1tok) / len(with_1tok)
				print(f"  Time to 1 token: {avg_1tok:.3f}s avg (n={len(with_1tok)})")

			# Time to 100 tokens
			with_100tok = [r for r in model_results if r['time_at_100_tokens']]
			if with_100tok:
				avg_100tok = sum(r['time_at_100_tokens'] for r in with_100tok) / len(with_100tok)
				avg_gen_100 = avg_100tok - avg_ttft
				print(f"  Time to 100 tokens: {avg_100tok:.3f}s avg (generation: {avg_gen_100:.3f}s, n={len(with_100tok)})")

			# Time to 500 tokens
			with_500tok = [r for r in model_results if r['time_at_500_tokens']]
			if with_500tok:
				avg_500tok = sum(r['time_at_500_tokens'] for r in with_500tok) / len(with_500tok)
				avg_gen_500 = avg_500tok - avg_ttft
				tokens_per_sec = 500 / avg_gen_500 if avg_gen_500 > 0 else 0
				print(f"  Time to 500 tokens: {avg_500tok:.3f}s avg (generation: {avg_gen_500:.3f}s, {tokens_per_sec:.1f} tok/s, n={len(with_500tok)})")

		print()

	# Direct comparison
	print("📊 Model comparison (averages across all runs):")
	for milestone, field in [
		("TTFT", 'ttft'),
		("1 token", 'time_at_1_token'),
		("100 tokens", 'time_at_100_tokens'),
		("500 tokens", 'time_at_500_tokens'),
	]:
		print(f"  {milestone}:")
		for model_name in models:
			matching = [r for r in results if r['model'] == model_name and r.get(field)]
			if matching:
				avg = sum(r[field] for r in matching) / len(matching)
				print(f"    {model_name}: {avg:.3f}s (n={len(matching)})")

	print()
	print("✅ Analysis complete!")

if __name__ == '__main__':
	asyncio.run(main())
