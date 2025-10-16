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
	'ul',
	'ol',
	'li',
	'img',
	'iframe',
}


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
		- Limit text to 80 chars
		- Minimal scroll info
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

			# Skip invisible elements
			if not is_visible and tag not in ['iframe', 'frame']:
				return DOMEvalSerializer._serialize_children(node, include_attributes, depth)

			# Build compact attributes string
			attributes_str = DOMEvalSerializer._build_compact_attributes(node.original_node)

			# Decide if this element should be shown
			is_semantic = tag in SEMANTIC_ELEMENTS
			has_useful_attrs = bool(attributes_str)
			has_text_content = DOMEvalSerializer._has_direct_text(node)

			# Skip generic containers without useful attributes
			if not is_semantic and not has_useful_attrs and not has_text_content:
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

			# Process children with increased depth
			children_text = DOMEvalSerializer._serialize_children(node, include_attributes, depth + 1)
			if children_text:
				formatted_text.append(children_text)

		elif node.original_node.node_type == NodeType.TEXT_NODE:
			# Text nodes are handled inline with their parent
			pass

		elif node.original_node.node_type == NodeType.DOCUMENT_FRAGMENT_NODE:
			# Minimal shadow DOM representation
			formatted_text.append(f'{depth_str}#shadow')
			children_text = DOMEvalSerializer._serialize_children(node, include_attributes, depth + 1)
			if children_text:
				formatted_text.append(children_text)

		return '\n'.join(formatted_text)

	@staticmethod
	def _serialize_children(node: SimplifiedNode, include_attributes: list[str], depth: int) -> str:
		"""Helper to serialize all children of a node."""
		children_output = []
		for child in node.children:
			child_text = DOMEvalSerializer.serialize_tree(child, include_attributes, depth)
			if child_text:
				children_output.append(child_text)
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
					if value and attr == 'class':
						# For class, limit to first 2 classes to save space
						classes = value.split()[:2]
						value = ' '.join(classes)
					if value:
						# Cap at 50 chars
						value = cap_text_length(value, 50)
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
		"""Get text content to display inline (max 80 chars)."""
		text_parts = []
		for child in node.children:
			if child.original_node.node_type == NodeType.TEXT_NODE:
				text = child.original_node.node_value.strip() if child.original_node.node_value else ''
				if text and len(text) > 1:
					text_parts.append(text)

		if not text_parts:
			return ''

		combined = ' '.join(text_parts)
		return cap_text_length(combined, 80)
