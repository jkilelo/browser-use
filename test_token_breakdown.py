"""
Verify Gemini token counting - separate text vs image tokens
"""
import asyncio
import os
from dotenv import load_dotenv
from google import genai
from google.genai import types
from PIL import Image
from io import BytesIO
import random

load_dotenv()

async def test_tokens(text_chars: int, include_image: bool):
	"""Test token counts"""

	client = genai.Client(api_key=os.getenv('GOOGLE_API_KEY'))

	# Create text
	text = "X" * text_chars

	# Simple schema
	schema = {
		'type': 'object',
		'properties': {
			'answer': {'type': 'string'}
		}
	}

	config = types.GenerateContentConfig(
		temperature=0.0,
		response_mime_type='application/json',
		response_schema=schema,
		thinking_config={'thinking_budget': 0},
	)

	parts = [types.Part(text=text)]

	if include_image:
		# Create small test image
		img = Image.new('RGB', (800, 600), color=(255, 255, 255))
		buffer = BytesIO()
		img.save(buffer, format='PNG')
		image_bytes = buffer.getvalue()
		image_kb = len(image_bytes) // 1024

		parts.append(
			types.Part(
				inline_data=types.Blob(
					mime_type='image/png',
					data=image_bytes
				)
			)
		)
	else:
		image_kb = 0

	content = types.Content(role='user', parts=parts)

	response = await client.aio.models.generate_content(
		model='gemini-flash-lite-latest',
		contents=[content],
		config=config,
	)

	usage = response.usage_metadata

	return {
		'text_chars': text_chars,
		'image_kb': image_kb,
		'prompt_tokens': usage.prompt_token_count,
		'completion_tokens': usage.candidates_token_count,
		'total_tokens': usage.total_token_count,
	}

async def main():
	print("Token Breakdown Test")
	print("=" * 80)
	print()

	# Test text only
	print("Text only:")
	for chars in [100, 1000, 10000, 40000]:
		result = await test_tokens(chars, False)
		print(f"  {chars:>6} chars: {result['prompt_tokens']:>6} prompt tokens")
		await asyncio.sleep(0.5)

	print()

	# Test with image
	print("40k chars + image:")
	result = await test_tokens(40000, True)
	print(f"  Text: 40000 chars")
	print(f"  Image: {result['image_kb']}KB")
	print(f"  Prompt tokens: {result['prompt_tokens']}")
	print(f"  Completion tokens: {result['completion_tokens']}")
	print(f"  Total tokens: {result['total_tokens']}")

	print()
	print("Expected: ~40k chars = ~10k text tokens, small image = ~200-500 image tokens")
	print("If prompt_tokens is 19k, something is wrong with the test")

if __name__ == '__main__':
	asyncio.run(main())
