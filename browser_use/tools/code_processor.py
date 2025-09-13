"""
Code processing utilities for fixing JavaScript evaluation issues in LLM-generated code.
"""

import base64
import re
import unicodedata


def normalize_text(s: str) -> str:
	"""Fix smart quotes, zero-width characters, and invisible chars that trigger SyntaxError."""
	# Replace smart quotes with ASCII quotes BEFORE normalization
	s = s.replace('\u201c', '"').replace('\u201d', '"')  # Left and right double quotation mark
	s = s.replace('\u2018', "'").replace('\u2019', "'")  # Left and right single quotation mark
	s = s.replace('"', '"').replace('"', '"').replace(""", "'").replace(""", "'")

	s = unicodedata.normalize('NFKC', s)

	# Replace non-breaking spaces and zero-width chars
	s = s.replace('\u00a0', ' ')
	zero_width_chars = ''.join(chr(c) for c in [0x200B, 0x200C, 0x200D, 0xFEFF])
	for zwc in zero_width_chars:
		s = s.replace(zwc, '')

	return s


def wrap_js_base64(js_src: str) -> str:
	"""
	Wrap JavaScript source in a Base64 trampoline to avoid quote/backtick issues.

	This approach:
	1. Encodes the JS as Base64 to avoid any quote/escape problems
	2. Creates a simple wrapper that decodes and executes it
	3. Catches errors and returns them as JSON instead of throwing
	"""
	js_src = normalize_text(js_src)
	b64 = base64.b64encode(js_src.encode('utf-8')).decode('ascii')

	# Stable wrapper using only ASCII chars - no regex literals, no backticks
	return (
		'() => {'
		f"  const __b64 = '{b64}';"
		'  const __src = atob(__b64);'
		'  try {'
		'    const __fn = (0,eval)(__src);'
		"    if (typeof __fn === 'function') {"
		'      const out = __fn();'
		"      return (typeof out === 'string' || out === null) ? out : JSON.stringify(out);"
		'    } else {'
		"      return (typeof __fn === 'string' || __fn === null) ? __fn : JSON.stringify(__fn);"
		'    }'
		'  } catch (e) {'
		'    return JSON.stringify({__error: String(e && e.message || e)});'
		'  }'
		'}'
	)


def patch_js_source(js_src: str) -> str:
	"""
	Auto-patch common JavaScript landmines before execution.

	Fixes:
	1. Invalid CSS :contains(...) selector usage
	2. URL substrings in regex literals causing "invalid flags"/"missing /"
	3. Lost backslashes in regex patterns (\\n -> n, \\s -> s, etc.)
	"""
	s = normalize_text(js_src)

	# A) Replace invalid CSS :contains(...) usage
	# querySelector doesn't support :contains, comment it out to avoid DOMException
	s = s.replace(':contains(', '/*:contains(*/')

	# B) Fix URL substrings mistakenly placed inside regex literals
	# Pattern: /anything|/path/anything/flags.test(x) becomes safer mixed approach
	# This catches patterns where URL paths appear inside regex literals
	def fix_url_regex(match):
		full_pattern = match.group(0)
		if '/phones/' in full_pattern or '/topic/' in full_pattern or '/game' in full_pattern:
			# Replace with safer alternative that uses includes() for URL parts
			return full_pattern.replace('/.test(', '.test.replaced.by.includes(')
		return full_pattern

	# Look for regex patterns that contain URL-like segments
	s = re.sub(r'/[^/]*\|/[^/]*/', fix_url_regex, s)

	# C) Fix common backslash collapses in regex literals
	# When Python strings lose escapes: /\n/ becomes /n/, /\s/ becomes /s/
	def fix_backslashes(m):
		body, flags = m.group(1), m.group(2)
		# Re-escape common regex metacharacters
		body = body.replace('\\n', '\\\\n').replace('\\r', '\\\\r')
		body = body.replace('\\s', '\\\\s').replace('\\d', '\\\\d')
		body = body.replace('\\w', '\\\\w').replace('\\.', '\\\\.')
		return f'/{body}/{flags}'

	s = re.sub(r'/([^/\n]+)/([gimuy]*)', fix_backslashes, s)

	return s


def patch_python_source(py_src: str) -> str:
	"""
	Fix common Python source issues in agent-generated code.

	Fixes:
	1. JavaScript-style "!" negation in Python (should be "not")
	2. Normalize text encoding issues
	"""
	s = normalize_text(py_src)

	# Fix JS-style "!" negation in Python conditions, but don't touch "!="
	s = re.sub(r'(?<![=!])!(?!=)', ' not ', s)

	return s


class CodeProcessor:
	"""Simple code processor focused on JavaScript evaluation fixes"""

	@staticmethod
	def fix_js_code_for_evaluate(js_code: str) -> str:
		"""Fix JavaScript code for target.evaluate() - minimal processing"""

		# Ensure arrow function format only
		if '=>' in js_code and not js_code.strip().startswith('('):
			if not js_code.strip().startswith('() =>'):
				js_code = f'() => {js_code.strip()}'
				js_code.replace('\\', '\\\\')  # double escape, because we will load the code again

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
		"""Fix common Python code issues found in LLM-generated code"""
		return patch_python_source(code)


# Backward compatibility
def fix_python_code_string_issues(code: str) -> str:
	"""Backward compatibility wrapper"""
	return CodeProcessor.fix_python_code_string_issues(code)
