"""
Code processing utilities for fixing JavaScript evaluation issues in LLM-generated code.
"""

import re


class CodeProcessor:
	"""Simple code processor focused on JavaScript evaluation fixes"""

	@staticmethod
	def fix_js_code_for_evaluate(js_code: str) -> str:
		"""Fix JavaScript code for target.evaluate() - minimal processing for variable pattern"""

		# When using variable pattern (js_code = """..."""), minimal escaping fixes needed
		# Only fix extreme over-escaping that LLMs sometimes still generate

		# Fix hex encoding issues first
		js_code = re.sub(r'\\x3d', '=', js_code)
		js_code = re.sub(r'\\x22', '"', js_code)
		js_code = re.sub(r'\\x27', "'", js_code)

		# ONLY fix extreme over-escaping in CSS selectors (4+ backslashes in a row)
		# This preserves regex patterns and normal CSS selectors
		def fix_extreme_escaping(match):
			full_match = match.group(0)
			inside = match.group(1)
			# Only fix if there are 4+ consecutive backslashes (extreme over-escaping)
			if '\\\\\\\\' in inside:
				# Remove excessive backslashes but preserve single/double backslashes for regex
				fixed_inside = re.sub(r'\\{4,}', r'\\\\', inside)
				return f'[{fixed_inside}]'
			# Leave everything else unchanged
			return full_match

		js_code = re.sub(r'\[([^]]+)\]', fix_extreme_escaping, js_code)

		# Ensure arrow function format
		if '=>' in js_code and not js_code.strip().startswith('('):
			if not js_code.strip().startswith('() =>'):
				js_code = f'() => {js_code.strip()}'

		return js_code

	@staticmethod
	def validate_css_selector(selector: str) -> bool:
		"""Simple CSS selector validation"""
		try:
			# Basic validation - check for balanced quotes and brackets
			if selector.count('"') % 2 != 0 or selector.count("'") % 2 != 0:
				return False
			if selector.count('[') != selector.count(']'):
				return False
			# Check for hex encoding or excessive escaping
			if re.search(r'\\x[0-9a-fA-F]{2}|\\{3,}', selector):
				return False
			return True
		except Exception:
			return False

	@staticmethod
	def fix_css_selector(selector: str) -> str:
		"""Fix common CSS selector issues"""
		# Remove excessive escaping and fix hex encoding
		selector = re.sub(r'\\{2,}', '', selector)
		selector = re.sub(r'\\x3d', '=', selector)
		selector = re.sub(r'\\x22', '"', selector)
		selector = re.sub(r'\\x27', "'", selector)
		selector = selector.replace('\\"', '"').replace("\\'", "'")
		return selector

	@staticmethod
	def _preserve_js_strings_in_target_evaluate(code: str) -> str:
		"""Private method for test compatibility - just calls fix_python_code_string_issues"""
		return CodeProcessor.fix_python_code_string_issues(code)

	@staticmethod
	def fix_browser_actor_code_issues(code: str) -> str:
		"""Fix code issues for browser actor execution - just calls fix_python_code_string_issues"""
		return CodeProcessor.fix_python_code_string_issues(code)

	@staticmethod
	def fix_python_code_string_issues(code: str) -> str:
		"""Basic Python string fixes - handle target.evaluate() specially"""

		# If contains target.evaluate, just fix the JS inside it
		if 'target.evaluate(' in code:
			pattern = r"(target\.evaluate\s*\(\s*['\"])(.*?)(['\"](?:\s*,.*?)?\s*\))"

			def fix_js_string(match):
				prefix = match.group(1)
				js_code = match.group(2)
				suffix = match.group(3)
				fixed_js = CodeProcessor.fix_js_code_for_evaluate(js_code)
				return f'{prefix}{fixed_js}{suffix}'

			return re.sub(pattern, fix_js_string, code, flags=re.DOTALL)

		# For regular Python code, just return as-is
		return code


# Backward compatibility
def fix_python_code_string_issues(code: str) -> str:
	"""Backward compatibility wrapper"""
	return CodeProcessor.fix_python_code_string_issues(code)
