# @file purpose: Concise evaluation serializer for DOM trees - optimized for LLM query writing


from browser_use.dom.utils import cap_text_length
from browser_use.dom.views import (
	EnhancedDOMTreeNode,
	NodeType,
	SimplifiedNode,
)

# Critical attributes for query writing and form interaction
EVAL_KEY_ATTRIBUTES = [
	'id',
	'class',
	'name',
	'type',
	'placeholder',
	'aria-label',
	'role',
	'value',
	'href',
	'data-testid',
	'alt',  # for images
	'title',  # useful for tooltips/link context
	# State attributes (critical for form interaction)
	'checked',
	'selected',
	'disabled',
	'required',
	'readonly',
	# ARIA states
	'aria-expanded',
	'aria-pressed',
	'aria-checked',
	'aria-selected',
	'aria-invalid',
	# Validation attributes (help agents avoid brute force)
	'pattern',
	'min',
	'max',
	'minlength',
	'maxlength',
	'step',
	'aria-valuemin',
	'aria-valuemax',
	'aria-valuenow',
]

# Semantic elements that should always be shown
SEMANTIC_ELEMENTS = {
	'h1',
	'h2',
	'h3',
	'h4',
	'h5',
	'h6',
	'a',
	'button',
	'input',
	'textarea',
	'select',
	'form',
	'label',
	'nav',
	'header',
	'footer',
	'main',
	'article',
	'section',
	'table',
	'thead',
	'tbody',
	'tr',
	'th',
	'td',
	'ul',
	'ol',
	'li',
	'img',
	'iframe',
	'video',
	'audio',
}

# Container elements that can be collapsed if they only wrap one child
COLLAPSIBLE_CONTAINERS = {'div', 'span', 'section', 'article'}


class DOMEvalSerializer:
	"""Ultra-concise DOM serializer for quick LLM query writing."""

	@staticmethod
	def serialize_tree(node: SimplifiedNode | None, include_attributes: list[str], depth: int = 0) -> str:
		"""
		Serialize complete DOM tree structure for LLM understanding.

		Strategy:
		- Show ALL elements to preserve DOM structure
		- Non-interactive elements show just tag name
		- Interactive elements show full attributes + [index]
		- Self-closing tags only (no closing tags)
		- Limit text to 25 chars inline
		- Minimal shadow/iframe notation
		"""
		if not node:
			return ''

		# Skip excluded nodes but process children
		if hasattr(node, 'excluded_by_parent') and node.excluded_by_parent:
			return DOMEvalSerializer._serialize_children(node, include_attributes, depth)

		# Skip nodes marked as should_display=False
		if not node.should_display:
			return DOMEvalSerializer._serialize_children(node, include_attributes, depth)

		formatted_text = []
		depth_str = depth * '\t'

		if node.original_node.node_type == NodeType.ELEMENT_NODE:
			tag = node.original_node.tag_name.lower()
			is_visible = node.original_node.snapshot_node and node.original_node.is_visible

			# Special handling for iframes - show them with their content
			if tag in ['iframe', 'frame']:
				return DOMEvalSerializer._serialize_iframe(node, include_attributes, depth)

			# Build compact attributes string
			attributes_str = DOMEvalSerializer._build_compact_attributes(node.original_node)

			# Check element properties
			has_text_content = DOMEvalSerializer._has_direct_text(node)
			has_children = len(node.children) > 0
			has_interactive_index = node.interactive_index is not None

			# Build element representation
			# Always show tag to preserve complete DOM structure
			line = f'{depth_str}<{tag}'

			# Add attributes only for interactive elements or elements with useful attributes
			if attributes_str or has_interactive_index:
				# Add interactive index notation [index] for elements with interactive_index
				if has_interactive_index:
					line += f' [{node.interactive_index}]'
				if attributes_str:
					line += f' {attributes_str}'


				# Add scroll info if element is scrollable
				if node.original_node.should_show_scroll_info:
					scroll_text = node.original_node.get_scroll_info_text()
					if scroll_text:
						line += f' scroll="{scroll_text}"'

			# Add inline text if present (keep it on same line for compactness)
			inline_text = DOMEvalSerializer._get_inline_text(node)
			if inline_text:
				line += f'>{inline_text}'
			else:
				line += ' />'

			formatted_text.append(line)

			# Process children with increased depth (but only if we have text-free children)
			if has_children and not inline_text:
				children_text = DOMEvalSerializer._serialize_children(node, include_attributes, depth + 1)
				if children_text:
					formatted_text.append(children_text)

		elif node.original_node.node_type == NodeType.TEXT_NODE:
			# Text nodes are handled inline with their parent
			pass

		elif node.original_node.node_type == NodeType.DOCUMENT_FRAGMENT_NODE:
			# Shadow DOM - just show children directly with minimal marker
			if node.children:
				formatted_text.append(f'{depth_str}#shadow')
				children_text = DOMEvalSerializer._serialize_children(node, include_attributes, depth + 1)
				if children_text:
					formatted_text.append(children_text)

		return '\n'.join(formatted_text)

	@staticmethod
	def _serialize_children(node: SimplifiedNode, include_attributes: list[str], depth: int) -> str:
		"""Helper to serialize all children of a node."""
		children_output = []

		# Serialize all children to preserve complete DOM structure
		for child in node.children:
			child_text = DOMEvalSerializer.serialize_tree(child, include_attributes, depth)
			if child_text:
				children_output.append(child_text)

		return '\n'.join(children_output)

	@staticmethod
	def _build_compact_attributes(node: EnhancedDOMTreeNode) -> str:
		"""Build ultra-compact attributes string with only key attributes."""
		attributes_to_include = {}

		# Collect HTML attributes first
		if node.attributes:
			for attr in EVAL_KEY_ATTRIBUTES:
				if attr in node.attributes:
					value = str(node.attributes[attr]).strip()
					if not value:
						continue

					# Special handling for different attributes
					if attr == 'class':
						# For class, limit to first 2 classes to save space
						classes = value.split()[:2]
						value = ' '.join(classes)
						value = cap_text_length(value, 25)
					elif attr == 'href':
						# Keep full href for navigation
						pass
					else:
						# Cap at 25 chars for other attributes
						value = cap_text_length(value, 25)

					attributes_to_include[attr] = value

		# Include AX properties (more reliable than HTML attributes)
		if node.ax_node and node.ax_node.properties:
			for prop in node.ax_node.properties:
				try:
					if prop.name in EVAL_KEY_ATTRIBUTES and prop.value is not None:
						# Convert boolean to lowercase string
						if isinstance(prop.value, bool):
							attributes_to_include[prop.name] = str(prop.value).lower()
						else:
							prop_value_str = str(prop.value).strip()
							if prop_value_str:
								attributes_to_include[prop.name] = prop_value_str
				except (AttributeError, ValueError):
					continue

		# Remove duplicate values (save tokens)
		if len(attributes_to_include) > 1:
			seen_values = {}
			keys_to_remove = set()
			for key, value in attributes_to_include.items():
				if len(value) > 5:  # Only dedupe longer values
					if value in seen_values:
						keys_to_remove.add(key)
					else:
						seen_values[value] = key
			for key in keys_to_remove:
				del attributes_to_include[key]

		# Remove redundant attributes
		# Role if it matches tag name
		if 'role' in attributes_to_include and attributes_to_include['role'].lower() == node.node_name.lower():
			del attributes_to_include['role']
		# Type if it matches tag name
		if 'type' in attributes_to_include and attributes_to_include['type'].lower() == node.node_name.lower():
			del attributes_to_include['type']
		# invalid="false" (only show when true)
		if 'invalid' in attributes_to_include and attributes_to_include['invalid'].lower() == 'false':
			del attributes_to_include['invalid']
		# aria-expanded if we have 'expanded' from AX tree
		if 'expanded' in attributes_to_include and 'aria-expanded' in attributes_to_include:
			del attributes_to_include['aria-expanded']

		# Add AX role if different from tag and not meaningless
		if node.ax_node and node.ax_node.role and node.ax_node.role.lower() != node.node_name.lower():
			role_lower = node.ax_node.role.lower()
			if role_lower not in ('none', 'presentation', 'generic') and 'role' not in attributes_to_include:
				attributes_to_include['role'] = node.ax_node.role

		# Build output string
		return ' '.join(f'{key}="{value}"' for key, value in attributes_to_include.items())

	@staticmethod
	def _has_direct_text(node: SimplifiedNode) -> bool:
		"""Check if node has direct text children (not nested in other elements)."""
		for child in node.children:
			if child.original_node.node_type == NodeType.TEXT_NODE:
				text = child.original_node.node_value.strip() if child.original_node.node_value else ''
				if len(text) > 1:
					return True
		return False

	@staticmethod
	def _get_inline_text(node: SimplifiedNode) -> str:
		"""Get text content to display inline (max 40 chars)."""
		text_parts = []
		for child in node.children:
			if child.original_node.node_type == NodeType.TEXT_NODE:
				text = child.original_node.node_value.strip() if child.original_node.node_value else ''
				if text and len(text) > 1:
					text_parts.append(text)

		if not text_parts:
			return ''

		combined = ' '.join(text_parts)
		return cap_text_length(combined, 75)

	@staticmethod
	def _serialize_iframe(node: SimplifiedNode, include_attributes: list[str], depth: int) -> str:
		"""Handle iframe serialization with content document."""
		formatted_text = []
		depth_str = depth * '\t'
		tag = node.original_node.tag_name.lower()

		# Build minimal iframe marker with key attributes
		attributes_str = DOMEvalSerializer._build_compact_attributes(node.original_node)
		line = f'{depth_str}<{tag}'
		if attributes_str:
			line += f' {attributes_str}'

		# Add scroll info for iframe content
		if node.original_node.should_show_scroll_info:
			scroll_text = node.original_node.get_scroll_info_text()
			if scroll_text:
				line += f' scroll="{scroll_text}"'

		line += ' />'
		formatted_text.append(line)

		# If iframe has content document, serialize its content
		if node.original_node.content_document:
			# Add marker for iframe content
			formatted_text.append(f'{depth_str}\t#iframe-content')

			# Process content document children
			for child_node in node.original_node.content_document.children_nodes or []:
				# Create temporary SimplifiedNode wrapper to reuse serialize_tree
				# We need to process the content document's DOM tree
				if child_node.tag_name.lower() == 'html':
					# Find body or start serializing from html
					for html_child in child_node.children:
						if html_child.tag_name.lower() in ['body', 'head']:
							# Only serialize body content for iframes
							if html_child.tag_name.lower() == 'body':
								for body_child in html_child.children:
									# Recursively process body children
									DOMEvalSerializer._serialize_document_node(body_child, formatted_text, include_attributes, depth + 2)
							break

		return '\n'.join(formatted_text)

	@staticmethod
	def _serialize_document_node(
		dom_node: EnhancedDOMTreeNode, output: list[str], include_attributes: list[str], depth: int
	) -> None:
		"""Helper to serialize a document node without SimplifiedNode wrapper."""
		depth_str = depth * '\t'

		if dom_node.node_type == NodeType.ELEMENT_NODE:
			tag = dom_node.tag_name.lower()

			# Build compact attributes string
			attributes_str = DOMEvalSerializer._build_compact_attributes(dom_node)

			# Build element line - always show tag to preserve structure
			line = f'{depth_str}<{tag}'

			# Only add attributes if element has them
			if attributes_str:
				line += f' {attributes_str}'

			# Get direct text content
			text_parts = []
			for child in dom_node.children:
				if child.node_type == NodeType.TEXT_NODE and child.node_value:
					text = child.node_value.strip()
					if text and len(text) > 1:
						text_parts.append(text)

			if text_parts:
				combined = ' '.join(text_parts)
				line += f'>{cap_text_length(combined, 30)}'
			else:
				line += ' />'

			output.append(line)

			# Process non-text children
			for child in dom_node.children:
				if child.node_type != NodeType.TEXT_NODE:
					DOMEvalSerializer._serialize_document_node(child, output, include_attributes, depth + 1)
