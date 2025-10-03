"""
Test pure Gemini API TTFT without any browser-use library code.
This tests the raw Google Gemini API streaming performance.
"""
import asyncio
import os
import time
from dotenv import load_dotenv
from google import genai
from google.genai import types

load_dotenv()

async def test_gemini_streaming_ttft():
	"""Test Gemini streaming TTFT with thinking_budget=0"""
	client = genai.Client(api_key=os.getenv('GOOGLE_API_KEY'))

	# Simple prompt to minimize processing time
	prompt = "What is 2+2? Respond with JSON: {\"answer\": number, \"explanation\": string}"

	# Minimal config for fastest response
	config = types.GenerateContentConfig(
		temperature=0.0,
		response_mime_type='application/json',
		response_schema={
			'type': 'object',
			'properties': {
				'answer': {'type': 'number'},
				'explanation': {'type': 'string'}
			},
			'required': ['answer', 'explanation']
		},
		thinking_config={'thinking_budget': 0},
	)

	print(f'[0.000s] 🚀 Starting Gemini streaming request...')
	print(f'         Model: gemini-2.0-flash-exp')
	print(f'         Thinking budget: 0')
	print(f'         Prompt: {prompt}')
	print()

	start = time.time()

	# Create streaming request (await it to get the async iterator)
	stream = await client.aio.models.generate_content_stream(
		model='gemini-2.0-flash-exp',
		contents=prompt,
		config=config,
	)

	stream_create_time = time.time() - start
	print(f'[{stream_create_time:.3f}s] ✅ Stream object created')
	print()

	# Process chunks
	chunk_count = 0
	first_chunk_time = None
	total_text = ""

	async for chunk in stream:
		chunk_count += 1
		elapsed = time.time() - start

		if chunk_count == 1:
			first_chunk_time = elapsed
			print(f'[{elapsed:.3f}s] ⚡ FIRST CHUNK RECEIVED (TTFT: {elapsed:.3f}s)')

		if chunk.text:
			chunk_len = len(chunk.text)
			total_text += chunk.text
			print(f'[{elapsed:.3f}s] Chunk #{chunk_count}: {chunk_len} chars - {repr(chunk.text[:80])}')

	total_time = time.time() - start
	print()
	print(f'[{total_time:.3f}s] ✅ Stream complete')
	print(f'         Total chunks: {chunk_count}')
	print(f'         TTFT: {first_chunk_time:.3f}s')
	print(f'         Total time: {total_time:.3f}s')
	print(f'         Full response: {total_text}')
	print()

	if first_chunk_time and first_chunk_time < 0.5:
		print(f'✅ SUCCESS: TTFT {first_chunk_time:.3f}s is < 0.5s')
	else:
		print(f'❌ FAIL: TTFT {first_chunk_time:.3f}s is >= 0.5s')

	return first_chunk_time

async def test_multiple_runs():
	"""Run the test multiple times to check consistency"""
	print("=" * 80)
	print("Testing Gemini TTFT across 3 runs")
	print("=" * 80)
	print()

	ttfts = []
	for i in range(3):
		print(f"{'=' * 80}")
		print(f"RUN #{i+1}")
		print(f"{'=' * 80}")
		ttft = await test_gemini_streaming_ttft()
		ttfts.append(ttft)
		print()
		await asyncio.sleep(1)  # Brief pause between runs

	print("=" * 80)
	print("SUMMARY")
	print("=" * 80)
	print(f"TTFTs: {[f'{t:.3f}s' for t in ttfts]}")
	print(f"Average TTFT: {sum(ttfts)/len(ttfts):.3f}s")
	print(f"Min TTFT: {min(ttfts):.3f}s")
	print(f"Max TTFT: {max(ttfts):.3f}s")

if __name__ == '__main__':
	asyncio.run(test_multiple_runs())
