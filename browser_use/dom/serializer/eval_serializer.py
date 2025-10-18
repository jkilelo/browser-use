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
	def _detect_pagination(node: SimplifiedNode | None) -> str | None:
		"""Detect pagination indicators and return concise note if found."""
		if not node:
			return None

		def search_pagination(n: SimplifiedNode) -> bool:
			if n.original_node.node_type == NodeType.ELEMENT_NODE:
				text = n.original_node.get_all_children_text().lower()
				attrs = n.original_node.attributes or {}
				tag = n.original_node.tag_name.lower()

				# Check for pagination patterns
				if any([
					'next' in text and 'page' in text,
					'prev' in text and 'page' in text,
					'load more' in text,
					'show more' in text,
					any('pagination' in str(v).lower() for v in attrs.values()),
					tag == 'nav' and 'page' in text,
				]):
					return True

			for child in n.children:
				if search_pagination(child):
					return True
			return False

		if search_pagination(node):
			return 'PAGINATION DETECTED: Extract ALL pages before calling done()'
		return None

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

		# Detect pagination at root level
		pagination_note = None
		if depth == 0:
			pagination_note = DOMEvalSerializer._detect_pagination(node)

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

		# Prepend pagination note if detected at root level
		if pagination_note and depth == 0:
			formatted_text.insert(0, pagination_note)

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

		# Check if parent is a table container
		is_table_container = (
			node.original_node.node_type == NodeType.ELEMENT_NODE
			and node.original_node.tag_name.lower() in ['table', 'tbody', 'thead']
		)

		# Detect repeated class patterns (likely product cards, search results, etc.)
		repeated_class_pattern = None
		if node.original_node.node_type == NodeType.ELEMENT_NODE:
			class_counts = {}
			for child in node.children:
				if child.original_node.node_type == NodeType.ELEMENT_NODE:
					attrs = child.original_node.attributes
					if attrs and 'class' in attrs:
						classes = str(attrs['class']).strip()
						# Only track if has meaningful classes (not empty, not single char)
						if classes and len(classes) > 3:
							class_counts[classes] = class_counts.get(classes, 0) + 1

			# If we have 8+ items with same class pattern, it's a repeated list
			for class_name, count in class_counts.items():
				if count >= 8:
					repeated_class_pattern = class_name
					break  # Use first pattern found

		# Track list items and consecutive links
		li_count = 0
		max_list_items = 5
		consecutive_link_count = 0
		max_consecutive_links = 5
		total_links_skipped = 0

		# Track table rows
		tr_count = 0
		max_table_rows = 8

		# Track repeated class pattern items
		pattern_item_count = 0
		max_pattern_items = 6

		for child in node.children:
			# If we're in a list container and this child is an li element
			if is_list_container and child.original_node.node_type == NodeType.ELEMENT_NODE:
				if child.original_node.tag_name.lower() == 'li':
					li_count += 1
					# Skip li elements after the 5th one
					if li_count > max_list_items:
						continue

			# If we're in a table container and this child is a tr element
			if is_table_container and child.original_node.node_type == NodeType.ELEMENT_NODE:
				if child.original_node.tag_name.lower() == 'tr':
					tr_count += 1
					# Skip table rows after the 8th one (show more rows than list items)
					if tr_count > max_table_rows:
						continue

			# Check if this matches a repeated class pattern
			skip_pattern_item = False
			if repeated_class_pattern and child.original_node.node_type == NodeType.ELEMENT_NODE:
				attrs = child.original_node.attributes
				if attrs and 'class' in attrs:
					child_classes = str(attrs['class']).strip()
					if child_classes == repeated_class_pattern:
						pattern_item_count += 1
						# Skip items after the 6th one in repeated pattern
						if pattern_item_count > max_pattern_items:
							skip_pattern_item = True

			if skip_pattern_item:
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
						children_output.append(f'{depth_str}... +{total_links_skipped} more')
						total_links_skipped = 0
					consecutive_link_count = 0

			child_text = DOMEvalSerializer.serialize_tree(child, include_attributes, depth)
			if child_text:
				children_output.append(child_text)

		# Add truncation message if we skipped items at the end
		if is_list_container and li_count > max_list_items:
			depth_str = depth * '\t'
			children_output.append(f'{depth_str}... +{li_count - max_list_items} more')

		# Add truncation message for table rows
		if is_table_container and tr_count > max_table_rows:
			depth_str = depth * '\t'
			children_output.append(f'{depth_str}... +{tr_count - max_table_rows} rows')

		# Add truncation message for repeated class patterns
		if repeated_class_pattern:
			pattern_total = sum(
				1 for child in node.children
				if child.original_node.node_type == NodeType.ELEMENT_NODE
				and child.original_node.attributes
				and 'class' in child.original_node.attributes
				and str(child.original_node.attributes['class']).strip() == repeated_class_pattern
			)
			if pattern_total > max_pattern_items:
				depth_str = depth * '\t'
				children_output.append(f'{depth_str}... +{pattern_total - max_pattern_items} similar (use evaluate() if you need more)')

		# Add truncation message for links if we skipped any at the end
		if total_links_skipped > 0:
			depth_str = depth * '\t'
			children_output.append(f'{depth_str}... +{total_links_skipped} more')

		return '\n'.join(children_output)

	@staticmethod
	def _build_compact_attributes(node: EnhancedDOMTreeNode) -> str:
		"""Build ultra-compact attributes string with only key attributes."""
		attrs = []
		attributes_to_include = {}

		# Add accessible name FIRST (gold semantic identifier from AX tree)
		if node.ax_node and node.ax_node.name:
			name = node.ax_node.name.strip()
			if name and len(name) > 2:
				attributes_to_include['ax-name'] = cap_text_length(name, 30)

		# Collect HTML attributes
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
						value = cap_text_length(value, 30)
					elif attr == 'href':
						# For href, cap at 30 chars to save space
						value = cap_text_length(value, 30)
					else:
						# Cap at 30 chars for other attributes
						value = cap_text_length(value, 30)

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

		# Build final string
		for key, value in attributes_to_include.items():
			attrs.append(f'{key}="{value}"')

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
		"""Get text content to display inline (max 20 chars)."""
		text_parts = []
		for child in node.children:
			if child.original_node.node_type == NodeType.TEXT_NODE:
				text = child.original_node.node_value.strip() if child.original_node.node_value else ''
				if text and len(text) > 1:
					text_parts.append(text)

		if not text_parts:
			return ''

		combined = ' '.join(text_parts)
		return cap_text_length(combined, 20)

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
