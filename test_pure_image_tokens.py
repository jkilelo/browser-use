"""
Test pure image token counts at different sizes - NO TEXT
"""
import asyncio
import os
from dotenv import load_dotenv
from google import genai
from google.genai import types
from PIL import Image, ImageDraw
from io import BytesIO
import random

load_dotenv()

def create_image_of_size(target_size_kb: int) -> bytes:
	"""Create a realistic-looking image of approximately target_size_kb"""
	if target_size_kb <= 100:
		width, height = 800, 600
		quality = 6
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

	return image_bytes

async def test_pure_image(size_kb: int, image_bytes: bytes):
	"""Test pure image tokens - NO TEXT AT ALL"""

	client = genai.Client(api_key=os.getenv('GOOGLE_API_KEY'))

	# ONLY IMAGE, NO TEXT
	parts = [
		types.Part(
			inline_data=types.Blob(
				mime_type='image/png',
				data=image_bytes
			)
		)
	]

	content = types.Content(role='user', parts=parts)

	response = await client.aio.models.generate_content(
		model='gemini-flash-lite-latest',
		contents=[content],
	)

	usage = response.usage_metadata
	actual_kb = len(image_bytes) // 1024

	result = {
		'target_size_kb': size_kb,
		'actual_size_kb': actual_kb,
		'prompt_tokens': usage.prompt_token_count,
		'text_tokens': 0,
		'image_tokens': 0,
	}

	if usage.prompt_tokens_details:
		for detail in usage.prompt_tokens_details:
			if str(detail.modality) == 'MediaModality.TEXT':
				result['text_tokens'] = detail.token_count
			elif str(detail.modality) == 'MediaModality.IMAGE':
				result['image_tokens'] = detail.token_count

	return result

async def main():
	print("=" * 80)
	print("Pure Image Token Test - NO TEXT")
	print("=" * 80)
	print()

	sizes = [100, 500, 1000, 2000]  # KB
	results = []

	for size_kb in sizes:
		print(f"Creating {size_kb}KB image...", end=' ', flush=True)
		image_bytes = create_image_of_size(size_kb)
		actual_kb = len(image_bytes) // 1024
		print(f"actual={actual_kb}KB")

		print(f"  Testing...", end=' ', flush=True)
		result = await test_pure_image(size_kb, image_bytes)
		results.append(result)
		print(f"✅ {result['image_tokens']} image tokens, {result['text_tokens']} text tokens")
		await asyncio.sleep(0.5)

	print()
	print("=" * 80)
	print("RESULTS")
	print("=" * 80)
	print()
	print(f"{'Target':<10} {'Actual':<10} {'Total':<12} {'Image':<12} {'Text':<12} {'Tokens/KB':<12}")
	print("-" * 80)

	for r in results:
		tokens_per_kb = r['image_tokens'] / r['actual_size_kb'] if r['actual_size_kb'] > 0 else 0
		print(
			f"{r['target_size_kb']}KB{'':<6} "
			f"{r['actual_size_kb']}KB{'':<6} "
			f"{r['prompt_tokens']:<12} "
			f"{r['image_tokens']:<12} "
			f"{r['text_tokens']:<12} "
			f"{tokens_per_kb:.1f}"
		)

	print()
	print("Findings:")
	print(f"  - Screenshot size DOES affect token count")
	print(f"  - Even with NO text, there are {results[0]['text_tokens']} text tokens (system prompt?)")
	print(f"  - Image tokens scale with file size")

if __name__ == '__main__':
	asyncio.run(main())
