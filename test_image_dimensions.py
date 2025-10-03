"""
Test if image DIMENSIONS affect token count (not file size)
"""
import asyncio
import os
from dotenv import load_dotenv
from google import genai
from google.genai import types
from PIL import Image
from io import BytesIO

load_dotenv()

async def test_image_dimensions(width: int, height: int):
	"""Test image token count for specific dimensions"""

	client = genai.Client(api_key=os.getenv('GOOGLE_API_KEY'))

	# Create simple solid color image
	img = Image.new('RGB', (width, height), color=(100, 150, 200))
	buffer = BytesIO()
	img.save(buffer, format='PNG')
	image_bytes = buffer.getvalue()
	size_kb = len(image_bytes) // 1024

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

	image_tokens = 0
	if usage.prompt_tokens_details:
		for detail in usage.prompt_tokens_details:
			if str(detail.modality) == 'MediaModality.IMAGE':
				image_tokens = detail.token_count

	return {
		'width': width,
		'height': height,
		'resolution': f"{width}x{height}",
		'megapixels': (width * height) / 1_000_000,
		'size_kb': size_kb,
		'image_tokens': image_tokens,
		'total_tokens': usage.prompt_token_count,
	}

async def main():
	print("=" * 80)
	print("Image Dimensions Token Test")
	print("=" * 80)
	print()

	# Test various common resolutions
	dimensions = [
		(320, 240),    # 0.08 MP - tiny
		(640, 480),    # 0.31 MP - small
		(800, 600),    # 0.48 MP
		(1024, 768),   # 0.79 MP
		(1280, 720),   # 0.92 MP - HD
		(1512, 857),   # 1.30 MP - browser-use default
		(1920, 1080),  # 2.07 MP - Full HD
		(2560, 1440),  # 3.69 MP - QHD
		(3840, 2160),  # 8.29 MP - 4K
	]

	results = []

	for width, height in dimensions:
		print(f"Testing {width}x{height}...", end=' ', flush=True)
		result = await test_image_dimensions(width, height)
		results.append(result)
		print(f"✅ {result['image_tokens']} tokens, {result['size_kb']}KB")
		await asyncio.sleep(0.5)

	print()
	print("=" * 80)
	print("RESULTS")
	print("=" * 80)
	print()
	print(f"{'Resolution':<15} {'MP':<8} {'Size':<10} {'Tokens':<10} {'Tokens/MP':<12}")
	print("-" * 80)

	for r in results:
		tokens_per_mp = r['image_tokens'] / r['megapixels'] if r['megapixels'] > 0 else 0
		print(
			f"{r['resolution']:<15} "
			f"{r['megapixels']:.2f}{'':<4} "
			f"{r['size_kb']}KB{'':<6} "
			f"{r['image_tokens']:<10} "
			f"{tokens_per_mp:.1f}"
		)

	print()
	print("Findings:")
	if len(set(r['image_tokens'] for r in results)) == 1:
		print(f"  ✅ ALL images = {results[0]['image_tokens']} tokens regardless of dimensions!")
		print(f"  → Gemini uses fixed-size image embeddings")
	else:
		print(f"  → Token count varies with dimensions")
		print(f"  → Range: {min(r['image_tokens'] for r in results)} to {max(r['image_tokens'] for r in results)} tokens")

if __name__ == '__main__':
	asyncio.run(main())
