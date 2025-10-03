import asyncio
import os
import time
from dotenv import load_dotenv
import google.generativeai as genai

load_dotenv()

async def test_gemini_ttft():
	genai.configure(api_key=os.getenv('GOOGLE_API_KEY'))

	model = genai.GenerativeModel(
		'gemini-2.0-flash-exp',
		generation_config={
			'thinking_config': {'thinking_budget': 0},
			'temperature': 0.0,
			'response_mime_type': 'application/json',
			'response_schema': {
				'type': 'object',
				'properties': {
					'action': {
						'type': 'array',
						'items': {
							'type': 'object',
							'properties': {
								'done': {
									'type': 'object',
									'properties': {
										'text': {'type': 'string'},
										'success': {'type': 'boolean'}
									}
								}
							}
						}
					}
				}
			}
		}
	)

	prompt = "You are a browser automation agent. Current page: google.com. Task: Go to google.com. Respond with action array containing done action."

	start = time.time()
	print(f'[{0:.3f}s] Starting stream request...')

	response = await model.generate_content_async(prompt, stream=True)

	print(f'[{time.time() - start:.3f}s] Stream created, waiting for chunks...')

	chunk_count = 0
	async for chunk in response:
		chunk_count += 1
		elapsed = time.time() - start
		if chunk_count == 1:
			print(f'[{elapsed:.3f}s] ⚡ FIRST CHUNK (TTFT: {elapsed:.3f}s)')
		if chunk.text:
			print(f'[{elapsed:.3f}s] Chunk #{chunk_count}: {len(chunk.text)} chars')

	total_time = time.time() - start
	print(f'[{total_time:.3f}s] ✅ Stream complete, {chunk_count} chunks total')

if __name__ == '__main__':
	asyncio.run(test_gemini_ttft())
