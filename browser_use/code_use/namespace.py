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
	cdp_session = await browser_session.get_or_create_cdp_session()

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

			# Build comprehensive error message
			error_msg = f'JavaScript execution error: {error_text}'
			if error_details:
				error_msg += f'\nDetails: {" | ".join(error_details)}'
			if 'lineNumber' in exception:
				error_msg += f'\nat line {exception["lineNumber"]}'
				# Try to extract the offending line from the code
				try:
					lines = code.split('\n')
					line_num = exception['lineNumber'] - 1
					if 0 <= line_num < len(lines):
						error_msg += f'\nOffending line: {lines[line_num].strip()}'
				except Exception:
					pass

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
		tools = Tools()

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
	async def evaluate_wrapper(code: str) -> Any:
		return await evaluate(code, browser_session)

	namespace['evaluate'] = evaluate_wrapper

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

		# Add the wrapper to the namespace
		namespace[action_name] = make_action_wrapper(action_name, param_model, action_function)

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
