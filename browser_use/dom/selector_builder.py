"""Robust CSS selector builder with fallback strategies for web scraping."""

import re
from typing import Any

from browser_use.dom.views import EnhancedDOMTreeNode


def escape_css_identifier(value: str) -> str:
	"""
	Escape special characters in CSS identifiers (IDs, classes, attribute values).

	CSS identifiers need escaping for: . : [ ] ( ) / @ $ % & * + , ; = ! # ~ ^
	Tailwind and modern frameworks often use these in class names.
	"""
	if not value:
		return value

	# Characters that need escaping in CSS selectors
	special_chars = r'[\\!"#$%&\'()*+,./:;<=>?@\[\]^`{|}~]'

	# Escape special characters with backslash
	escaped = re.sub(special_chars, r'\\\g<0>', value)

	# If starts with digit, prepend backslash and space
	if escaped and escaped[0].isdigit():
		escaped = f'\\3{escaped[0]} {escaped[1:]}'

	return escaped


def is_valid_css_value(value: str) -> bool:
	"""Check if attribute value is safe for direct CSS selector use."""
	if not value or len(value) > 100:
		return False

	# Reject if contains too many special chars (likely obfuscated or encoded)
	special_count = sum(1 for c in value if c in r'[](){}:;,./\|@#$%^&*+=!~`"\'')
	if special_count > len(value) * 0.3:
		return False

	# Reject whitespace-heavy values (use text search instead)
	if value.count(' ') > 5:
		return False

	return True


def build_robust_selector(
	tag_name: str,
	element_id: str | None = None,
	classes: list[str] | None = None,
	attributes: dict[str, Any] | None = None,
	max_classes: int = 3,
) -> str:
	"""
	Build a robust CSS selector with fallback strategies.

	Priority order (most to least specific):
	1. ID selector (if valid and unique)
	2. Tag + multiple classes (most specific combo)
	3. Tag + data-* attributes (stable tracking/component IDs)
	4. Tag + semantic attributes (name, type, role, aria-label)
	5. Tag + partial attribute matches (for dynamic values)
	6. Tag only (last resort)

	Args:
		tag_name: HTML tag name (div, button, input, etc.)
		element_id: Element ID attribute
		classes: List of CSS classes
		attributes: Dictionary of HTML attributes
		max_classes: Maximum number of classes to include (default 3)

	Returns:
		CSS selector string

	Examples:
		>>> build_robust_selector('button', element_id='submit-btn')
		'#submit-btn'

		>>> build_robust_selector('div', classes=['product-card', 'featured'])
		'div.product-card.featured'

		>>> build_robust_selector('a', attributes={'data-asin': 'B00ABC123'})
		'a[data-asin="B00ABC123"]'

		>>> build_robust_selector('input', attributes={'type': 'email', 'name': 'user-email'})
		'input[type="email"][name="user-email"]'
	"""
	tag = tag_name.lower() if tag_name else 'div'
	parts: list[str] = []

	# Strategy 1: ID selector (most specific, but only if it looks stable)
	if element_id and is_valid_css_value(element_id):
		# Check if ID looks dynamically generated (uuid, timestamp, random hash)
		if not re.match(r'^[a-f0-9]{8,}$|^\d{10,}$|^[A-Z0-9]{20,}$', element_id):
			# ID looks stable, use it directly
			return f'#{escape_css_identifier(element_id)}'

	# Strategy 2: Tag + Data attributes (MOST stable for e-commerce/tracking)
	# Prioritize data attributes BEFORE classes because they're more stable
	if attributes:
		data_attrs = {k: v for k, v in attributes.items() if k.startswith('data-') and v}

		# Priority data attributes (most stable)
		priority_data = [
			'data-testid',
			'data-cy',
			'data-test',
			'data-qa',
			'data-automation',
			'data-asin',
			'data-product-id',
			'data-sku',
			'data-item-id',
			'data-component-type',
			'data-component-id',
			'data-element-id',
			'data-widget-id',
		]

		for data_key in priority_data:
			if data_key in data_attrs:
				value = str(data_attrs[data_key])
				if is_valid_css_value(value):
					escaped_value = value.replace('"', '\\"')
					# Return immediately - data attributes are most stable
					return f'{tag}[{data_key}="{escaped_value}"]'

	# Strategy 3: Tag + Classes (if no data attributes available)
	if classes:
		# Filter out obfuscated/dynamic classes (random hashes, very short, very long)
		stable_classes = [
			c
			for c in classes
			if c
			and len(c) >= 2  # Too short likely generated
			and len(c) <= 50  # Too long likely concatenated
			and not re.match(r'^[a-f0-9]{6,}$', c)  # Hash-like
			and not re.match(r'^_[a-zA-Z0-9]{5,}$', c)  # CSS module hash
		]

		if stable_classes:
			# Use up to max_classes for specificity
			selected_classes = stable_classes[:max_classes]
			class_str = '.'.join(escape_css_identifier(c) for c in selected_classes)
			parts.append(f'{tag}.{class_str}')

	# Strategy 4: Tag + Semantic attributes (name, type, role, aria-*)
	if attributes and not parts:
		semantic_attrs = {}

		# Collect semantic attributes in priority order
		priority_attrs = ['name', 'type', 'role', 'aria-label', 'placeholder', 'title', 'alt']

		for attr_key in priority_attrs:
			if attr_key in attributes:
				value = str(attributes[attr_key])
				if value and is_valid_css_value(value):
					semantic_attrs[attr_key] = value
					if len(semantic_attrs) >= 2:
						break

		if semantic_attrs:
			attr_strs = []
			for attr_key, attr_value in list(semantic_attrs.items())[:2]:
				# For text-heavy attributes, use partial match
				if attr_key in ('aria-label', 'title', 'alt', 'placeholder') and len(attr_value) > 30:
					# Extract first few meaningful words
					words = attr_value.split()[:3]
					if words:
						partial = ' '.join(words)
						escaped_partial = partial.replace('"', '\\"')
						attr_strs.append(f'[{attr_key}*="{escaped_partial}"]')
				else:
					escaped_value = attr_value.replace('"', '\\"')
					attr_strs.append(f'[{attr_key}="{escaped_value}"]')

			if attr_strs:
				parts.append(f'{tag}{"".join(attr_strs)}')

	# Strategy 5: Tag + any stable attribute (href, src, etc.)
	if attributes and not parts:
		stable_attrs = ['href', 'src', 'action', 'for']
		for attr_key in stable_attrs:
			if attr_key in attributes:
				value = str(attributes[attr_key])
				if value and is_valid_css_value(value):
					# For URLs, use partial match on path (ignore query params)
					if attr_key in ('href', 'src', 'action'):
						if '?' in value:
							path_part = value.split('?')[0]
						else:
							path_part = value

						# Use last segment of path for more stable selector
						if '/' in path_part:
							segments = [s for s in path_part.split('/') if s]
							if segments:
								last_segment = segments[-1]
								if len(last_segment) > 3 and len(last_segment) < 50:
									escaped_segment = last_segment.replace('"', '\\"')
									parts.append(f'{tag}[{attr_key}*="{escaped_segment}"]')
									break

					# Fall back to exact match if partial didn't work
					escaped_value = value.replace('"', '\\"')
					parts.append(f'{tag}[{attr_key}="{escaped_value}"]')
					break

	# Strategy 6: Tag only (last resort)
	if not parts:
		parts.append(tag)

	# Return first (most specific) selector
	return parts[0] if parts else tag


def build_selector_with_fallbacks(
	tag_name: str,
	element_id: str | None = None,
	classes: list[str] | None = None,
	attributes: dict[str, Any] | None = None,
	max_fallbacks: int = 3,
) -> list[str]:
	"""
	Build multiple selector fallbacks in priority order.

	Use this when you want to try multiple strategies until one works.

	Returns:
		List of selectors from most to least specific

	Example usage in extraction:
		```python
		selectors = build_selector_with_fallbacks(
			'div',
			classes=['product-card'],
			attributes={'data-asin': 'B00ABC123'}
		)

		element = None
		for selector in selectors:
			element = document.querySelector(selector)
			if element:
				break
		```
	"""
	selectors: list[str] = []
	tag = tag_name.lower() if tag_name else 'div'

	# 1. ID-based (if stable)
	if element_id and is_valid_css_value(element_id):
		if not re.match(r'^[a-f0-9]{8,}$|^\d{10,}$|^[A-Z0-9]{20,}$', element_id):
			selectors.append(f'#{escape_css_identifier(element_id)}')

	# 2. Data attributes (most stable)
	if attributes:
		priority_data = [
			'data-testid',
			'data-cy',
			'data-asin',
			'data-product-id',
			'data-component-type',
		]
		for data_key in priority_data:
			if data_key in attributes:
				value = str(attributes[data_key])
				if is_valid_css_value(value):
					escaped_value = value.replace('"', '\\"')
					selectors.append(f'{tag}[{data_key}="{escaped_value}"]')
					break

	# 3. Tag + classes
	if classes:
		stable_classes = [
			c
			for c in classes
			if c and len(c) >= 2 and len(c) <= 50 and not re.match(r'^[a-f0-9]{6,}$', c)
		]
		if stable_classes:
			class_str = '.'.join(escape_css_identifier(c) for c in stable_classes[:2])
			selectors.append(f'{tag}.{class_str}')

	# 4. Tag + semantic attributes
	if attributes:
		for attr_key in ['name', 'type', 'role']:
			if attr_key in attributes:
				value = str(attributes[attr_key])
				if value and is_valid_css_value(value):
					escaped_value = value.replace('"', '\\"')
					selectors.append(f'{tag}[{attr_key}="{escaped_value}"]')
					break

	# 5. Tag + aria-label (partial match)
	if attributes and 'aria-label' in attributes:
		aria_value = str(attributes['aria-label'])
		if aria_value and len(aria_value) > 5:
			words = aria_value.split()[:2]
			if words:
				partial = ' '.join(words)
				escaped_partial = partial.replace('"', '\\"')
				selectors.append(f'{tag}[aria-label*="{escaped_partial}"]')

	# 6. Tag only (last resort)
	if not selectors or len(selectors) < max_fallbacks:
		selectors.append(tag)

	return selectors[:max_fallbacks]


def get_selector_for_element_node(node: EnhancedDOMTreeNode, max_classes: int = 3) -> str:
	"""
	Build robust selector from an EnhancedDOMTreeNode.

	Convenience wrapper around build_robust_selector for DOM tree nodes.
	"""
	element_id = node.attributes.get('id') if node.attributes else None
	class_str = node.attributes.get('class') if node.attributes else None
	classes = class_str.split() if class_str else None

	return build_robust_selector(
		tag_name=node.tag_name,
		element_id=element_id,
		classes=classes,
		attributes=node.attributes or {},
		max_classes=max_classes,
	)
