def cap_text_length(text: str, max_length: int) -> str:
	"""Cap text length for display."""
	if len(text) <= max_length:
		return text
	return text[:max_length] + '...'


def generate_css_selector_for_element(enhanced_node) -> str | None:
	"""Generate a robust CSS selector using node properties.

	This function builds CSS selectors with the following priority:
	1. ID (if valid and unique-looking)
	2. Tag + classes (all valid classes)
	3. Tag + safe attributes (data-*, aria-*, name, type, etc.)

	Args:
		enhanced_node: An EnhancedDOMTreeNode instance

	Returns:
		A CSS selector string, or None if the node is invalid
	"""
	import re

	if not enhanced_node or not hasattr(enhanced_node, 'tag_name') or not enhanced_node.tag_name:
		return None

	# Get base selector from tag name
	tag_name = enhanced_node.tag_name.lower().strip()
	if not tag_name or not re.match(r'^[a-zA-Z][a-zA-Z0-9]*$', tag_name):
		return None

	css_selector = tag_name

	# Add ID if available (most specific)
	if enhanced_node.attributes and 'id' in enhanced_node.attributes:
		element_id = enhanced_node.attributes['id']
		if element_id and element_id.strip():
			# Validate ID contains only valid characters
			if re.match(r'^[a-zA-Z][a-zA-Z0-9_-]*$', element_id.strip()):
				return f'#{element_id.strip()}'

	# Handle class attributes - include ALL valid classes for better specificity
	if enhanced_node.attributes and 'class' in enhanced_node.attributes and enhanced_node.attributes['class']:
		# Define a regex pattern for valid class names in CSS
		valid_class_name_pattern = re.compile(r'^[a-zA-Z_][a-zA-Z0-9_-]*$')

		# Iterate through the class attribute values
		classes = enhanced_node.attributes['class'].split()
		for class_name in classes:
			# Strip whitespace and skip empty class names
			class_name = class_name.strip()
			if not class_name:
				continue

			# Check if the class name is valid
			if valid_class_name_pattern.match(class_name):
				# Append the valid class name to the CSS selector
				css_selector += f'.{class_name}'

	# Expanded set of safe attributes that are stable and useful for selection
	SAFE_ATTRIBUTES = {
		# Data attributes (stable identifiers)
		'data-id',
		'data-qa',
		'data-cy',
		'data-testid',
		'data-asin',
		'data-component-type',
		'data-component-id',
		# Amazon-specific data attributes
		'data-csa-c-type',
		'data-csa-c-slot-id',
		'data-csa-c-content-id',
		'data-nav-ref',
		'data-nav-role',
		# Standard HTML attributes
		'name',
		'type',
		'placeholder',
		# Accessibility attributes
		'aria-label',
		'aria-labelledby',
		'aria-describedby',
		'role',
		# Common form attributes
		'for',
		'autocomplete',
		'required',
		'readonly',
		# Media attributes
		'alt',
		'title',
		'src',
		# Link attributes
		'href',
		'target',
	}

	# Handle other attributes
	if enhanced_node.attributes:
		for attribute, value in enhanced_node.attributes.items():
			if attribute == 'class':
				continue

			# Skip invalid attribute names
			if not attribute.strip():
				continue

			if attribute not in SAFE_ATTRIBUTES:
				continue

			# Escape special characters in attribute names
			safe_attribute = attribute.replace(':', r'\:')

			# Handle different value cases
			if value == '':
				css_selector += f'[{safe_attribute}]'
			elif any(char in value for char in '"\'<>`\n\r\t'):
				# Use contains for values with special characters
				# For newline-containing text, only use the part before the newline
				if '\n' in value:
					value = value.split('\n')[0]
				# Regex-substitute *any* whitespace with a single space, then strip.
				collapsed_value = re.sub(r'\s+', ' ', value).strip()
				# Escape embedded double-quotes.
				safe_value = collapsed_value.replace('"', '\\"')
				css_selector += f'[{safe_attribute}*="{safe_value}"]'
			else:
				css_selector += f'[{safe_attribute}="{value}"]'

	# Final validation: ensure the selector doesn't contain problematic unescaped characters
	# Note: Double quotes in attribute selectors like [attr="value"] are valid!
	# Only reject if we have newlines/tabs which indicate malformed selectors
	if css_selector and not any(char in css_selector for char in ['\n', '\r', '\t']):
		return css_selector

	# If we get here, the selector was problematic, return just the tag name as fallback
	return tag_name
