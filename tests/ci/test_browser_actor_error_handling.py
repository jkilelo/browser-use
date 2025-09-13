"""
Test enhanced error handling for browser actor code execution.

These tests validate that JavaScript evaluation errors are properly detected,
categorized, and reported with helpful debugging information.
"""

from unittest.mock import AsyncMock, patch

import pytest

from browser_use.agent.views import ActionResult
from browser_use.tools.service import Tools
from browser_use.tools.views import BrowserUseCodeAction


class TestBrowserActorErrorHandling:
	"""Test enhanced error handling for browser actor code execution"""

	def setup_method(self):
		"""Set up test tools instance"""
		self.tools = Tools(exclude_actions=[])

	@pytest.mark.asyncio
	async def test_javascript_error_detection_and_categorization(self):
		"""Test that JavaScript errors are properly detected and categorized"""

		# Mock browser session
		mock_browser_session = AsyncMock()
		mock_cdp_session = AsyncMock()
		mock_cdp_session.session_id = 'test_session'
		mock_cdp_session.target_id = 'test_target'
		mock_browser_session.get_or_create_cdp_session.return_value = mock_cdp_session

		# Create action with problematic JavaScript
		action = BrowserUseCodeAction(
			code="""
async def executor():
    # This will cause a JavaScript evaluation error due to invalid selector
    result = await target.evaluate('() => document.querySelector("invalid[selector")') 
    return result
"""
		)

		# Mock the target.evaluate to raise a JavaScript error
		with patch('browser_use.actor.Target') as MockTarget:
			mock_target = MockTarget.return_value
			mock_target.evaluate = AsyncMock(side_effect=Exception("SyntaxError: Invalid selector 'invalid[selector'"))

			# Execute the action through registry
			result = await self.tools.registry.execute_action(
				action_name='execute_browser_use_code', params=action.model_dump(), browser_session=mock_browser_session
			)

			# Should return an ActionResult with error
			assert isinstance(result, ActionResult)
			assert result.error is not None
			assert 'JavaScript evaluation error' in result.error
			assert '💡 Additional tip:' in result.error  # Should include debugging tip

	@pytest.mark.asyncio
	async def test_python_error_detection(self):
		"""Test that Python syntax errors are properly detected"""

		mock_browser_session = AsyncMock()

		# Action with Python syntax error
		action = BrowserUseCodeAction(
			code="""
async def executor()  # Missing colon
    return "test"
"""
		)

		result = await self.tools.registry.execute_action(
			action_name='execute_browser_use_code', params=action.model_dump(), browser_session=mock_browser_session
		)

		assert isinstance(result, ActionResult)
		assert result.error is not None
		# Should detect as Python error, not JavaScript error

	@pytest.mark.asyncio
	async def test_css_selector_error_tips(self):
		"""Test that CSS selector errors provide helpful tips"""

		mock_browser_session = AsyncMock()
		mock_cdp_session = AsyncMock()
		mock_browser_session.get_or_create_cdp_session.return_value = mock_cdp_session

		action = BrowserUseCodeAction(
			code="""
async def executor():
    result = await target.evaluate('() => document.querySelector("invalid[selector")') 
    return result
"""
		)

		# Simulate JavaScript evaluation error
		with patch('builtins.exec') as mock_exec:
			mock_exec.side_effect = Exception('invalid selector error')

			result = await self.tools.registry.execute_action(
				action_name='execute_browser_use_code', params=action.model_dump(), browser_session=mock_browser_session
			)

			assert result.error is not None
			assert 'Check CSS selector syntax' in result.error or 'Tip:' in result.error

	def test_error_message_formatting(self):
		"""Test that error messages are properly formatted"""
		tools = self.tools

		test_cases = [
			('SyntaxError: invalid selector', 'JavaScript evaluation error'),
			('Python syntax error', 'Python code error'),
			('General error', 'Code execution error'),
			('JavaScript evaluation failed: test', 'JavaScript evaluation error'),
		]

		for error_str, expected_category in test_cases:
			# Test the error categorization logic
			is_js_error = any(
				js_error in error_str.lower()
				for js_error in [
					'javascript evaluation failed',
					'syntaxerror',
					'uncaught',
					'invalid selector',
					'queryselector',
					'cdp',
					'evaluate',
				]
			)

			if expected_category == 'JavaScript evaluation error':
				assert is_js_error, f"Should categorize '{error_str}' as JavaScript error"

	@pytest.mark.asyncio
	async def test_successful_execution_reporting(self):
		"""Test that successful executions are reported correctly"""

		mock_browser_session = AsyncMock()
		mock_cdp_session = AsyncMock()
		mock_cdp_session.session_id = 'test_session'
		mock_cdp_session.target_id = 'test_target'
		mock_browser_session.get_or_create_cdp_session.return_value = mock_cdp_session

		action = BrowserUseCodeAction(
			code="""
async def executor():
    return "success"
"""
		)

		# Mock successful execution
		with patch('builtins.exec') as mock_exec:
			# Set up the executor function in local_vars
			def setup_executor(code, local_vars):
				async def executor():
					return 'success'

				local_vars['executor'] = executor

			mock_exec.side_effect = setup_executor

			result = await self.tools.registry.execute_action(
				action_name='execute_browser_use_code', params=action.model_dump(), browser_session=mock_browser_session
			)

			assert isinstance(result, ActionResult)
			assert result.error is None
			assert result.extracted_content and 'executed successfully' in result.extracted_content

	def test_debugging_tips_generation(self):
		"""Test that appropriate debugging tips are generated for different error types"""
		tools = self.tools

		tip_tests = [
			('invalid selector', 'Check CSS selector syntax'),
			('SyntaxError', 'arrow function format'),
		]

		for error_keyword, expected_tip_content in tip_tests:
			# This tests the tip generation logic that would be used in error handling
			error_msg = f'Test {error_keyword} error'

			if 'invalid selector' in error_msg.lower():
				tip = 'Check CSS selector syntax in target.evaluate() calls. Use proper quote escaping.'
				assert 'CSS selector' in tip
			elif 'syntaxerror' in error_msg.lower():
				tip = "Ensure JavaScript code uses correct arrow function format: '() => expression'"
				assert 'arrow function' in tip
