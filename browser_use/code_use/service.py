"""Code-use agent service - Jupiter notebook-like code execution for browser automation."""

import logging
import traceback
from pathlib import Path
from typing import Any

from browser_use.browser import BrowserSession
from browser_use.browser.profile import BrowserProfile
from browser_use.dom.service import DomService
from browser_use.filesystem.file_system import FileSystem
from browser_use.llm.base import BaseChatModel
from browser_use.llm.messages import AssistantMessage, BaseMessage, SystemMessage, UserMessage
from browser_use.tools.service import Tools

from .namespace import create_namespace
from .views import ExecutionStatus, NotebookSession

logger = logging.getLogger(__name__)


class CodeUseAgent:
	"""
	Agent that executes Python code in a notebook-like environment for browser automation.

	This agent provides a Jupiter notebook-like interface where the LLM writes Python code
	that gets executed in a persistent namespace with browser control functions available.
	"""

	def __init__(
		self,
		task: str,
		llm: BaseChatModel,
		browser_session: BrowserSession | None = None,
		browser_profile: BrowserProfile | None = None,
		tools: Tools | None = None,
		page_extraction_llm: BaseChatModel | None = None,
		file_system: FileSystem | None = None,
		available_file_paths: list[str] | None = None,
		sensitive_data: dict[str, str | dict[str, str]] | None = None,
		max_steps: int = 100,
	):
		"""
		Initialize the code-use agent.

		Args:
			task: The task description for the agent
			llm: The LLM to use for generating code
			browser_session: Optional browser session (will be created if not provided)
			browser_profile: Optional browser profile for creating a new session
			tools: Optional Tools instance (will create default if not provided)
			page_extraction_llm: Optional LLM for page extraction
			file_system: Optional file system for file operations
			available_file_paths: Optional list of available file paths
			sensitive_data: Optional sensitive data dictionary
			max_steps: Maximum number of execution steps
		"""
		self.task = task
		self.llm = llm
		self.browser_session = browser_session
		self.browser_profile = browser_profile or BrowserProfile()
		self.tools = tools or Tools()
		self.page_extraction_llm = page_extraction_llm
		self.file_system = file_system if file_system is not None else FileSystem(base_dir='./')
		self.available_file_paths = available_file_paths or []
		self.sensitive_data = sensitive_data
		self.max_steps = max_steps

		self.session = NotebookSession()
		self.namespace: dict[str, Any] = {}
		self.history: list[BaseMessage] = []
		self.dom_service: DomService | None = None

	async def run(self) -> NotebookSession:
		"""
		Run the agent to complete the task.

		Returns:
			The notebook session with all executed cells
		"""
		# Start browser if not provided
		if self.browser_session is None:
			self.browser_session = BrowserSession(browser_profile=self.browser_profile)
			await self.browser_session.start()

		# Initialize DOM service
		self.dom_service = DomService(browser_session=self.browser_session)

		# Create namespace with all tools
		self.namespace = create_namespace(
			browser_session=self.browser_session,
			tools=self.tools,
			page_extraction_llm=self.page_extraction_llm,
			file_system=self.file_system,
			available_file_paths=self.available_file_paths,
			sensitive_data=self.sensitive_data,
		)

		# Load system prompt
		system_prompt_path = Path(__file__).parent / 'system_prompt.md'
		system_prompt = system_prompt_path.read_text()

		# Initialize conversation with task
		self.history.append(SystemMessage(content=system_prompt))
		self.history.append(UserMessage(content=f'Task: {self.task}'))

		# Main execution loop
		for step in range(self.max_steps):
			logger.info(f'\n\n\n\nStep {step + 1}/{self.max_steps}')

			try:
				# Get code from LLM
				code = await self._get_code_from_llm()

				if not code or code.strip() == '':
					logger.warning('LLM returned empty code')
					break

				# Execute code
				output, error, browser_state = await self._execute_code(code)

				# Log execution results
				if error:
					logger.info(f'Code execution error:\n{error}')
				if output:
					logger.info(f'Code output:\n{output}')
				if browser_state:
					logger.info(f'Browser state:\n{browser_state}')

				# Check if task is done
				if self._is_task_done():
					logger.info('Task completed successfully')
					break

				# Add result to history for next iteration
				result_message = self._format_execution_result(code, output, error, browser_state)
				self.history.append(UserMessage(content=result_message))

			except Exception as e:
				logger.error(f'Error in step {step + 1}: {e}')
				traceback.print_exc()
				break

		return self.session

	async def _get_code_from_llm(self) -> str:
		"""Get Python code from the LLM."""
		# Call LLM with history
		response = await self.llm.ainvoke(self.history)

		# Log the LLM's raw output for debugging
		logger.info(f'LLM Response:\n{response.completion}')

		# Extract code from response
		code = response.completion

		# Try to extract code from markdown code blocks
		if '```python' in code:
			# Extract code between ```python and ```
			parts = code.split('```python')
			if len(parts) > 1:
				code_part = parts[1].split('```')[0]
				code = code_part.strip()
		elif '```' in code:
			# Extract code between ``` and ```
			parts = code.split('```')
			if len(parts) > 1:
				code = parts[1].strip()

		# Add to history
		self.history.append(AssistantMessage(content=response.completion))

		return code

	async def _execute_code(self, code: str) -> tuple[str | None, str | None, str | None]:
		"""
		Execute Python code in the namespace.

		Args:
			code: The Python code to execute

		Returns:
			Tuple of (output, error, browser_state)
		"""
		# Create new cell
		cell = self.session.add_cell(source=code)
		cell.status = ExecutionStatus.RUNNING
		cell.execution_count = self.session.increment_execution_count()

		output = None
		error = None
		browser_state = None

		try:
			# Capture output
			import io
			import sys

			old_stdout = sys.stdout
			sys.stdout = io.StringIO()

			try:
				# Wrap code in async function to handle top-level await
				# Use globals() to ensure variables persist across cells
				wrapped_code = f"""
async def __code_use_exec__():
	_globals = globals()
{chr(10).join('	' + line for line in code.split(chr(10)))}
	# Update globals with any new variables defined in this cell
	_locals = locals()
	for _key in list(_locals.keys()):
		if not _key.startswith('_'):
			_globals[_key] = _locals[_key]

import asyncio
__result__ = asyncio.create_task(__code_use_exec__())
"""

				# Compile and execute
				compiled_code = compile(wrapped_code, '<code>', 'exec')
				exec(compiled_code, self.namespace)

				# Wait for the task to complete
				task = self.namespace.get('__result__')
				if task:
					await task

				# Get output
				output_value = sys.stdout.getvalue()
				if output_value:
					output = output_value

			finally:
				sys.stdout = old_stdout
				# Clean up namespace
				self.namespace.pop('__code_use_exec__', None)
				self.namespace.pop('__result__', None)

			# Get browser state after execution
			if self.browser_session and self.dom_service:
				try:
					browser_state = await self._get_browser_state()
				except Exception as e:
					logger.warning(f'Failed to get browser state: {e}')

			cell.status = ExecutionStatus.SUCCESS
			cell.output = output
			cell.browser_state = browser_state

		except Exception as e:
			# For syntax errors and common parsing errors, show just the error message
			# without the full traceback to keep output clean
			if isinstance(e, SyntaxError):
				error = f'{type(e).__name__}: {e.msg}'
				if e.lineno:
					error += f' at line {e.lineno}'
				if e.text:
					error += f'\n{e.text}'
			else:
				# For other errors, include the full traceback
				error = f'{type(e).__name__}: {e}\n{traceback.format_exc()}'

			cell.status = ExecutionStatus.ERROR
			cell.error = error
			logger.error(f'Code execution error: {error}')

		return output, error, browser_state

	async def _get_browser_state(self) -> str:
		"""Get the current browser state as text."""
		if not self.browser_session or not self.dom_service:
			return 'Browser state not available'

		try:
			# Get current URL and title
			url = await self.browser_session.get_current_page_url()
			return f'Current page: {url}'
		except Exception as e:
			logger.error(f'Failed to get browser state: {e}')
			return f'Error getting browser state: {e}'

	def _format_execution_result(self, code: str, output: str | None, error: str | None, browser_state: str | None) -> str:
		"""Format the execution result for the LLM."""
		result = []
		result.append('## Executed\n')
		if error:
			result.append(f'**Error:**\n```\n{error}\n```\n')

		if output:
			# Truncate output if too long
			if len(output) > 20000:
				output = output[:19950] + '\n... [Truncated after 20000 characters]'
			result.append(f'**Output:**\n```\n{output}\n```\n')

		# Add browser state
		if browser_state:
			# Truncate browser state if too long
			if len(browser_state) > 30000:
				browser_state = browser_state[:29950] + '\n... [Truncated after 30000 characters]'
			result.append(f'\n{browser_state}\n')

		return ''.join(result)

	def _is_task_done(self) -> bool:
		"""Check if the task is marked as done in the namespace."""
		# Check if 'done' was called by looking for a special marker in namespace
		return self.namespace.get('_task_done', False)

	async def close(self):
		"""Close the browser session."""
		if self.browser_session:
			await self.browser_session.stop()

	async def __aenter__(self):
		"""Async context manager entry."""
		return self

	async def __aexit__(self, exc_type, exc_val, exc_tb):
		"""Async context manager exit."""
		await self.close()
