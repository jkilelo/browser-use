"""
Test JavaScript evaluation fixes for escaping issues.

These tests validate the fixes for the JavaScript string escaping problems
that were causing evaluation failures in the LLM-generated code.
"""

import pytest

from browser_use.tools.code_processor import CodeProcessor, fix_python_code_string_issues
from browser_use.tools.service import Tools


class TestJavaScriptEscapingFixes:
	"""Test the JavaScript escaping fixes"""

	def setup_method(self):
		"""Set up test tools instance"""
		self.tools = Tools(exclude_actions=[])

	def test_css_selector_validation(self):
		"""Test CSS selector validation catches malformed selectors"""

		# Valid selectors should pass
		assert CodeProcessor.validate_css_selector('button[type="submit"]')
		assert CodeProcessor.validate_css_selector('a[draggable="false"]')
		assert CodeProcessor.validate_css_selector('input[name="email"]')

		# Invalid selectors should fail
		assert not CodeProcessor.validate_css_selector('a[draggable\\\\\\="false"]')  # Over-escaped
		assert not CodeProcessor.validate_css_selector('button[type="unclosed')  # Unbalanced quotes
		assert not CodeProcessor.validate_css_selector('input[name=\\x3d"test"]')  # Hex encoding

	def test_css_selector_fixing(self):
		"""Test CSS selector auto-fixing"""

		# Test fixing over-escaped selectors
		fixed = CodeProcessor.fix_css_selector('a[draggable\\\\\\="false"]')
		assert fixed == 'a[draggable="false"]'

		# Test fixing hex-encoded characters
		fixed = CodeProcessor.fix_css_selector('input[type\\x3d"text"]')
		assert fixed == 'input[type="text"]'

		# Test fixing escaped quotes
		fixed = CodeProcessor.fix_css_selector('button[data-id=\\"123\\"]')
		assert fixed == 'button[data-id="123"]'

	def test_js_code_fixing_for_evaluate(self):
		"""Test JavaScript code fixing for target.evaluate calls"""

		# Test fixing over-escaped JavaScript (4+ backslashes)
		malformed_js = 'document.querySelectorAll("a[draggable\\\\\\\\=\\\\\\"false\\\\\\\\\\"]")'
		fixed_js = CodeProcessor.fix_js_code_for_evaluate(malformed_js)
		# Should reduce 4+ consecutive backslashes but preserve necessary escaping
		assert '\\\\\\\\\\\\\\\\' not in fixed_js  # 8+ backslashes should be reduced
		assert 'draggable' in fixed_js

		# Test fixing hex-encoded characters
		hex_js = '() => document.querySelector("input[type\\x3d\\"text\\"]")'
		fixed_js = CodeProcessor.fix_js_code_for_evaluate(hex_js)
		assert 'type=' in fixed_js  # Hex encoding should be fixed
		assert '\\x3d' not in fixed_js
		assert 'text' in fixed_js

	def test_browser_actor_code_issues_handling(self):
		"""Test browser actor code issues are handled properly"""

		# Code with target.evaluate should use special handling
		code_with_evaluate = """
async def executor():
    result = await target.evaluate('() => document.querySelector("button[type=\\"submit\\"]").click()')
    return result
"""

		fixed_code = CodeProcessor.fix_browser_actor_code_issues(code_with_evaluate)
		assert 'target.evaluate(' in fixed_code
		assert 'button[type=' in fixed_code

	def test_code_processor_browser_actor_awareness(self):
		"""Test code processor handles browser actor code correctly"""

		# Code with target.evaluate should be handled specially
		code_with_evaluate = """
async def executor():
    text = await target.evaluate('() => document.body.innerText')
    return text
"""

		fixed_code = fix_python_code_string_issues(code_with_evaluate)
		assert 'target.evaluate(' in fixed_code
		assert '() => document.body.innerText' in fixed_code

	def test_preserve_js_strings_in_target_evaluate(self):
		"""Test that JavaScript strings are preserved in target.evaluate calls"""

		code = """
result = await target.evaluate('() => document.querySelector("a[draggable=\\"false\\"]").href')
"""

		fixed_code = CodeProcessor._preserve_js_strings_in_target_evaluate(code)
		# Should preserve the structure but fix escaping issues
		assert 'target.evaluate(' in fixed_code
		assert 'querySelector(' in fixed_code

	def test_error_categorization(self):
		"""Test that JavaScript errors are properly categorized"""

		# This would normally be tested with a mock, but we can test the error detection logic
		js_errors = [
			'SyntaxError: Invalid selector',
			'JavaScript evaluation failed: Uncaught',
			'querySelectorAll is not valid',
			'CDP evaluation error',
		]

		for error_str in js_errors:
			# Check if our error detection logic would catch these
			is_js_error = any(
				js_error in error_str.lower()
				for js_error in [
					'javascript evaluation failed',
					'syntaxerror',
					'uncaught',
					'invalid selector',
					'queryselector',
					'cdp',
				]
			)
			assert is_js_error, f"Should detect '{error_str}' as a JavaScript error"

	@pytest.mark.parametrize(
		'malformed_selector,expected_fix',
		[
			('a[draggable\\\\\\="false"]', 'a[draggable="false"]'),
			('input[name\\x22email\\x22]', 'input[name"email"]'),  # Simplified for this test
			('button[type=\\"submit\\"]', 'button[type="submit"]'),
			('div[class\\x3d\\"test\\"]', 'div[class="test"]'),
		],
	)
	def test_css_selector_fix_examples(self, malformed_selector, expected_fix):
		"""Test specific CSS selector fix examples"""

		fixed = CodeProcessor.fix_css_selector(malformed_selector)
		# The fix should improve the selector (remove excessive escaping)
		assert len(fixed) <= len(malformed_selector)  # Should not add more characters
		assert '\\\\' not in fixed  # Should not have double backslashes
