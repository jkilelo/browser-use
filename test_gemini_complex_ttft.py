"""
Test Gemini TTFT with complex prompts similar to browser-use:
- Large image (simulated with base64)
- 20k character DOM-like text
- Complex JSON schema
- Variable response lengths
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

# Create a dummy image (small red square)
def create_dummy_image() -> str:
	"""Create a base64-encoded dummy image"""
	# Create a simple 800x600 red square as PNG
	from PIL import Image
	img = Image.new('RGB', (800, 600), color='red')
	# Add some noise to make it more realistic
	import random
	pixels = img.load()
	for i in range(800):
		for j in range(600):
			noise = random.randint(-20, 20)
			pixels[i, j] = (max(0, min(255, 200 + noise)), noise % 50, noise % 30)

	buffer = BytesIO()
	img.save(buffer, format='PNG')
	return base64.b64encode(buffer.getvalue()).decode('utf-8')

def create_large_dom_text() -> str:
	"""Create a 20k character DOM-like text"""
	# Simulate a complex DOM structure
	elements = []
	for i in range(200):
		element = f"""
<element id="{i}" index="{i}" clickable="true">
	<tag>div</tag>
	<text>Product item #{i} - Gaming Laptop with RTX 4090, 32GB RAM, 1TB SSD</text>
	<attributes>
		<class>product-card search-result-item</class>
		<data-product-id>PROD-{i:05d}</data-product-id>
		<aria-label>Product {i}</aria-label>
	</attributes>
	<bbox>{{x: {i*10}, y: {i*50}, width: 300, height: 150}}</bbox>
	<children>
		<element>
			<tag>img</tag>
			<attributes><src>/images/laptop-{i}.jpg</src><alt>Laptop {i}</alt></attributes>
		</element>
		<element>
			<tag>button</tag>
			<text>Add to Cart</text>
		</element>
	</children>
</element>"""
		elements.append(element)

	dom = f"""
Current Page State:
URL: https://www.amazon.com/s?k=laptop
Title: Amazon.com : laptop

Interactive Elements on Page:
{''.join(elements)}

Page Metrics:
- Total elements: 200
- Clickable elements: 180
- Viewport: 1512x857
- Scroll position: 2400px
"""
	return dom[:20000]  # Ensure exactly 20k chars

async def test_complex_prompt(response_type: str = "short"):
	"""
	Test TTFT with complex prompt

	Args:
		response_type: "short" (1 action), "medium" (3 actions), "long" (5 actions + thinking)
	"""
	client = genai.Client(api_key=os.getenv('GOOGLE_API_KEY'))

	print(f"\n{'='*80}")
	print(f"Testing with {response_type.upper()} response")
	print(f"{'='*80}\n")

	# Create dummy image
	print("[Setup] Creating dummy 800x600 image...")
	image_data = create_dummy_image()
	print(f"[Setup] Image size: {len(image_data)} base64 chars")

	# Create large DOM text
	print("[Setup] Creating 20k char DOM text...")
	dom_text = create_large_dom_text()
	print(f"[Setup] DOM text size: {len(dom_text)} chars")
	print()

	# Create task instruction based on response type
	if response_type == "short":
		task = "Click on the first laptop product."
	elif response_type == "medium":
		task = "Scroll down, then click on the third product, then click 'Add to Cart'."
	else:  # long
		task = "Search for the cheapest gaming laptop, compare the top 3 results, select the best value option, add it to cart, and proceed to checkout."

	# Build complex prompt similar to browser-use
	prompt = f"""You are a browser automation agent. Your task is to perform web actions.

Current browser state:
{dom_text}

Task: {task}

Previous steps:
1. Navigated to amazon.com
2. Searched for 'laptop'
3. Waited for results to load

Respond with a JSON action array. Available actions: click, scroll, done.
"""

	# Complex schema similar to browser-use
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
								'index': {'type': 'integer'},
								'text': {'type': 'string'}
							}
						},
						'scroll': {
							'type': 'object',
							'properties': {
								'down': {'type': 'boolean'},
								'num_pages': {'type': 'number'}
							}
						},
						'done': {
							'type': 'object',
							'properties': {
								'text': {'type': 'string'},
								'success': {'type': 'boolean'}
							}
						}
					}
				}
			},
			'thinking': {'type': 'string'},
			'memory': {'type': 'string'}
		},
		'required': ['action']
	}

	config = types.GenerateContentConfig(
		temperature=0.0,
		response_mime_type='application/json',
		response_schema=schema,
		thinking_config={'thinking_budget': 0},
	)

	print(f"[{0.000:.3f}s] 🚀 Starting Gemini streaming request...")
	print(f"           Model: gemini-2.0-flash-exp")
	print(f"           Prompt size: {len(prompt)} chars")
	print(f"           Image size: {len(image_data)} base64 chars")
	print(f"           Thinking budget: 0")
	print()

	start = time.time()

	# Create streaming request with image
	stream = await client.aio.models.generate_content_stream(
		model='gemini-2.0-flash-exp',
		contents=[
			types.Content(
				role='user',
				parts=[
					types.Part(text=prompt),
					types.Part(inline_data=types.Blob(
						mime_type='image/png',
						data=base64.b64decode(image_data)
					))
				]
			)
		],
		config=config,
	)

	stream_create_time = time.time() - start
	print(f"[{stream_create_time:.3f}s] ✅ Stream object created")

	# Process chunks
	chunk_count = 0
	first_chunk_time = None
	action_complete_time = None
	total_text = ""

	async for chunk in stream:
		chunk_count += 1
		elapsed = time.time() - start

		if chunk_count == 1:
			first_chunk_time = elapsed
			print(f"[{elapsed:.3f}s] ⚡ FIRST CHUNK (TTFT: {elapsed:.3f}s)")

		if chunk.text:
			chunk_len = len(chunk.text)
			total_text += chunk.text

			# Check if we have complete action array (simplified check)
			open_brackets = total_text.count('[')
			close_brackets = total_text.count(']')

			if action_complete_time is None and open_brackets > 0 and open_brackets == close_brackets:
				action_complete_time = elapsed
				print(f"[{elapsed:.3f}s] 🎯 ACTION ARRAY COMPLETE (detected by bracket count)")

			preview = chunk.text[:80].replace('\n', ' ')
			print(f"[{elapsed:.3f}s] Chunk #{chunk_count}: {chunk_len} chars - {repr(preview)}")

	total_time = time.time() - start

	print()
	print(f"[{total_time:.3f}s] ✅ Stream complete")
	print(f"           Total chunks: {chunk_count}")
	print(f"           TTFT: {first_chunk_time:.3f}s")
	print(f"           Action complete: {action_complete_time:.3f}s (delta: {action_complete_time - first_chunk_time:.3f}s)")
	print(f"           Total time: {total_time:.3f}s")
	print(f"           Response length: {len(total_text)} chars")
	print()

	if first_chunk_time < 1.0:
		print(f"✅ GOOD: TTFT {first_chunk_time:.3f}s is < 1.0s")
	else:
		print(f"⚠️  SLOW: TTFT {first_chunk_time:.3f}s is >= 1.0s")

	if action_complete_time and action_complete_time < 1.5:
		print(f"✅ GOOD: Actions ready at {action_complete_time:.3f}s (< 1.5s)")
	elif action_complete_time:
		print(f"⚠️  SLOW: Actions ready at {action_complete_time:.3f}s (>= 1.5s)")

	return {
		'ttft': first_chunk_time,
		'action_time': action_complete_time,
		'total_time': total_time,
		'response_len': len(total_text)
	}

async def main():
	"""Test different response lengths"""
	print("="*80)
	print("Testing Gemini TTFT with Complex Prompts (browser-use simulation)")
	print("="*80)

	# Try to import PIL, install if needed
	try:
		from PIL import Image
	except ImportError:
		print("\n⚠️  Installing Pillow for image generation...")
		import subprocess
		subprocess.run(['uv', 'add', 'pillow'], check=True)
		from PIL import Image

	results = {}

	# Test short response
	results['short'] = await test_complex_prompt('short')
	await asyncio.sleep(1)

	# Test medium response
	results['medium'] = await test_complex_prompt('medium')
	await asyncio.sleep(1)

	# Test long response
	results['long'] = await test_complex_prompt('long')

	# Summary
	print("\n" + "="*80)
	print("SUMMARY")
	print("="*80)
	print(f"{'Response Type':<15} {'TTFT':<12} {'Action Time':<15} {'Total Time':<12}")
	print("-"*80)
	for resp_type, data in results.items():
		print(f"{resp_type.upper():<15} {data['ttft']:.3f}s{'':<6} {data['action_time']:.3f}s{'':<7} {data['total_time']:.3f}s")
	print()
	print(f"Average TTFT: {sum(r['ttft'] for r in results.values()) / len(results):.3f}s")
	print(f"Average Action Time: {sum(r['action_time'] for r in results.values()) / len(results):.3f}s")

if __name__ == '__main__':
	asyncio.run(main())
