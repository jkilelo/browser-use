"""Simple HTML prettifier utility."""

import re


class HTMLPrettifier:
	"""A simple HTML prettifier that adds proper indentation and formatting."""

	def __init__(self, indent_size: int = 2):
		self.indent_size = indent_size
		self.self_closing_tags = {
			'area',
			'base',
			'br',
			'col',
			'embed',
			'hr',
			'img',
			'input',
			'link',
			'meta',
			'source',
			'track',
			'wbr',
		}

	def prettify(self, html: str) -> str:
		"""
		Prettify HTML string with proper indentation.

		Args:
		    html: Raw HTML string to prettify

		Returns:
		    Formatted HTML string with proper indentation
		"""
		if not html or not html.strip():
			return html

		# Remove extra whitespace and normalize
		html = self._normalize_html(html)

		# Split into tokens
		tokens = self._tokenize(html)

		# Format with indentation
		return self._format_tokens(tokens)

	def _normalize_html(self, html: str) -> str:
		"""Normalize HTML by removing extra whitespace."""
		# Remove extra whitespace between tags
		html = re.sub(r'>\s+<', '><', html)
		# Remove leading/trailing whitespace
		html = html.strip()
		return html

	def _tokenize(self, html: str) -> list[str]:
		"""Split HTML into tokens (tags and text)."""
		# Pattern to match tags and text content
		pattern = r'(<[^>]*>|[^<]+)'
		tokens = re.findall(pattern, html)

		# Filter out empty tokens
		return [token.strip() for token in tokens if token.strip()]

	def _format_tokens(self, tokens: list[str]) -> str:
		"""Format tokens with proper indentation."""
		result = []
		indent_level = 0
		i = 0

		while i < len(tokens):
			token = tokens[i]

			if self._is_opening_tag(token):
				# Add indentation before opening tag
				result.append(' ' * (indent_level * self.indent_size) + token)

				# Check if next token is text and token after that is closing tag
				if i + 2 < len(tokens) and self._is_text_content(tokens[i + 1]) and self._is_closing_tag(tokens[i + 2]):
					# Inline content: <tag>text</tag>
					result[-1] += tokens[i + 1] + tokens[i + 2]
					i += 3  # Skip text and closing tag
					continue

				# Increase indent level if not self-closing
				tag_name = self._extract_tag_name(token)
				if tag_name and tag_name.lower() not in self.self_closing_tags:
					indent_level += 1

			elif self._is_closing_tag(token):
				# Decrease indent level before closing tag
				indent_level = max(0, indent_level - 1)
				result.append(' ' * (indent_level * self.indent_size) + token)

			elif self._is_text_content(token):
				# Block text content
				result.append(' ' * (indent_level * self.indent_size) + token)
			else:
				# Other content (comments, etc.)
				result.append(' ' * (indent_level * self.indent_size) + token)

			i += 1

		return '\n'.join(result)

	def _is_opening_tag(self, token: str) -> bool:
		"""Check if token is an opening tag."""
		return token.startswith('<') and not token.startswith('</') and not token.startswith('<!--') and token.endswith('>')

	def _is_closing_tag(self, token: str) -> bool:
		"""Check if token is a closing tag."""
		return token.startswith('</')

	def _is_text_content(self, token: str) -> bool:
		"""Check if token is text content."""
		return not token.startswith('<')

	def _extract_tag_name(self, tag: str) -> str:
		"""Extract tag name from opening tag."""
		if not tag.startswith('<'):
			return ''

		# Remove < and >
		content = tag[1:-1]

		# Get first word (tag name)
		parts = content.split()
		if parts:
			return parts[0].lower()

		return ''


def prettify_html(html: str, indent_size: int = 2) -> str:
	"""
	Convenience function to prettify HTML.

	Args:
	    html: Raw HTML string to prettify
	    indent_size: Number of spaces for each indentation level

	Returns:
	    Formatted HTML string with proper indentation
	"""
	prettifier = HTMLPrettifier(indent_size=indent_size)
	return prettifier.prettify(html)


# Example usage
if __name__ == '__main__':
	# Test with simple example
	sample_html = """<div bid123><p>Hello</p><div bid456><span>World</span></div></div>"""

	print('Original:')
	print(sample_html)
	print('\nPrettified:')
	print(prettify_html(sample_html))

	print('\n' + '=' * 50 + '\n')

	# Test with more complex example
	complex_html = """<html><head><title>Test</title></head><body><div bid123 class="container"><h1>Title</h1><p>Some text here</p><ul><li>Item 1</li><li>Item 2</li></ul><div bid456><input bid789 type="text" placeholder="Enter text"><button bid101112>Submit</button></div></div></body></html>"""

	print('Complex Original:')
	print(complex_html)
	print('\nComplex Prettified:')
	print(prettify_html(complex_html))
