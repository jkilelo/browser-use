# @file purpose: Concise evaluation serializer for DOM trees - optimized for LLM query writing


from browser_use.dom.utils import cap_text_length
from browser_use.dom.views import (
	EnhancedDOMTreeNode,
	NodeType,
	SimplifiedNode,
)

# Critical attributes for query writing and form interaction
# NOTE: Removed 'id' and 'class' to force more robust structural selectors
EVAL_KEY_ATTRIBUTES = [
	'id',  # Removed - can have special chars, forces structural selectors
	'class',  # Removed - can have special chars like +, forces structural selectors
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
		Serialize DOM tree focusing on semantic/interactive elements.

		Strategy for conciseness:
		- Self-closing tags only (no closing tags)
		- Skip meaningless containers (divs/spans without useful attributes)
		- Prioritize semantic elements
		- Flatten single-child wrappers
		- Limit text to 80 chars
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

			# Skip invisible elements (except iframes which might have visible content)
			if not is_visible and tag not in ['iframe', 'frame']:
				return DOMEvalSerializer._serialize_children(node, include_attributes, depth)

			# Special handling for iframes - show them with their content
			if tag in ['iframe', 'frame']:
				return DOMEvalSerializer._serialize_iframe(node, include_attributes, depth)

			# Build compact attributes string
			attributes_str = DOMEvalSerializer._build_compact_attributes(node.original_node)

			# Decide if this element should be shown
			is_semantic = tag in SEMANTIC_ELEMENTS
			has_useful_attrs = bool(attributes_str)
			has_text_content = DOMEvalSerializer._has_direct_text(node)
			has_children = len(node.children) > 0

			# Skip generic containers without useful attributes or semantic value
			if not is_semantic and not has_useful_attrs and not has_text_content:
				return DOMEvalSerializer._serialize_children(node, include_attributes, depth)

			# Collapse single-child wrappers without useful attributes
			if (
				tag in COLLAPSIBLE_CONTAINERS
				and not has_useful_attrs
				and not has_text_content
				and len(node.children) == 1
			):
				# Skip this wrapper and just show the child
				return DOMEvalSerializer._serialize_children(node, include_attributes, depth)

			# Build compact element representation
			line = f'{depth_str}'
			# Add backend node ID notation - [interactive_X] for interactive, [X] for others
			if node.interactive_index is not None:
				line += f' [i_{node.original_node.backend_node_id}]'
			else:
				line += f' [{node.original_node.backend_node_id}]'
			line += f'<{tag}'

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

		# Check if parent is a list container (ul, ol)
		is_list_container = (
			node.original_node.node_type == NodeType.ELEMENT_NODE
			and node.original_node.tag_name.lower() in ['ul', 'ol']
		)

		# Track list items and consecutive links
		li_count = 0
		max_list_items = 5
		consecutive_link_count = 0
		max_consecutive_links = 5
		total_links_skipped = 0

		for child in node.children:
			# If we're in a list container and this child is an li element
			if is_list_container and child.original_node.node_type == NodeType.ELEMENT_NODE:
				if child.original_node.tag_name.lower() == 'li':
					li_count += 1
					# Skip li elements after the 5th one
					if li_count > max_list_items:
						continue

			# Track consecutive anchor tags (links)
			if child.original_node.node_type == NodeType.ELEMENT_NODE:
				if child.original_node.tag_name.lower() == 'a':
					consecutive_link_count += 1
					# Skip links after the 5th consecutive one
					if consecutive_link_count > max_consecutive_links:
						total_links_skipped += 1
						continue
				else:
					# Reset counter when we hit a non-link element
					# But first add truncation message if we skipped links
					if total_links_skipped > 0:
						depth_str = depth * '\t'
						children_output.append(f'{depth_str}... ({total_links_skipped} more links in this list)')
						total_links_skipped = 0
					consecutive_link_count = 0

			child_text = DOMEvalSerializer.serialize_tree(child, include_attributes, depth)
			if child_text:
				children_output.append(child_text)

		# Add truncation message if we skipped items at the end
		if is_list_container and li_count > max_list_items:
			depth_str = depth * '\t'
			children_output.append(f'{depth_str}... ({li_count - max_list_items} more items in this list)')

		# Add truncation message for links if we skipped any at the end
		if total_links_skipped > 0:
			depth_str = depth * '\t'
			children_output.append(f'{depth_str}... ({total_links_skipped} more links in this list)')

		return '\n'.join(children_output)

	@staticmethod
	def _build_compact_attributes(node: EnhancedDOMTreeNode) -> str:
		"""Build ultra-compact attributes string with only key attributes."""
		attrs = []

		# Prioritize attributes that help with query writing
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
						value = cap_text_length(value, 40)
					elif attr == 'href':
						# For href, cap at 20 chars to save space
						value = cap_text_length(value, 40)
					else:
						# Cap at 25 chars for other attributes
						value = cap_text_length(value, 40)

					attrs.append(f'{attr}="{value}"')

		# Add AX role if different from tag and not a meaningless/presentational role
		# Skip role="none", "presentation", and "generic" as they indicate decorative or semantically empty elements
		if node.ax_node and node.ax_node.role and node.ax_node.role.lower() != node.node_name.lower():
			role_lower = node.ax_node.role.lower()
			if role_lower not in ('none', 'presentation', 'generic'):
				attrs.append(f'role="{node.ax_node.role}"')

		return ' '.join(attrs)

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
		return cap_text_length(combined, 25)

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

			# Skip invisible and non-semantic elements
			is_visible = dom_node.snapshot_node and dom_node.is_visible
			if not is_visible:
				return

			# Check if semantic or has useful attributes
			is_semantic = tag in SEMANTIC_ELEMENTS
			attributes_str = DOMEvalSerializer._build_compact_attributes(dom_node)

			if not is_semantic and not attributes_str:
				# Skip but process children
				for child in dom_node.children:
					DOMEvalSerializer._serialize_document_node(child, output, include_attributes, depth)
				return

			# Build element line
			line = f'{depth_str}<{tag}'
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
