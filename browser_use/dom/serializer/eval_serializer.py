# @file purpose: Concise evaluation serializer for DOM trees - optimized for LLM query writing


from browser_use.dom.utils import cap_text_length
from browser_use.dom.views import (
	EnhancedDOMTreeNode,
	NodeType,
	SimplifiedNode,
)

# Only the most critical attributes for query writing
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
			line = f'{depth_str}<{tag}'

			if attributes_str:
				line += f' {attributes_str}'

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

		# Track list items if we're in a list
		li_count = 0
		max_list_items = 5

		for child in node.children:
			# If we're in a list container and this child is an li element
			if is_list_container and child.original_node.node_type == NodeType.ELEMENT_NODE:
				if child.original_node.tag_name.lower() == 'li':
					li_count += 1
					# Skip li elements after the 5th one
					if li_count > max_list_items:
						continue

			child_text = DOMEvalSerializer.serialize_tree(child, include_attributes, depth)
			if child_text:
				children_output.append(child_text)

		# Add truncation message if we skipped items
		if is_list_container and li_count > max_list_items:
			depth_str = depth * '\t'
			children_output.append(f'{depth_str}... ({li_count - max_list_items} more items - use evaluate to explore more.)')

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
						value = cap_text_length(value, 25)
					elif attr == 'href':
						# For href, cap at 20 chars to save space
						value = cap_text_length(value, 20)
					else:
						# Cap at 25 chars for other attributes
						value = cap_text_length(value, 25)

					attrs.append(f'{attr}="{value}"')

		# Add AX role if different from tag
		if node.ax_node and node.ax_node.role and node.ax_node.role.lower() != node.node_name.lower():
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
