"""
Code processing utilities for fixing JavaScript evaluation issues in LLM-generated code.
"""

import json
import re
import unicodedata


class CodeProcessor:
	"""Simple code processor focused on JavaScript evaluation fixes"""

	# Zero-width characters that can cause parsing issues
	ZERO_WIDTH = ''.join(chr(c) for c in [0x200B, 0x200C, 0x200D, 0xFEFF])

	@staticmethod
	def _normalize(s: str) -> str:
		"""Normalize string to remove problematic Unicode characters"""
		s = unicodedata.normalize('NFKC', s)
		return (
			s.replace('"', '"')
			.replace('"', '"')
			.replace(""", "'").replace(""", "'")
			.replace('\u00a0', ' ')
			.replace(CodeProcessor.ZERO_WIDTH, '')
		)

	@staticmethod
	def patch_js_source(js_src: str) -> str:
		"""Apply targeted fixes for common JavaScript evaluation issues"""
		s = CodeProcessor._normalize(js_src)

		# A) Replace invalid CSS :contains(...)
		s = s.replace(':contains(', '/*:contains(*/(')

		# B) Dangerous URL segments inside regex literals → split into regex + includes
		#    e.g. /5g|/phones/|/topic/5g/.test(href)
		s = re.sub(
			r'/([^/]+)\|/([a-zA-Z0-9_\-\/\.]+)/(?:([gimuy]*))\.test\(([^)]+)\)',
			r"( ((String(\4)).match(new RegExp(\1,'\3'))) || (String(\4)).includes('/\2') )",
			s,
		)
		s = re.sub(
			r'/([a-zA-Z0-9_\-\|\.\?\+\*\(\)\[\]\{\}\\\\]+)\|/([a-zA-Z0-9_\-\/\.]+)/(?:([gimuy]*))\.test\(([^)]+)\)',
			r"( ((String(\4)).match(new RegExp('\1','\3'))) || (String(\4)).includes('/\2') )",
			s,
		)

		# C) Lost backslashes inside regex literals (/\n/, /\s/, /\w/, /\d/, /\./)
		def _fix_backslashes(m):
			body, flags = m.group(1), (m.group(2) or '')
			body = (
				body.replace('\\n', '\\\\n')
				.replace('\\r', '\\\\r')
				.replace('\\s', '\\\\s')
				.replace('\\w', '\\\\w')
				.replace('\\d', '\\\\d')
				.replace('\\.', '\\\\.')
			)
			return f'/{body}/{flags}'

		s = re.sub(r'/([^/\n]+)/([gimuy]*)', _fix_backslashes, s)

		return s

	@staticmethod
	def create_json_safe_wrapper(js_src: str) -> str:
		"""Create a JSON-safe wrapper for JavaScript evaluation"""
		js_src = CodeProcessor.patch_js_source(js_src)
		code_json = json.dumps(js_src)  # All quotes/backslashes escaped safely

		wrapper = (
			'() => {'
			f'  const __src = {code_json};'
			'  try {'
			'    const __fn = (0,eval)(__src);'
			"    if (typeof __fn === 'function') {"
			'      const out = __fn();'
			"      return (typeof out === 'string' || out == null) ? out : JSON.stringify(out);"
			'    }'
			"    return (typeof __fn === 'string' || __fn == null) ? __fn : JSON.stringify(__fn);"
			'  } catch (e) {'
			'    return JSON.stringify({__error: String(e && e.message || e)});'
			'  }'
			'}'
		)
		return wrapper

	@staticmethod
	def fix_js_code_for_evaluate(js_code: str) -> str:
		"""Fix JavaScript code for target.evaluate() using JSON-safe wrapper"""
		return CodeProcessor.create_json_safe_wrapper(js_code)

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
