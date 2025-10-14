# @file purpose: Serializes enhanced DOM trees to clean markdown format for content extraction

import logging
import re

from browser_use.dom.views import EnhancedDOMTreeNode, NodeType

logger = logging.getLogger(__name__)


class MarkdownSerializer:
	"""Serializes enhanced DOM trees to clean markdown, capturing dynamic content.

	Key principles from python-markdownify:
	- Process elements based on their display type (block vs inline)
	- Properly handle whitespace and text normalization
	- Use dedicated handlers for each element type
	- Build output incrementally, not by extracting all text at once
	"""

	# Elements that should be completely skipped
	SKIP_ELEMENTS = {
		'script',
		'style',
		'noscript',
		'svg',
		'path',
		'meta',
		'link',
		'head',
	}

	# Block-level elements that should have line breaks
	BLOCK_ELEMENTS = {
		'div',
		'p',
		'h1',
		'h2',
		'h3',
		'h4',
		'h5',
		'h6',
		'section',
		'article',
		'header',
		'footer',
		'main',
		'nav',
		'aside',
		'blockquote',
		'pre',
		'ul',
		'ol',
		'li',
		'table',
		'tr',
		'td',
		'th',
		'form',
		'fieldset',
		'legend',
		'dl',
		'dt',
		'dd',
		'figure',
		'figcaption',
		'address',
		'hr',
		'br',
	}

	# Inline elements that should not add extra spacing
	INLINE_ELEMENTS = {'span', 'a', 'strong', 'em', 'b', 'i', 'u', 'code', 'small', 'sub', 'sup', 'mark'}

	def __init__(self, extract_links: bool = False, deduplicate_threshold: int = 3):
		self.extract_links = extract_links
		self.deduplicate_threshold = deduplicate_threshold  # How many times to allow same text before deduplicating
		self._output_lines: list[str] = []
		self._link_counter = 0
		self._links: dict[int, str] = {}
		self._text_counts: dict[str, int] = {}  # Track how many times we've seen each text
		self._current_line_parts: list[str] = []  # Buffer for building current line

	def serialize(self, root_node: EnhancedDOMTreeNode) -> str:
		"""Serialize the entire DOM tree to markdown.

		Args:
			root_node: Root node of the enhanced DOM tree

		Returns:
			Clean markdown representation of the page content
		"""
		self._output_lines = []
		self._link_counter = 0
		self._links = {}
		self._text_counts = {}  # Reset deduplication tracking
		self._current_line_parts = []  # Reset line buffer

		# Start serialization from root
		self._serialize_node(root_node, depth=0)

		# Flush any remaining line content
		self._flush_current_line()

		# Add links section if we collected any
		markdown = '\n'.join(self._output_lines)
		if self.extract_links and self._links:
			markdown += '\n\n## Links\n\n'
			for idx, url in sorted(self._links.items()):
				markdown += f'[{idx}]: {url}\n'

		return markdown.strip()

	def _normalize_whitespace(self, text: str) -> str:
		"""Normalize whitespace in text (collapse multiple spaces, trim).

		Args:
			text: Text to normalize

		Returns:
			Normalized text
		"""
		# Replace multiple whitespace with single space
		text = re.sub(r'\s+', ' ', text)
		# Strip leading/trailing whitespace
		return text.strip()

	def _add_text(self, text: str) -> None:
		"""Add text to the current line buffer.

		Args:
			text: Text to add
		"""
		if not text:
			return

		normalized = self._normalize_whitespace(text)
		if not normalized:
			return

		# Check deduplication
		if not self._should_include_text(normalized):
			return

		# Add to current line buffer
		self._current_line_parts.append(normalized)

	def _flush_current_line(self) -> None:
		"""Flush the current line buffer to output lines."""
		if not self._current_line_parts:
			return

		line = ' '.join(self._current_line_parts)
		if line:
			self._output_lines.append(line)
		self._current_line_parts = []

	def _add_line(self, text: str) -> None:
		"""Add a complete line to output (flushes current line first).

		Args:
			text: Text to add as a line
		"""
		self._flush_current_line()
		normalized = self._normalize_whitespace(text)
		if normalized and self._should_include_text(normalized):
			self._output_lines.append(normalized)

	def _add_blank_line(self) -> None:
		"""Add a blank line (for block element spacing)."""
		self._flush_current_line()
		if self._output_lines and self._output_lines[-1].strip():
			self._output_lines.append('')

	def _should_include_text(self, text: str) -> bool:
		"""Check if text should be included based on deduplication threshold.

		Args:
			text: Text to check

		Returns:
			True if text should be included, False if it exceeds threshold
		"""
		if not text or self.deduplicate_threshold <= 0:
			return True

		# Normalize text for deduplication (strip whitespace, lowercase)
		normalized = text.strip().lower()
		if not normalized:
			return True

		# Track count
		current_count = self._text_counts.get(normalized, 0)
		self._text_counts[normalized] = current_count + 1

		# Allow if under threshold
		return current_count < self.deduplicate_threshold

	def _serialize_node(self, node: EnhancedDOMTreeNode, depth: int, max_depth: int = 50) -> None:
		"""Recursively serialize a node and its children.

		Args:
			node: Current node to serialize
			depth: Current depth in the tree (for debugging)
			max_depth: Maximum depth to prevent infinite recursion
		"""
		# Safety check to prevent infinite recursion
		if depth > max_depth:
			return

		# Handle different node types
		if node.node_type == NodeType.DOCUMENT_NODE:
			# Process document's children
			for child in node.children:
				self._serialize_node(child, depth + 1, max_depth)
			return

		if node.node_type == NodeType.DOCUMENT_FRAGMENT_NODE:
			# Shadow DOM - process children directly
			for child in node.children:
				self._serialize_node(child, depth + 1, max_depth)
			return

		if node.node_type == NodeType.TEXT_NODE:
			# Add text to current line buffer (will be deduplicated and normalized)
			if node.is_visible and node.node_value:
				self._add_text(node.node_value)
			return

		if node.node_type == NodeType.ELEMENT_NODE:
			tag_name = node.tag_name.lower()

			# Skip elements that don't contribute to content
			if tag_name in self.SKIP_ELEMENTS:
				return

			# Only process visible elements (or their children might be visible)
			if not node.is_visible and not node.children:
				return

			# Handle iframe recursively - include full content
			if tag_name in ('iframe', 'frame'):
				if node.content_document:
					self._add_blank_line()
					self._add_line('---')
					self._add_line('**[Iframe Content Start]**')
					self._add_blank_line()
					self._serialize_node(node.content_document, depth + 1, max_depth)
					self._add_blank_line()
					self._add_line('**[Iframe Content End]**')
					self._add_line('---')
					self._add_blank_line()
				return

			# Handle special elements with markdown formatting
			if tag_name in ('h1', 'h2', 'h3', 'h4', 'h5', 'h6'):
				# Headings - extract text from children inline
				level = int(tag_name[1])
				self._add_blank_line()
				# Process children to build heading text
				heading_start = len(self._current_line_parts)
				for child in node.children_and_shadow_roots:
					self._serialize_node(child, depth + 1, max_depth)
				# Build heading line
				if self._current_line_parts[heading_start:]:
					heading_text = ' '.join(self._current_line_parts[heading_start:])
					self._current_line_parts = self._current_line_parts[:heading_start]
					self._add_line(f'{"#" * level} {heading_text}')
					self._add_blank_line()
				return

			if tag_name == 'a':
				# Links - process children inline
				for child in node.children_and_shadow_roots:
					self._serialize_node(child, depth + 1, max_depth)
				return

			if tag_name in ('strong', 'b', 'em', 'i', 'code'):
				# Inline formatting - just process children
				for child in node.children_and_shadow_roots:
					self._serialize_node(child, depth + 1, max_depth)
				return

			if tag_name == 'pre':
				# Code block
				text = self._get_text_content(node)
				if text:
					self._add_blank_line()
					self._add_line('```')
					self._add_line(text)
					self._add_line('```')
					self._add_blank_line()
				return

			if tag_name == 'ul' or tag_name == 'ol':
				# Lists - process each item inline
				self._add_blank_line()
				counter = 1
				for child in node.children:
					if child.tag_name.lower() == 'li':
						# Process list item children inline
						prefix = f'{counter}. ' if tag_name == 'ol' else '- '
						self._current_line_parts.append(prefix)
						for li_child in child.children_and_shadow_roots:
							self._serialize_node(li_child, depth + 2, max_depth)
						self._flush_current_line()
						counter += 1
					else:
						self._serialize_node(child, depth + 1, max_depth)
				self._add_blank_line()
				return

			if tag_name == 'table':
				# Tables
				self._serialize_table(node, depth, max_depth)
				return

			if tag_name == 'img':
				# Images
				alt_text = node.attributes.get('alt', '') if node.attributes else ''
				if alt_text:
					self._add_text(f'[Image: {alt_text}]')
				return

			if tag_name == 'hr':
				# Horizontal rule
				self._add_blank_line()
				self._add_line('---')
				self._add_blank_line()
				return

			if tag_name == 'br':
				# Line break - flush current line
				self._flush_current_line()
				return

			# Input elements
			if tag_name == 'input':
				input_type = node.attributes.get('type', 'text') if node.attributes else 'text'
				value = node.attributes.get('value', '') if node.attributes else ''
				placeholder = node.attributes.get('placeholder', '') if node.attributes else ''

				if input_type in ('text', 'email', 'password', 'search', 'tel', 'url', 'number'):
					label = placeholder or value or f'{input_type} input'
					self._add_text(f'[{label}]')
				elif input_type in ('checkbox', 'radio'):
					checked = 'checked' in node.attributes if node.attributes else False
					state = '[x]' if checked else '[ ]'
					label = node.attributes.get('aria-label', value or input_type) if node.attributes else input_type
					self._add_text(f'{state} {label}')
				elif input_type in ('button', 'submit'):
					label = value or 'button'
					self._add_text(f'[{label}]')
				return

			# Textarea
			if tag_name == 'textarea':
				value = node.attributes.get('value', '') if node.attributes else ''
				placeholder = node.attributes.get('placeholder', '') if node.attributes else ''
				label = placeholder or value or 'text area'
				self._add_text(f'[{label}]')
				return

			# Select dropdowns - LIMIT options to avoid repetition
			if tag_name == 'select':
				# Skip select elements entirely - they cause too much noise
				# Most modern sites use custom dropdowns anyway
				return

			# Button
			if tag_name == 'button':
				# Extract text from button and wrap in brackets
				text = self._get_text_content(node)
				if text:
					self._add_text(f'[{text}]')
				return

			# Label
			if tag_name == 'label':
				# Process label children inline
				for child in node.children_and_shadow_roots:
					self._serialize_node(child, depth + 1, max_depth)
				self._add_text(':')
				return

			# Block elements - add spacing and process children
			if tag_name in self.BLOCK_ELEMENTS:
				self._add_blank_line()
				# Process children
				for child in node.children_and_shadow_roots:
					self._serialize_node(child, depth + 1, max_depth)
				self._add_blank_line()
				return

			# For all other elements (including inline), just process children
			for child in node.children_and_shadow_roots:
				self._serialize_node(child, depth + 1, max_depth)

	def _get_text_content(self, node: EnhancedDOMTreeNode, max_depth: int = 10) -> str:
		"""Extract all text content from a node and its descendants (for special cases like tables, code blocks).

		Args:
			node: Node to extract text from
			max_depth: Maximum depth to traverse

		Returns:
			Concatenated text content
		"""
		if max_depth <= 0:
			return ''

		parts = []

		if node.node_type == NodeType.TEXT_NODE:
			if node.is_visible and node.node_value:
				text = node.node_value.strip()
				if text:
					parts.append(text)

		elif node.node_type == NodeType.ELEMENT_NODE:
			# Skip non-content elements
			if node.tag_name.lower() in self.SKIP_ELEMENTS:
				return ''

			# Get text from children (recursively)
			for child in node.children_and_shadow_roots:
				child_text = self._get_text_content(child, max_depth - 1)
				if child_text:
					parts.append(child_text)

		elif node.node_type == NodeType.DOCUMENT_FRAGMENT_NODE:
			# Handle shadow DOM fragments
			for child in node.children:
				child_text = self._get_text_content(child, max_depth - 1)
				if child_text:
					parts.append(child_text)

		return self._normalize_whitespace(' '.join(parts))

	def _serialize_table(self, table_node: EnhancedDOMTreeNode, depth: int, max_depth: int) -> None:
		"""Serialize a table to markdown format.

		Args:
			table_node: Table element node
			depth: Current depth
			max_depth: Maximum depth
		"""
		self._add_blank_line()

		# Extract table structure
		rows: list[list[str]] = []
		header_row: list[str] | None = None

		# Find thead and tbody
		for child in table_node.children:
			if child.tag_name.lower() == 'thead':
				# Process header rows
				for tr in child.children:
					if tr.tag_name.lower() == 'tr':
						header_cells = []
						for cell in tr.children:
							if cell.tag_name.lower() in ('th', 'td'):
								text = self._get_text_content(cell)
								header_cells.append(text or '')
						if header_cells:
							header_row = header_cells
							break

			elif child.tag_name.lower() == 'tbody':
				# Process body rows
				for tr in child.children:
					if tr.tag_name.lower() == 'tr':
						row_cells = []
						for cell in tr.children:
							if cell.tag_name.lower() in ('th', 'td'):
								text = self._get_text_content(cell)
								row_cells.append(text or '')
						if row_cells:
							rows.append(row_cells)

			elif child.tag_name.lower() == 'tr':
				# Direct tr children (no thead/tbody)
				row_cells = []
				is_header = False
				for cell in child.children:
					if cell.tag_name.lower() == 'th':
						is_header = True
						text = self._get_text_content(cell)
						row_cells.append(text or '')
					elif cell.tag_name.lower() == 'td':
						text = self._get_text_content(cell)
						row_cells.append(text or '')

				if row_cells:
					if is_header and header_row is None:
						header_row = row_cells
					else:
						rows.append(row_cells)

		# Render table
		if header_row:
			# Render header
			self._add_line('| ' + ' | '.join(header_row) + ' |')
			self._add_line('| ' + ' | '.join(['---'] * len(header_row)) + ' |')

			# Render rows
			for row in rows:
				# Pad row to match header length
				while len(row) < len(header_row):
					row.append('')
				self._add_line('| ' + ' | '.join(row[: len(header_row)]) + ' |')
		elif rows:
			# No header, just render rows
			max_cols = max(len(row) for row in rows)
			for row in rows:
				# Pad row to match max length
				while len(row) < max_cols:
					row.append('')
				self._add_line('| ' + ' | '.join(row) + ' |')

		self._add_blank_line()
