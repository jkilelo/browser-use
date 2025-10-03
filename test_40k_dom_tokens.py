"""
Test how many tokens the 40k char DOM actually uses
"""
import asyncio
import os
from dotenv import load_dotenv
from google import genai
from google.genai import types
import random
import time

load_dotenv()

def create_text(size_chars: int, unique_id: int = 1) -> str:
	"""Create text of specified size with unique content"""
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

async def test_text_only(text: str):
	"""Test text-only tokens"""

	client = genai.Client(api_key=os.getenv('GOOGLE_API_KEY'))

	task = "Click on the first product and add to cart."

	prompt = f"""{text}

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

	parts = [types.Part(text=prompt)]
	content = types.Content(role='user', parts=parts)

	response = await client.aio.models.generate_content(
		model='gemini-flash-lite-latest',
		contents=[content],
		config=config,
	)

	usage = response.usage_metadata

	return {
		'prompt_chars': len(prompt),
		'prompt_tokens': usage.prompt_token_count,
		'text_tokens': 0,
		'completion_tokens': usage.candidates_token_count,
		'total_tokens': usage.total_token_count,
	}

async def main():
	print("=" * 80)
	print("40k Char DOM Token Test - TEXT ONLY, NO IMAGE")
	print("=" * 80)
	print()

	dom_text = create_text(40000, unique_id=1)
	print(f"DOM size: {len(dom_text):,} chars")
	print()

	print("Testing...", end=' ', flush=True)
	result = await test_text_only(dom_text)
	print(f"✅ {result['prompt_tokens']} prompt tokens")

	print()
	print("=" * 80)
	print("RESULTS")
	print("=" * 80)
	print()
	print(f"Prompt chars: {result['prompt_chars']:,}")
	print(f"Prompt tokens: {result['prompt_tokens']:,}")
	print(f"Completion tokens: {result['completion_tokens']:,}")
	print(f"Total tokens: {result['total_tokens']:,}")
	print()
	print(f"Chars per token: {result['prompt_chars'] / result['prompt_tokens']:.2f}")
	print()
	print("Conclusion:")
	print(f"  40k char DOM = {result['prompt_tokens']:,} tokens")
	print(f"  Add 258 image tokens = {result['prompt_tokens'] + 258:,} total prompt tokens")
	print()
	if result['prompt_tokens'] + 258 > 19000:
		print(f"  ✅ This matches the 19,300 tokens we saw in screenshot test!")
	else:
		print(f"  ❌ This doesn't match - expected ~19,300 tokens")

if __name__ == '__main__':
	asyncio.run(main())
