# @file purpose: Serializes enhanced DOM trees to clean markdown format for content extraction

import logging

from browser_use.dom.views import EnhancedDOMTreeNode, NodeType

logger = logging.getLogger(__name__)


class MarkdownSerializer:
	"""Serializes enhanced DOM trees to clean markdown, capturing dynamic content."""

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

	def __init__(self, extract_links: bool = False):
		self.extract_links = extract_links
		self._output_lines: list[str] = []
		self._link_counter = 0
		self._links: dict[int, str] = {}

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

		# Start serialization from root
		self._serialize_node(root_node, depth=0)

		# Add links section if we collected any
		markdown = '\n'.join(self._output_lines)
		if self.extract_links and self._links:
			markdown += '\n\n## Links\n\n'
			for idx, url in sorted(self._links.items()):
				markdown += f'[{idx}]: {url}\n'

		return markdown.strip()

	def _serialize_node(self, node: EnhancedDOMTreeNode, depth: int) -> None:
		"""Recursively serialize a node and its children.

		Args:
			node: Current node to serialize
			depth: Current depth in the tree (for debugging)
		"""

		# Handle different node types
		if node.node_type == NodeType.DOCUMENT_NODE:
			# Process document's children
			for child in node.children:
				self._serialize_node(child, depth)
			return

		if node.node_type == NodeType.DOCUMENT_FRAGMENT_NODE:
			# Shadow DOM - process children directly
			for child in node.children:
				self._serialize_node(child, depth)
			return

		if node.node_type == NodeType.TEXT_NODE:
			# Only include visible text
			if node.is_visible and node.node_value:
				text = node.node_value.strip()
				if text and len(text) > 1:
					self._output_lines.append(text)
			return

		if node.node_type == NodeType.ELEMENT_NODE:
			tag_name = node.tag_name.lower()

			# Skip elements that don't contribute to content
			if tag_name in self.SKIP_ELEMENTS:
				return

			# Handle iframe recursively
			if tag_name in ('iframe', 'frame'):
				if node.content_document:
					self._output_lines.append('\n[iframe content]:')
					self._serialize_node(node.content_document, depth + 1)
					self._output_lines.append('[end iframe]\n')
				return

			# Only process visible elements (or their children might be visible)
			if not node.is_visible and not node.children:
				return

			# Handle special elements with markdown formatting
			if tag_name in ('h1', 'h2', 'h3', 'h4', 'h5', 'h6'):
				# Headings
				level = int(tag_name[1])
				text = self._get_text_content(node)
				if text:
					self._output_lines.append('')
					self._output_lines.append(f'{"#" * level} {text}')
					self._output_lines.append('')
				return

			if tag_name == 'a':
				# Links
				text = self._get_text_content(node)
				if text:
					if self.extract_links and node.attributes and 'href' in node.attributes:
						href = node.attributes['href']
						self._link_counter += 1
						self._links[self._link_counter] = href
						self._output_lines.append(f'[{text}][{self._link_counter}]')
					else:
						self._output_lines.append(text)
				return

			if tag_name in ('strong', 'b'):
				# Bold
				text = self._get_text_content(node)
				if text:
					self._output_lines.append(f'**{text}**')
				return

			if tag_name in ('em', 'i'):
				# Italic
				text = self._get_text_content(node)
				if text:
					self._output_lines.append(f'*{text}*')
				return

			if tag_name == 'code':
				# Inline code
				text = self._get_text_content(node)
				if text:
					self._output_lines.append(f'`{text}`')
				return

			if tag_name == 'pre':
				# Code block
				text = self._get_text_content(node)
				if text:
					self._output_lines.append('')
					self._output_lines.append('```')
					self._output_lines.append(text)
					self._output_lines.append('```')
					self._output_lines.append('')
				return

			if tag_name == 'blockquote':
				# Blockquote
				self._output_lines.append('')
				for child in node.children:
					# Process children, then prefix with >
					child_start_idx = len(self._output_lines)
					self._serialize_node(child, depth + 1)
					# Prefix all lines added by children with >
					for i in range(child_start_idx, len(self._output_lines)):
						if self._output_lines[i]:
							self._output_lines[i] = f'> {self._output_lines[i]}'
				self._output_lines.append('')
				return

			if tag_name == 'ul' or tag_name == 'ol':
				# Lists
				self._output_lines.append('')
				counter = 1
				for child in node.children:
					if child.tag_name.lower() == 'li':
						prefix = f'{counter}. ' if tag_name == 'ol' else '- '
						text = self._get_text_content(child)
						if text:
							self._output_lines.append(f'{prefix}{text}')
							counter += 1
					else:
						self._serialize_node(child, depth + 1)
				self._output_lines.append('')
				return

			if tag_name == 'table':
				# Tables
				self._serialize_table(node)
				return

			if tag_name == 'img':
				# Images
				alt_text = node.attributes.get('alt', 'image') if node.attributes else 'image'
				self._output_lines.append(f'![{alt_text}]')
				return

			if tag_name == 'hr':
				# Horizontal rule
				self._output_lines.append('')
				self._output_lines.append('---')
				self._output_lines.append('')
				return

			if tag_name == 'br':
				# Line break
				self._output_lines.append('')
				return

			# Input elements - include their value
			if tag_name == 'input':
				input_type = node.attributes.get('type', 'text') if node.attributes else 'text'
				value = node.attributes.get('value', '') if node.attributes else ''
				placeholder = node.attributes.get('placeholder', '') if node.attributes else ''

				if input_type in ('text', 'email', 'password', 'search', 'tel', 'url', 'number'):
					label = placeholder or value or f'{input_type} input'
					self._output_lines.append(f'[{label}]')
				elif input_type in ('checkbox', 'radio'):
					checked = 'checked' in node.attributes if node.attributes else False
					state = '[x]' if checked else '[ ]'
					label = node.attributes.get('aria-label', value or input_type) if node.attributes else input_type
					self._output_lines.append(f'{state} {label}')
				elif input_type == 'button' or input_type == 'submit':
					label = value or 'button'
					self._output_lines.append(f'[{label}]')
				return

			# Textarea - include value
			if tag_name == 'textarea':
				value = node.attributes.get('value', '') if node.attributes else ''
				placeholder = node.attributes.get('placeholder', '') if node.attributes else ''
				label = placeholder or value or 'text area'
				self._output_lines.append(f'[{label}]')
				return

			# Select - show selected option
			if tag_name == 'select':
				selected_text = ''
				for child in node.children:
					if child.tag_name.lower() == 'option':
						if child.attributes and 'selected' in child.attributes:
							selected_text = self._get_text_content(child)
							break
				if not selected_text:
					# Get first option if no selection
					for child in node.children:
						if child.tag_name.lower() == 'option':
							selected_text = self._get_text_content(child)
							break

				label = selected_text or 'dropdown'
				self._output_lines.append(f'[{label} ▼]')
				return

			# Button
			if tag_name == 'button':
				text = self._get_text_content(node)
				if text:
					self._output_lines.append(f'[{text}]')
				return

			# Label
			if tag_name == 'label':
				text = self._get_text_content(node)
				if text:
					self._output_lines.append(f'{text}:')
				return

			# Block elements - add spacing before and after
			if tag_name in self.BLOCK_ELEMENTS:
				# Add blank line before block element if needed
				if self._output_lines and self._output_lines[-1].strip():
					self._output_lines.append('')

				# Process children
				for child in node.children:
					self._serialize_node(child, depth + 1)

				# Add blank line after block element if needed
				if self._output_lines and self._output_lines[-1].strip():
					self._output_lines.append('')
				return

			# For all other elements (including inline), just process children
			for child in node.children_and_shadow_roots:
				self._serialize_node(child, depth + 1)

	def _get_text_content(self, node: EnhancedDOMTreeNode, max_depth: int = 10) -> str:
		"""Extract all text content from a node and its descendants.

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
			if node.node_value:
				text = node.node_value.strip()
				if text:
					parts.append(text)

		elif node.node_type == NodeType.ELEMENT_NODE:
			# Skip non-content elements
			if node.tag_name.lower() in self.SKIP_ELEMENTS:
				return ''

			# Get text from children
			for child in node.children_and_shadow_roots:
				child_text = self._get_text_content(child, max_depth - 1)
				if child_text:
					parts.append(child_text)

		return ' '.join(parts)

	def _serialize_table(self, table_node: EnhancedDOMTreeNode) -> None:
		"""Serialize a table to markdown format.

		Args:
			table_node: Table element node
		"""
		self._output_lines.append('')

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
			self._output_lines.append('| ' + ' | '.join(header_row) + ' |')
			self._output_lines.append('| ' + ' | '.join(['---'] * len(header_row)) + ' |')

			# Render rows
			for row in rows:
				# Pad row to match header length
				while len(row) < len(header_row):
					row.append('')
				self._output_lines.append('| ' + ' | '.join(row[: len(header_row)]) + ' |')
		elif rows:
			# No header, just render rows
			max_cols = max(len(row) for row in rows)
			for row in rows:
				# Pad row to match max length
				while len(row) < max_cols:
					row.append('')
				self._output_lines.append('| ' + ' | '.join(row) + ' |')

		self._output_lines.append('')
