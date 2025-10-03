"""
Check actual prompt size sent to Gemini in screenshot test
"""
import random
import time

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

# Generate the text
dom_text = create_text(40000, unique_id=1)
task = "Click on the first product and add to cart."

prompt = f"""{dom_text}

Task: {task}

Respond with JSON action array."""

print("Actual prompt analysis:")
print("=" * 80)
print(f"DOM text length: {len(dom_text):,} chars")
print(f"Full prompt length: {len(prompt):,} chars")
print(f"Estimated tokens (÷4): ~{len(prompt) // 4:,} tokens")
print()
print("Schema is also sent separately, adds ~100-200 tokens")
print("Image tokens: ~200-500 tokens for small images")
print()
print(f"Expected total prompt tokens: ~{(len(prompt) // 4) + 200 + 300:,}")
print()
print("If we're seeing 19,299 prompt tokens, the DOM might be duplicated or")
print("there's something wrong with how we're constructing the prompt")
