"""
Code processing utilities for fixing JavaScript evaluation issues in LLM-generated code.
"""

import re


class CodeProcessor:
	"""Simple code processor focused on JavaScript evaluation fixes"""

	@staticmethod
	def fix_js_code_for_evaluate(js_code: str) -> str:
		"""Fix JavaScript code for target.evaluate() - preserve regex patterns"""

		# Step 1: Extract and protect JavaScript regex patterns
		regex_patterns = []
		regex_placeholder = '___REGEX_PATTERN_{}_PLACEHOLDER___'

		# Find regex patterns: /pattern/flags and preserve them
		regex_matches = list(re.finditer(r'/([^/\n\\]|\\.)*/[gimuy]*', js_code))
		for i, match in enumerate(regex_matches):
			pattern_text = match.group(0)
			placeholder = regex_placeholder.format(i)
			regex_patterns.append(pattern_text)
			js_code = js_code.replace(pattern_text, placeholder, 1)

		# Step 2: Fix problematic escaping (now safe since regex is protected)
		js_code = re.sub(r'\\{3,}', r'\\', js_code)  # Reduce excessive backslashes
		js_code = re.sub(r'\\x3d', '=', js_code)  # Fix hex encoding first
		js_code = re.sub(r'\\x22', '"', js_code)  # Fix hex encoding first
		js_code = re.sub(r'\\x27', "'", js_code)  # Fix hex encoding first
		js_code = js_code.replace('\\"', '"').replace("\\'", "'")  # Fix quote escaping
		js_code = re.sub(r'\\n', ' ', js_code)  # Remove \n
		js_code = re.sub(r'\\t', ' ', js_code)  # Remove \t
		js_code = re.sub(r'\\r', ' ', js_code)  # Remove \r

		# Step 3: Fix CSS selectors in JavaScript (querySelector calls)
		pattern = r'(querySelector(?:All)?\s*\(\s*[\'"])([^\'\"]+)([\'\"]\s*\))'

		def fix_selector(match):
			prefix, selector, suffix = match.groups()
			if not CodeProcessor.validate_css_selector(selector):
				selector = CodeProcessor.fix_css_selector(selector)
			return f'{prefix}{selector}{suffix}'

		js_code = re.sub(pattern, fix_selector, js_code)

		# Step 4: Restore protected regex patterns
		for i, pattern in enumerate(regex_patterns):
			placeholder = regex_placeholder.format(i)
			js_code = js_code.replace(placeholder, pattern)

		# Step 5: Ensure arrow function format
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
