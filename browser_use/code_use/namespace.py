"""Namespace initialization for code-use mode.

This module creates a namespace with all browser tools available as functions,
similar to a Jupiter notebook environment.
"""

import asyncio
import csv
import json
import logging
import re
from datetime import datetime
from pathlib import Path
from typing import Any

from browser_use.browser import BrowserSession
from browser_use.filesystem.file_system import FileSystem
from browser_use.llm.base import BaseChatModel
from browser_use.tools.service import Tools

logger = logging.getLogger(__name__)

# Try to import optional data science libraries
try:
	import numpy as np

	NUMPY_AVAILABLE = True
except ImportError:
	NUMPY_AVAILABLE = False

try:
	import pandas as pd

	PANDAS_AVAILABLE = True
except ImportError:
	PANDAS_AVAILABLE = False

try:
	import matplotlib.pyplot as plt

	MATPLOTLIB_AVAILABLE = True
except ImportError:
	MATPLOTLIB_AVAILABLE = False

try:
	import requests

	REQUESTS_AVAILABLE = True
except ImportError:
	REQUESTS_AVAILABLE = False

try:
	from bs4 import BeautifulSoup

	BS4_AVAILABLE = True
except ImportError:
	BS4_AVAILABLE = False

try:
	from pypdf import PdfReader

	PYPDF_AVAILABLE = True
except ImportError:
	PYPDF_AVAILABLE = False


def _strip_js_comments(js_code: str) -> str:
	"""
	Remove JavaScript comments before CDP evaluation.
	CDP's Runtime.evaluate doesn't handle comments in all contexts.

	Args:
		js_code: JavaScript code potentially containing comments

	Returns:
		JavaScript code with comments stripped
	"""
	# Remove single-line comments (// ...) but preserve URLs (http://, https://)
	# Negative lookbehind (?<!:) ensures we don't match // in URLs
	js_code = re.sub(r'(?<!:)//(?!/\w).*$', '', js_code, flags=re.MULTILINE)

	# Remove multi-line comments (/* ... */)
	js_code = re.sub(r'/\*.*?\*/', '', js_code, flags=re.DOTALL)

	return js_code


async def evaluate(code: str, browser_session: BrowserSession) -> Any:
	"""
	Execute JavaScript code in the browser and return the result.

	Args:
		code: JavaScript code to execute (must be wrapped in IIFE)

	Returns:
		The result of the JavaScript execution

	Example:
		result = await evaluate('''
		(function(){
			return Array.from(document.querySelectorAll('.product')).map(p => ({
				name: p.querySelector('.name').textContent,
				price: p.querySelector('.price').textContent
			}))
		})()
		''')
	"""
	# Strip JavaScript comments before CDP evaluation (CDP doesn't support them in all contexts)
	code = _strip_js_comments(code)

	cdp_session = await browser_session.get_or_create_cdp_session()

	# Inject jQuery and Lodash if not already present (for convenience with DOM queries and data processing)
	try:
		# Check if jQuery is already loaded
		jquery_check = await cdp_session.cdp_client.send.Runtime.evaluate(
			params={'expression': 'typeof jQuery !== "undefined" && typeof $ !== "undefined"', 'returnByValue': True},
			session_id=cdp_session.session_id,
		)
		jquery_exists = jquery_check.get('result', {}).get('value', False)

		if not jquery_exists:
			# Inject jQuery from CDN with proper wait
			jquery_injection = '''
			(function() {
				if (typeof jQuery === 'undefined') {
					var script = document.createElement('script');
					script.src = 'https://code.jquery.com/jquery-3.7.1.slim.min.js';
					script.integrity = 'sha256-kmHvs0B+OpCW5GVHUNjv9rOmY0IvSIRcf7zGUDTDQM8=';
					script.crossOrigin = 'anonymous';
					document.head.appendChild(script);
					return new Promise(resolve => {
						script.onload = () => {
							var checkReady = setInterval(() => {
								if (typeof jQuery !== 'undefined' && typeof $ !== 'undefined') {
									clearInterval(checkReady);
									resolve(true);
								}
							}, 10);
							setTimeout(() => {
								clearInterval(checkReady);
								resolve(false);
							}, 5000);
						};
						script.onerror = () => resolve(false);
					});
				}
				return true;
			})()
			'''
			inject_result = await cdp_session.cdp_client.send.Runtime.evaluate(
				params={'expression': jquery_injection, 'returnByValue': True, 'awaitPromise': True},
				session_id=cdp_session.session_id,
			)

			# Verify jQuery is actually available
			if inject_result.get('result', {}).get('value'):
				verify_check = await cdp_session.cdp_client.send.Runtime.evaluate(
					params={'expression': 'typeof $ === "function"', 'returnByValue': True},
					session_id=cdp_session.session_id,
				)
				if not verify_check.get('result', {}).get('value', False):
					logger.warning('jQuery injection reported success but $ is not a function')
	except Exception as jquery_error:
		# jQuery injection failed, but continue anyway - user code might not need it
		logger.debug(f'jQuery injection failed (non-critical): {jquery_error}')

	# Inject Lodash if not already present (for data processing and manipulation)
	try:
		lodash_check = await cdp_session.cdp_client.send.Runtime.evaluate(
			params={'expression': 'typeof _ !== "undefined"', 'returnByValue': True},
			session_id=cdp_session.session_id,
		)
		lodash_exists = lodash_check.get('result', {}).get('value', False)

		if not lodash_exists:
			# Inject Lodash from CDN with proper wait
			lodash_injection = '''
			(function() {
				if (typeof _ === 'undefined') {
					var script = document.createElement('script');
					script.src = 'https://cdn.jsdelivr.net/npm/lodash@4.17.21/lodash.min.js';
					script.integrity = 'sha256-qXBd/EfAdjOA2FGrGAG+b3YBn2tn5A6bhz+LSgYD96k=';
					script.crossOrigin = 'anonymous';
					document.head.appendChild(script);
					return new Promise(resolve => {
						script.onload = () => {
							var checkReady = setInterval(() => {
								if (typeof _ !== 'undefined' && typeof _.groupBy === 'function') {
									clearInterval(checkReady);
									resolve(true);
								}
							}, 10);
							setTimeout(() => {
								clearInterval(checkReady);
								resolve(false);
							}, 5000);
						};
						script.onerror = () => resolve(false);
					});
				}
				return true;
			})()
			'''
			inject_result = await cdp_session.cdp_client.send.Runtime.evaluate(
				params={'expression': lodash_injection, 'returnByValue': True, 'awaitPromise': True},
				session_id=cdp_session.session_id,
			)

			if inject_result.get('result', {}).get('value'):
				verify_check = await cdp_session.cdp_client.send.Runtime.evaluate(
					params={'expression': 'typeof _ === "function"', 'returnByValue': True},
					session_id=cdp_session.session_id,
				)
				if not verify_check.get('result', {}).get('value', False):
					logger.warning('Lodash injection reported success but _ is not a function')
	except Exception as lodash_error:
		logger.debug(f'Lodash injection failed (non-critical): {lodash_error}')

	try:
		# Execute JavaScript with proper error handling
		result = await cdp_session.cdp_client.send.Runtime.evaluate(
			params={'expression': code, 'returnByValue': True, 'awaitPromise': True},
			session_id=cdp_session.session_id,
		)

		# Check for JavaScript execution errors
		if result.get('exceptionDetails'):
			exception = result['exceptionDetails']
			error_text = exception.get('text', 'Unknown error')

			# Try to get more details from the exception
			error_details = []
			if 'exception' in exception:
				exc_obj = exception['exception']
				if 'description' in exc_obj:
					error_details.append(exc_obj['description'])
				elif 'value' in exc_obj:
					error_details.append(str(exc_obj['value']))

			# Build comprehensive error message with full CDP context
			error_msg = f'JavaScript execution error: {error_text}'
			if error_details:
				error_msg += f'\nDetails: {" | ".join(error_details)}'

			# Track if this is a cryptic error with no useful info
			is_cryptic_error = False
			line_num = exception.get('lineNumber')
			col_num = exception.get('columnNumber')

			# Check for cryptic "line 0 column 0" errors
			if (line_num == 0 or line_num is None) and (col_num == 0 or col_num is None):
				is_cryptic_error = True

			# Add column number if available
			if col_num is not None:
				error_msg += f' (column {col_num})'

			# Add stack trace if available
			if 'stackTrace' in exception and exception['stackTrace'].get('callFrames'):
				frames = exception['stackTrace']['callFrames']
				if frames:
					error_msg += '\n\nStack trace:'
					for frame in frames[:3]:  # Show first 3 frames
						func_name = frame.get('functionName', '<anonymous>')
						line = frame.get('lineNumber', '?')
						col = frame.get('columnNumber', '?')
						error_msg += f'\n  at {func_name} (line {line}, col {col})'

			# Add guidance for cryptic CDP errors
			if is_cryptic_error:
				error_msg += '\n\n💡 This is a cryptic CDP error with no useful location info. This is a CDP environment limitation, not your fault.'
				error_msg += '\n  • Simplify the JavaScript - break into smaller steps'
				error_msg += '\n  • Use different selectors or DOM methods'
				error_msg += '\n  • Try an alternative strategy to achieve the same goal'
				# Show first 200 chars of the JS code
				code_preview = code[:100].replace('\n', ' ')
				if len(code) > 100:
					code_preview += '... Truncated'
				error_msg += f'\n\nYour JS code: {code_preview}'

			raise RuntimeError(error_msg)

		# Get the result data
		result_data = result.get('result', {})

		# Get the actual value
		value = result_data.get('value')

		# Return the value directly
		if value is None:
			return None if 'value' in result_data else 'undefined'
		elif isinstance(value, (dict, list)):
			# Complex objects - already deserialized by returnByValue
			return value
		else:
			# Primitive values
			return value

	except Exception as e:
		raise RuntimeError(f'Failed to execute JavaScript: {type(e).__name__}: {e}') from e


def create_namespace(
	browser_session: BrowserSession,
	tools: Tools | None = None,
	page_extraction_llm: BaseChatModel | None = None,
	file_system: FileSystem | None = None,
	available_file_paths: list[str] | None = None,
	sensitive_data: dict[str, str | dict[str, str]] | None = None,
) -> dict[str, Any]:
	"""
	Create a namespace with all browser tools available as functions.

	This function creates a dictionary of functions that can be used to interact
	with the browser, similar to a Jupiter notebook environment.

	Args:
		browser_session: The browser session to use
		tools: Optional Tools instance (will create default if not provided)
		page_extraction_llm: Optional LLM for page extraction
		file_system: Optional file system for file operations
		available_file_paths: Optional list of available file paths
		sensitive_data: Optional sensitive data dictionary

	Returns:
		Dictionary containing all available functions and objects

	Example:
		namespace = create_namespace(browser_session)
		await namespace['navigate'](url='https://google.com')
		result = await namespace['evaluate']('document.title')
	"""
	if tools is None:
		# For code-use mode, include click, input, send_keys, and upload_file actions
		# but exclude the more complex ones that aren't needed
		tools = Tools(
			exclude_actions=[
				'scroll',
				'extract',
				'find_text',
				'select_dropdown',
				'dropdown_options',
				'screenshot',
				'search',
				# 'click',  # Keep for code-use
				# 'input',  # Keep for code-use
				'switch',
				# 'send_keys',  # Keep for code-use
				'close',
				'go_back',
				# 'upload_file',  # Keep for code-use
			]
		)

	if available_file_paths is None:
		available_file_paths = []

	namespace: dict[str, Any] = {
		# Core objects
		'browser': browser_session,
		'file_system': file_system,
		# Standard library modules (always available)
		'json': json,
		'asyncio': asyncio,
		'Path': Path,
		'csv': csv,
		're': re,
		'datetime': datetime,
	}

	# Add optional data science libraries if available
	if NUMPY_AVAILABLE:
		namespace['np'] = np
		namespace['numpy'] = np
	if PANDAS_AVAILABLE:
		namespace['pd'] = pd
		namespace['pandas'] = pd
	if MATPLOTLIB_AVAILABLE:
		namespace['plt'] = plt
		namespace['matplotlib'] = plt
	if REQUESTS_AVAILABLE:
		namespace['requests'] = requests
	if BS4_AVAILABLE:
		namespace['BeautifulSoup'] = BeautifulSoup
		namespace['bs4'] = BeautifulSoup
	if PYPDF_AVAILABLE:
		namespace['PdfReader'] = PdfReader
		namespace['pypdf'] = PdfReader

	# Add custom evaluate function that returns values directly
	async def evaluate_wrapper(code: str | None = None, *_args: Any, **kwargs: Any) -> Any:
		# Handle both positional and keyword argument styles
		if code is None:
			# Check if code was passed as keyword arg
			code = kwargs.get('code', kwargs.get('js_code', kwargs.get('expression', '')))
		if not code:
			raise ValueError('No JavaScript code provided to evaluate()')
		# Ignore any extra arguments (like browser_session if passed)
		return await evaluate(code, browser_session)

	namespace['evaluate'] = evaluate_wrapper

	# Add get_selector_from_index helper for code_use mode
	async def get_selector_from_index_wrapper(index: int) -> str:
		"""
		Get a JavaScript selector expression for an element by its index.

		AUTOMATICALLY handles Shadow DOM - returns the full traversal path!
		Just use the returned string directly in your JavaScript code.

		Args:
			index: The interactive index from the browser state (e.g., [123])

		Returns:
			str: JavaScript expression to access the element (handles Shadow DOM automatically)

		Examples:
			Regular element: Returns "document.querySelector('button.submit')"
			Shadow DOM element: Returns "document.querySelector('my-app').shadowRoot.querySelector('.item')"

		Usage:
			selector = await get_selector_from_index(123)
			result = await evaluate(f'({selector})?.textContent')
		"""
		from browser_use.dom.utils import generate_css_selector_for_element

		# Get element by index from browser session
		node = await browser_session.get_element_by_index(index)
		if node is None:
			raise ValueError(f'Element index {index} not found in browser state')

		# Build shadow DOM traversal path
		shadow_path = []
		current = node.parent_node
		while current:
			# Check if this is a shadow root (parent is a shadow host)
			if current.shadow_root_type is not None:
				# This node is a shadow host - we need to traverse through it
				host_selector = generate_css_selector_for_element(current)
				if host_selector:
					shadow_path.insert(0, {'type': 'shadow', 'selector': host_selector})

			# Check if this is an iframe
			if current.tag_name and current.tag_name.lower() == 'iframe':
				iframe_selector = generate_css_selector_for_element(current)
				if iframe_selector:
					shadow_path.insert(0, {'type': 'iframe', 'selector': iframe_selector})
					logger.warning(
						f'⚠️ Element [{index}] is inside an iframe. Iframe content requires special handling - regular DOM access won\'t work across iframe boundaries.'
					)

			current = current.parent_node

		# Generate selector for the target element
		element_selector = generate_css_selector_for_element(node)
		if not element_selector:
			if node.tag_name:
				element_selector = node.tag_name.lower()
			else:
				raise ValueError(f'Could not generate selector for element index {index}')

		# Build the JavaScript access expression
		if not shadow_path:
			# Simple case: regular DOM element
			js_expression = f'document.querySelector({json.dumps(element_selector)})'
		else:
			# Complex case: element is inside shadow DOM
			parts = []
			for step in shadow_path:
				if step['type'] == 'shadow':
					if not parts:
						# First step from document root
						parts.append(f'document.querySelector({json.dumps(step["selector"])})')
					parts.append('shadowRoot')
				elif step['type'] == 'iframe':
					# Iframe traversal - this won't work with regular querySelector
					# We need to warn but still try to provide useful output
					if not parts:
						parts.append(f'document.querySelector({json.dumps(step["selector"])})')
					parts.append('contentDocument')

			# Add final querySelector for the element
			parts.append(f'querySelector({json.dumps(element_selector)})')

			# Join with dots to create the full expression
			js_expression = '.'.join(parts)

			# Log helpful info for Shadow DOM
			logger.info(f'✨ Element [{index}] is in Shadow DOM - auto-generated traversal path')
			logger.info(f'   JavaScript expression: {js_expression}')

		return js_expression

	namespace['get_selector_from_index'] = get_selector_from_index_wrapper

	# Inject all tools as functions into the namespace
	# Skip 'evaluate' since we have a custom implementation above
	for action_name, action in tools.registry.registry.actions.items():
		if action_name == 'evaluate':
			continue  # Skip - use custom evaluate that returns Python objects directly
		param_model = action.param_model
		action_function = action.function

		# Create a closure to capture the current action_name, param_model, and action_function
		def make_action_wrapper(act_name, par_model, act_func):
			async def action_wrapper(*args, **kwargs):
				# Convert positional args to kwargs based on param model fields
				if args:
					# Get the field names from the pydantic model
					field_names = list(par_model.model_fields.keys())
					for i, arg in enumerate(args):
						if i < len(field_names):
							kwargs[field_names[i]] = arg

				# Create params from kwargs
				try:
					params = par_model(**kwargs)
				except Exception as e:
					raise ValueError(f'Invalid parameters for {act_name}: {e}') from e

				# Build special context
				special_context = {
					'browser_session': browser_session,
					'page_extraction_llm': page_extraction_llm,
					'available_file_paths': available_file_paths,
					'has_sensitive_data': False,  # Can be handled separately if needed
					'file_system': file_system,
				}

				# Execute the action
				result = await act_func(params=params, **special_context)

				# For code-use mode, we want to return the result directly
				# not wrapped in ActionResult
				if hasattr(result, 'extracted_content'):
					# Special handling for done action - mark task as complete
					if act_name == 'done' and hasattr(result, 'is_done') and result.is_done:
						namespace['_task_done'] = True
						# Store the extracted content as the final result
						if result.extracted_content:
							namespace['_task_result'] = result.extracted_content
						# Store the self-reported success status
						if hasattr(result, 'success'):
							namespace['_task_success'] = result.success

					# If there's extracted content, return it
					if result.extracted_content:
						return result.extracted_content
					# If there's an error, raise it
					if result.error:
						raise RuntimeError(result.error)
					# Otherwise return None
					return None
				return result

			return action_wrapper

		# Rename 'input' to 'input_text' to avoid shadowing Python's built-in input()
		namespace_action_name = 'input_text' if action_name == 'input' else action_name

		# Add the wrapper to the namespace
		namespace[namespace_action_name] = make_action_wrapper(action_name, param_model, action_function)

	return namespace


def get_namespace_documentation(namespace: dict[str, Any]) -> str:
	"""
	Generate documentation for all available functions in the namespace.

	Args:
		namespace: The namespace dictionary

	Returns:
		Markdown-formatted documentation string
	"""
	docs = ['# Available Functions\n']

	# Document each function
	for name, obj in sorted(namespace.items()):
		if callable(obj) and not name.startswith('_'):
			# Get function signature and docstring
			if hasattr(obj, '__doc__') and obj.__doc__:
				docs.append(f'## {name}\n')
				docs.append(f'{obj.__doc__}\n')

	return '\n'.join(docs)
