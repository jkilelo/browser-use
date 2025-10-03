"""
Test how many tokens a real browser-use screenshot consumes:
1. Load a real screenshot from browser-use
2. Send to Gemini with minimal text
3. Measure time and token usage
"""
import asyncio
import os
import time
import base64
from pathlib import Path
from dotenv import load_dotenv
from google import genai
from google.genai import types

load_dotenv()

async def test_screenshot_tokens(screenshot_path: str, model_name: str) -> dict:
	"""Test screenshot token usage"""

	# Load screenshot
	with open(screenshot_path, 'rb') as f:
		screenshot_bytes = f.read()

	screenshot_size_kb = len(screenshot_bytes) // 1024

	client = genai.Client(api_key=os.getenv('GOOGLE_API_KEY'))

	# Minimal text prompt
	prompt = "What do you see?"

	# No schema, just text response
	config = types.GenerateContentConfig(
		temperature=0.0,
		thinking_config={'thinking_budget': 0},
	)

	# Build content with screenshot
	parts = [
		types.Part(text=prompt),
		types.Part(
			inline_data=types.Blob(
				mime_type='image/png',
				data=screenshot_bytes
			)
		)
	]

	content = types.Content(role='user', parts=parts)

	# Measure
	start = time.time()

	response = await client.aio.models.generate_content(
		model=model_name,
		contents=[content],
		config=config,
	)

	total_time = time.time() - start

	# Get usage info
	usage = response.usage_metadata

	return {
		'model': model_name,
		'screenshot_size_kb': screenshot_size_kb,
		'prompt_tokens': usage.prompt_token_count if usage else 0,
		'completion_tokens': usage.candidates_token_count if usage else 0,
		'total_tokens': usage.total_token_count if usage else 0,
		'cached_tokens': getattr(usage, 'cached_content_token_count', 0) if usage else 0,
		'time': total_time,
		'response_preview': response.text[:100] if response.text else '',
	}

async def main():
	"""Test screenshot token usage"""

	print("="*100)
	print("Screenshot Token Usage Test")
	print("="*100)
	print()

	# Find most recent browser-use screenshot
	temp_dirs = Path('/var/folders/q0/hy1vcj9j02qdx_zx_2mqwvhm0000gn/T/').glob('browser_use_agent_*/screenshots/*.png')
	screenshots = sorted(temp_dirs, key=lambda p: p.stat().st_mtime, reverse=True)

	if not screenshots:
		print("❌ No browser-use screenshots found!")
		print("   Run browser-use first to generate screenshots")
		return

	screenshot_path = str(screenshots[0])
	screenshot_size = screenshots[0].stat().st_size // 1024

	print(f"📸 Using screenshot: {screenshot_path}")
	print(f"   Size: {screenshot_size}KB")
	print()

	models = [
		'gemini-flash-latest',
		'gemini-flash-lite-latest',
	]

	results = []

	for model_name in models:
		print(f"Testing {model_name}...", end=' ', flush=True)

		try:
			result = await test_screenshot_tokens(screenshot_path, model_name)
			results.append(result)
			print(f"✅ {result['total_tokens']} tokens, {result['time']:.3f}s")
		except Exception as e:
			print(f"ERROR: {e}")

		await asyncio.sleep(1.0)

	# Analysis
	print()
	print("="*100)
	print("RESULTS")
	print("="*100)
	print()

	print(f"{'Model':<30} {'Screenshot':<12} {'Prompt Tok':<12} {'Compl Tok':<12} {'Total Tok':<12} {'Time':<10}")
	print("-"*100)

	for result in results:
		print(
			f"{result['model']:<30} "
			f"{result['screenshot_size_kb']}KB{'':<8} "
			f"{result['prompt_tokens']:<12} "
			f"{result['completion_tokens']:<12} "
			f"{result['total_tokens']:<12} "
			f"{result['time']:.3f}s"
		)

	print()
	print("="*100)
	print("ANALYSIS")
	print("="*100)
	print()

	for result in results:
		print(f"📊 {result['model']}:")
		print(f"   Screenshot size: {result['screenshot_size_kb']}KB")
		print(f"   Prompt tokens: {result['prompt_tokens']:,} (includes image)")
		print(f"   Completion tokens: {result['completion_tokens']:,}")
		print(f"   Total tokens: {result['total_tokens']:,}")
		if result['cached_tokens']:
			print(f"   Cached tokens: {result['cached_tokens']:,}")
		print(f"   Time: {result['time']:.3f}s")
		print(f"   Response preview: {result['response_preview']}")
		print()

	# Calculate tokens per KB
	if results:
		print("📊 Image token efficiency:")
		for result in results:
			# Subtract text prompt tokens (roughly 3-5 tokens)
			image_tokens = result['prompt_tokens'] - 5
			tokens_per_kb = image_tokens / result['screenshot_size_kb'] if result['screenshot_size_kb'] > 0 else 0
			print(f"   {result['model']}: ~{tokens_per_kb:.1f} tokens/KB")

	print()
	print("✅ Analysis complete!")

if __name__ == '__main__':
	asyncio.run(main())
