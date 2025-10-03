"""
Check how Gemini counts image tokens vs text tokens
"""
import asyncio
import os
from dotenv import load_dotenv
from google import genai
from google.genai import types
from PIL import Image
from io import BytesIO

load_dotenv()

async def test_with_image():
	"""Test token counting with image"""

	client = genai.Client(api_key=os.getenv('GOOGLE_API_KEY'))

	# Create 100KB image
	img = Image.new('RGB', (800, 600), color=(255, 255, 255))
	buffer = BytesIO()
	img.save(buffer, format='PNG')
	image_bytes = buffer.getvalue()
	image_kb = len(image_bytes) // 1024

	# Small text prompt
	text = "X" * 1000

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

	parts = [
		types.Part(text=text),
		types.Part(
			inline_data=types.Blob(
				mime_type='image/png',
				data=image_bytes
			)
		)
	]

	content = types.Content(role='user', parts=parts)

	print("Testing 1000 chars + 100KB image...")
	response = await client.aio.models.generate_content(
		model='gemini-flash-lite-latest',
		contents=[content],
		config=config,
	)

	usage = response.usage_metadata

	print(f"\nImage size: {image_kb}KB")
	print(f"Text size: 1000 chars (~250 tokens)")
	print()
	print(f"prompt_token_count: {usage.prompt_token_count}")
	print(f"candidates_token_count: {usage.candidates_token_count}")
	print(f"total_token_count: {usage.total_token_count}")
	print()

	if usage.prompt_tokens_details:
		print("Prompt tokens by modality:")
		for detail in usage.prompt_tokens_details:
			print(f"  {detail.modality}: {detail.token_count} tokens")

	print()
	print("Interpretation:")
	print(f"  If prompt_tokens = {usage.prompt_token_count}, this INCLUDES image tokens")
	print(f"  Image tokens ≈ {usage.prompt_token_count - 250} (assuming 250 text tokens)")

if __name__ == '__main__':
	asyncio.run(test_with_image())
