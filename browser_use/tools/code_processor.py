"""
Code processing utilities for fixing JavaScript evaluation issues in LLM-generated code.
"""


class CodeProcessor:
	"""Simple code processor focused on JavaScript evaluation fixes"""

	@staticmethod
	def fix_js_code_for_evaluate(js_code: str) -> str:
		"""Fix JavaScript code for target.evaluate() - minimal processing"""

		# Ensure arrow function format only
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
			return True
		except Exception:
			return False

	@staticmethod
	def fix_css_selector(selector: str) -> str:
		"""Fix common CSS selector issues"""
		# No processing - return as-is
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
		"""Basic Python string fixes - no processing"""
		# No processing - return as-is
		return code


# Backward compatibility
def fix_python_code_string_issues(code: str) -> str:
	"""Backward compatibility wrapper"""
	return CodeProcessor.fix_python_code_string_issues(code)
