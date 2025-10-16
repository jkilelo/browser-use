# @file purpose: Evaluation-focused serializer for DOM trees (no interactive indexes, full structure)


from browser_use.dom.utils import cap_text_length
from browser_use.dom.views import (
	EnhancedDOMTreeNode,
	NodeType,
	SimplifiedNode,
)

# Additional attributes useful for evaluation context
EVAL_INCLUDE_ATTRIBUTES = [
	'class',  # Include class for better context
	'href',  # Include links
	'src',  # Include image/script sources
	'data-testid',  # Test IDs can be useful
	'data-test',
]


class DOMEvalSerializer:
	"""Serializes DOM trees for evaluation contexts without interactive indexes."""

	@staticmethod
	def serialize_tree(node: SimplifiedNode | None, include_attributes: list[str], depth: int = 0) -> str:
		"""
		Serialize the DOM tree for evaluation purposes.

		Key differences from interactive serializer:
		- No interactive indexes ([1], [2], etc.)
		- Includes full HTML structure up to interactive elements
		- Shows more attributes for context
		- Preserves all meaningful text content
		"""
		if not node:
			return ''

		# Skip rendering excluded nodes, but process their children
		if hasattr(node, 'excluded_by_parent') and node.excluded_by_parent:
			formatted_text = []
			for child in node.children:
				child_text = DOMEvalSerializer.serialize_tree(child, include_attributes, depth)
				if child_text:
					formatted_text.append(child_text)
			return '\n'.join(formatted_text)

		formatted_text = []
		depth_str = depth * '\t'
		next_depth = depth

		if node.original_node.node_type == NodeType.ELEMENT_NODE:
			# Skip displaying nodes marked as should_display=False
			if not node.should_display:
				for child in node.children:
					child_text = DOMEvalSerializer.serialize_tree(child, include_attributes, depth)
					if child_text:
						formatted_text.append(child_text)
				return '\n'.join(formatted_text)

			# Always show element nodes with enhanced attributes for context
			is_any_scrollable = node.original_node.is_actually_scrollable or node.original_node.is_scrollable
			should_show_scroll = node.original_node.should_show_scroll_info

			# Show all visible elements to provide full context
			is_visible = node.original_node.snapshot_node and node.original_node.is_visible
			if is_visible or is_any_scrollable or node.original_node.tag_name.upper() in ['IFRAME', 'FRAME'] or node.children:
				next_depth += 1

				# Build enhanced attributes string with more context
				text_content = ''
				attributes_html_str = DOMEvalSerializer._build_attributes_string(
					node.original_node, include_attributes, text_content
				)

				# Build the line with element context
				shadow_prefix = ''
				if node.is_shadow_host:
					# Check if any shadow children are closed
					has_closed_shadow = any(
						child.original_node.node_type == NodeType.DOCUMENT_FRAGMENT_NODE
						and child.original_node.shadow_root_type
						and child.original_node.shadow_root_type.lower() == 'closed'
						for child in node.children
					)
					shadow_prefix = '|SHADOW(closed)|' if has_closed_shadow else '|SHADOW(open)|'

				# Build opening tag with attributes
				if should_show_scroll:
					line = f'{depth_str}{shadow_prefix}|SCROLL|<{node.original_node.tag_name}'
				elif node.original_node.tag_name.upper() == 'IFRAME':
					line = f'{depth_str}{shadow_prefix}|IFRAME|<{node.original_node.tag_name}'
				elif node.original_node.tag_name.upper() == 'FRAME':
					line = f'{depth_str}{shadow_prefix}|FRAME|<{node.original_node.tag_name}'
				else:
					line = f'{depth_str}{shadow_prefix}<{node.original_node.tag_name}'

				if attributes_html_str:
					line += f' {attributes_html_str}'

				line += '>'

				# Add scroll information when applicable
				if should_show_scroll:
					scroll_info_text = node.original_node.get_scroll_info_text()
					if scroll_info_text:
						line += f' ({scroll_info_text})'

				formatted_text.append(line)

		elif node.original_node.node_type == NodeType.DOCUMENT_FRAGMENT_NODE:
			# Shadow DOM representation
			if node.original_node.shadow_root_type and node.original_node.shadow_root_type.lower() == 'closed':
				formatted_text.append(f'{depth_str}#shadow-root (closed)')
			else:
				formatted_text.append(f'{depth_str}#shadow-root (open)')

			next_depth += 1

			# Process shadow DOM children
			for child in node.children:
				child_text = DOMEvalSerializer.serialize_tree(child, include_attributes, next_depth)
				if child_text:
					formatted_text.append(child_text)

			# Close shadow DOM indicator
			if node.children:
				formatted_text.append(f'{depth_str}#shadow-root-end')

		elif node.original_node.node_type == NodeType.TEXT_NODE:
			# Include all visible text for full context
			is_visible = node.original_node.snapshot_node and node.original_node.is_visible
			if (
				is_visible
				and node.original_node.node_value
				and node.original_node.node_value.strip()
				and len(node.original_node.node_value.strip()) > 1
			):
				clean_text = node.original_node.node_value.strip()
				# For eval, keep more text content (up to 500 chars per text node)
				if len(clean_text) > 500:
					clean_text = clean_text[:497] + '...'
				formatted_text.append(f'{depth_str}{clean_text}')

		# Process children (for non-shadow elements)
		if node.original_node.node_type != NodeType.DOCUMENT_FRAGMENT_NODE:
			for child in node.children:
				child_text = DOMEvalSerializer.serialize_tree(child, include_attributes, next_depth)
				if child_text:
					formatted_text.append(child_text)

			# Add closing tag for element nodes with children
			if (
				node.original_node.node_type == NodeType.ELEMENT_NODE
				and node.children
				and node.should_display
				and (node.original_node.snapshot_node and node.original_node.is_visible or node.children)
			):
				formatted_text.append(f'{depth_str}</{node.original_node.tag_name}>')

		return '\n'.join(formatted_text)

	@staticmethod
	def _build_attributes_string(node: EnhancedDOMTreeNode, include_attributes: list[str], text: str) -> str:
		"""Build the attributes string for an element with enhanced context."""
		attributes_to_include = {}

		# Combine standard and eval-specific attributes
		all_attributes = list(set(include_attributes + EVAL_INCLUDE_ATTRIBUTES))

		# Include HTML attributes
		if node.attributes:
			attributes_to_include.update(
				{
					key: str(value).strip()
					for key, value in node.attributes.items()
					if key in all_attributes and str(value).strip() != ''
				}
			)

		# Include accessibility properties
		if node.ax_node and node.ax_node.properties:
			for prop in node.ax_node.properties:
				try:
					if prop.name in all_attributes and prop.value is not None:
						# Convert boolean to lowercase string, keep others as-is
						if isinstance(prop.value, bool):
							attributes_to_include[prop.name] = str(prop.value).lower()
						else:
							prop_value_str = str(prop.value).strip()
							if prop_value_str:
								attributes_to_include[prop.name] = prop_value_str
				except (AttributeError, ValueError):
					continue

		if not attributes_to_include:
			return ''

		# Remove duplicate values (but be more lenient than interactive serializer)
		ordered_keys = [key for key in all_attributes if key in attributes_to_include]

		if len(ordered_keys) > 1:
			keys_to_remove = set()
			seen_values = {}

			for key in ordered_keys:
				value = attributes_to_include[key]
				# Only dedupe very long values (>15 chars) to preserve more context
				if len(value) > 15:
					if value in seen_values:
						keys_to_remove.add(key)
					else:
						seen_values[value] = key

			for key in keys_to_remove:
				del attributes_to_include[key]

		# Remove attributes that duplicate accessibility data
		role = node.ax_node.role if node.ax_node else None
		if role and node.node_name == role:
			attributes_to_include.pop('role', None)

		# Remove type attribute if it matches the tag name (e.g. <button type="button">)
		if 'type' in attributes_to_include and attributes_to_include['type'].lower() == node.node_name.lower():
			del attributes_to_include['type']

		# Remove invalid attribute if it's false (only show when true)
		if 'invalid' in attributes_to_include and attributes_to_include['invalid'].lower() == 'false':
			del attributes_to_include['invalid']

		# Remove aria-expanded if we have expanded (prefer AX tree over HTML attribute)
		if 'expanded' in attributes_to_include and 'aria-expanded' in attributes_to_include:
			del attributes_to_include['aria-expanded']

		if attributes_to_include:
			# For eval, allow longer attribute values (200 chars instead of 100)
			return ' '.join(f'{key}="{cap_text_length(value, 200)}"' for key, value in attributes_to_include.items())

		return ''
