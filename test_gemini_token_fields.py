"""
Check what fields Gemini actually returns in usage_metadata
"""
import asyncio
import os
from dotenv import load_dotenv
from google import genai
from google.genai import types

load_dotenv()

async def test_token_fields():
	"""See what's in usage_metadata"""

	client = genai.Client(api_key=os.getenv('GOOGLE_API_KEY'))

	prompt = "X" * 100  # Small text

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

	parts = [types.Part(text=prompt)]
	content = types.Content(role='user', parts=parts)

	print("Testing with streaming...")
	stream = await client.aio.models.generate_content_stream(
		model='gemini-flash-lite-latest',
		contents=[content],
		config=config,
	)

	usage_metadata = None
	async for chunk in stream:
		if hasattr(chunk, 'usage_metadata') and chunk.usage_metadata:
			usage_metadata = chunk.usage_metadata

	print(f"\nusage_metadata type: {type(usage_metadata)}")
	print(f"usage_metadata dir: {dir(usage_metadata)}")
	print()
	print("Available fields:")
	for field in dir(usage_metadata):
		if not field.startswith('_'):
			try:
				value = getattr(usage_metadata, field)
				if not callable(value):
					print(f"  {field}: {value}")
			except:
				pass

if __name__ == '__main__':
	asyncio.run(test_token_fields())
