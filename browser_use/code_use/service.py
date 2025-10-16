"""Code-use agent service - Jupiter notebook-like code execution for browser automation."""

import asyncio
import logging
import traceback
from datetime import datetime
from pathlib import Path
from typing import Any

from uuid_extensions import uuid7str

from browser_use.browser import BrowserSession
from browser_use.browser.profile import BrowserProfile
from browser_use.dom.service import DomService
from browser_use.filesystem.file_system import FileSystem
from browser_use.llm.base import BaseChatModel
from browser_use.llm.messages import AssistantMessage, BaseMessage, SystemMessage, UserMessage
from browser_use.screenshots.service import ScreenshotService
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
		**kwargs,
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
			**kwargs: Additional keyword arguments for compatibility (ignored)
		"""
		# Log and ignore unknown kwargs for compatibility
		if kwargs:
			logger.debug(f'Ignoring additional kwargs for CodeUseAgent compatibility: {list(kwargs.keys())}')
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
		self._llm_messages: list[BaseMessage] = []  # Internal LLM conversation history
		self.complete_history: list[dict] = []  # Eval system history with model_output and result
		self.dom_service: DomService | None = None

		# Initialize screenshot service for eval tracking
		self.id = uuid7str()
		timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
		base_tmp = Path('/tmp')
		self.agent_directory = base_tmp / f'browser_use_code_agent_{self.id}_{timestamp}'
		self.screenshot_service = ScreenshotService(agent_directory=self.agent_directory)

	async def run(self, max_steps: int | None = None) -> NotebookSession:
		"""
		Run the agent to complete the task.

		Args:
			max_steps: Optional override for maximum number of steps (uses __init__ value if not provided)

		Returns:
			The notebook session with all executed cells
		"""
		# Use override if provided, otherwise use value from __init__
		steps_to_run = max_steps if max_steps is not None else self.max_steps
		self.max_steps = steps_to_run
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
		self._llm_messages.append(SystemMessage(content=system_prompt))
		self._llm_messages.append(UserMessage(content=f'Task: {self.task}'))

		# Main execution loop
		for step in range(self.max_steps):
			logger.info(f'\n\n\n\nStep {step + 1}/{self.max_steps}')

			try:
				# Get code from LLM (this also adds to self._llm_messages)
				code, full_llm_response = await self._get_code_from_llm()

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

				# Take screenshot for eval tracking
				screenshot_path = await self._capture_screenshot(step + 1)

				# Add step to complete_history for eval system
				await self._add_step_to_complete_history(
					model_output_code=code,
					full_llm_response=full_llm_response,
					output=output,
					error=error,
					screenshot_path=screenshot_path,
				)

				# Check if task is done
				if self._is_task_done():
					# Get the final result from namespace
					final_result = self.namespace.get('_task_result', output)
					logger.info('Task completed successfully')
					if final_result:
						logger.info(f'Final result: {final_result}')
					break

				# Add result to LLM messages for next iteration
				result_message = self._format_execution_result(code, output, error, browser_state)
				self._llm_messages.append(UserMessage(content=result_message))

			except Exception as e:
				logger.error(f'Error in step {step + 1}: {e}')
				traceback.print_exc()
				break
		else:
			# Loop completed without break - max_steps reached
			logger.warning(f'Maximum steps ({self.max_steps}) reached without task completion')

		# Auto-close browser if keep_alive is False
		await self.close()

		return self.session

	async def _get_code_from_llm(self) -> tuple[str, str]:
		"""Get Python code from the LLM.

		Returns:
			Tuple of (extracted_code, full_llm_response)
		"""
		# Call LLM with message history
		response = await self.llm.ainvoke(self._llm_messages)

		# Log the LLM's raw output for debugging
		logger.info(f'LLM Response:\n{response.completion}')

		# Store the full response
		full_response = response.completion

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

		# Add to LLM messages
		self._llm_messages.append(AssistantMessage(content=response.completion))

		return code, full_response

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
				# The function will execute in the namespace context
				wrapped_code = f"""
async def __code_use_exec__():
{chr(10).join('	' + line for line in code.split(chr(10)))}
	# Update globals with any new variables defined in this cell
	_locals = locals()
	for _key in list(_locals.keys()):
		if not _key.startswith('_'):
			globals()[_key] = _locals[_key]

__result__ = __code_use_exec__()
"""

				# Add asyncio to namespace if not already there
				if 'asyncio' not in self.namespace:
					self.namespace['asyncio'] = asyncio

				# Compile and execute in the namespace context
				# Using namespace as both globals and locals ensures all variables are accessible
				compiled_code = compile(wrapped_code, '<code>', 'exec')
				exec(compiled_code, self.namespace, self.namespace)

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
		"""Get the current browser state as text with DOM structure."""
		if not self.browser_session or not self.dom_service:
			return 'Browser state not available'

		try:
			# Get current URL
			url = await self.browser_session.get_current_page_url()

			# Get simplified DOM structure using JavaScript via CDP
			cdp_session = await self.browser_session.get_or_create_cdp_session()

			js_code = """
			(function() {
				// Get all interactive elements
				const allElements = document.querySelectorAll('a, button, input, select, textarea, [onclick], [role="button"]');

				// Get a sample of visible text elements
				const textElements = Array.from(document.querySelectorAll('h1, h2, h3, p, span, div'))
					.filter(el => el.textContent.trim().length > 0 && el.offsetParent !== null)
					.slice(0, 20);

				// Get form elements
				const forms = Array.from(document.querySelectorAll('form'));

				return {
					url: window.location.href,
					title: document.title,
					interactive_count: allElements.length,
					forms_count: forms.length,
					sample_text: textElements.map(el => ({
						tag: el.tagName.toLowerCase(),
						class: el.className,
						text: el.textContent.trim().substring(0, 100)
					})).slice(0, 10),
					sample_links: Array.from(document.querySelectorAll('a[href]'))
						.filter(a => a.textContent.trim().length > 0)
						.map(a => ({
							text: a.textContent.trim().substring(0, 50),
							href: a.href
						}))
						.slice(0, 10),
					inputs: Array.from(document.querySelectorAll('input, select, textarea'))
						.map(inp => ({
							type: inp.type || inp.tagName.toLowerCase(),
							name: inp.name,
							id: inp.id,
							placeholder: inp.placeholder
						}))
						.slice(0, 5)
				};
			})()
			"""

			result = await cdp_session.cdp_client.send.Runtime.evaluate(
				params={'expression': js_code, 'returnByValue': True, 'awaitPromise': True},
				session_id=cdp_session.session_id,
			)

			# Get the result data
			result_data = result.get('result', {})
			dom_structure = result_data.get('value', {})

			# Format the browser state
			lines = ['## Browser State']
			lines.append(f'**URL:** {url}')
			lines.append(f'**Title:** {dom_structure.get("title", "N/A")}')
			lines.append(f'**Interactive elements:** {dom_structure.get("interactive_count", 0)}')
			lines.append(f'**Forms:** {dom_structure.get("forms_count", 0)}')

			# Add sample text elements
			if dom_structure.get('sample_text'):
				lines.append('\n**Sample visible text:**')
				for item in dom_structure['sample_text'][:5]:
					lines.append(f'  - <{item["tag"]} class="{item["class"][:50]}"> {item["text"][:80]}')

			# Add sample links
			if dom_structure.get('sample_links'):
				lines.append('\n**Sample links:**')
				for link in dom_structure['sample_links'][:5]:
					lines.append(f'  - {link["text"][:50]} → {link["href"][:100]}')

			# Add input fields
			if dom_structure.get('inputs'):
				lines.append('\n**Input fields:**')
				for inp in dom_structure['inputs']:
					lines.append(f'  - {inp["type"]}: {inp.get("placeholder") or inp.get("name") or inp.get("id") or "unnamed"}')

			return '\n'.join(lines)

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

	async def _capture_screenshot(self, step_number: int) -> str | None:
		"""Capture and store screenshot for eval tracking."""
		if not self.browser_session:
			return None

		try:
			# Get browser state summary which includes screenshot
			state = await self.browser_session.get_browser_state_summary(include_screenshot=True)
			if state and state.screenshot:
				# Store screenshot using screenshot service
				screenshot_path = await self.screenshot_service.store_screenshot(state.screenshot, step_number)
				return str(screenshot_path) if screenshot_path else None
		except Exception as e:
			logger.warning(f'Failed to capture screenshot for step {step_number}: {e}')
			return None

	async def _add_step_to_complete_history(
		self, model_output_code: str, full_llm_response: str, output: str | None, error: str | None, screenshot_path: str | None
	) -> None:
		"""Add a step to complete_history in eval system format."""
		# Get current browser URL and title for state
		url = None
		title = None
		if self.browser_session:
			try:
				url = await self.browser_session.get_current_page_url()
				# Get title from browser
				cdp_session = await self.browser_session.get_or_create_cdp_session()
				result = await cdp_session.cdp_client.send.Runtime.evaluate(
					params={'expression': 'document.title', 'returnByValue': True},
					session_id=cdp_session.session_id,
				)
				title = result.get('result', {}).get('value')
			except Exception as e:
				logger.debug(f'Failed to get browser URL/title for history: {e}')

		# Create result entry matching eval system expectations
		# Check if this is a done result
		is_done = self._is_task_done()

		result_entry = {
			'extracted_content': output if output else None,
			'error': error if error else None,
			'is_done': is_done,  # Add is_done flag for eval system
			'success': not bool(error) if is_done else None,  # Add success flag if task is done
		}

		# Create state entry (will be converted to object with get_screenshot() method by DictToObject)
		# The eval system expects state to have url, title, and get_screenshot() method
		state_entry = {
			'url': url,
			'title': title,
			'screenshot_path': screenshot_path,  # Store path here for get_screenshot() to use
		}

		# Create metadata entry (eval system uses this for token counting and timing)
		# CodeUseAgent doesn't track these yet, so provide empty/null values
		metadata_entry = {
			'input_tokens': None,  # Token counting not implemented in CodeUseAgent yet
			'output_tokens': None,
			'step_start_time': None,  # Timing not implemented yet
			'step_end_time': None,
		}

		# Create history entry matching eval system format
		# For CodeUseAgent, model_output contains the code and full LLM response
		history_entry = {
			'model_output': {
				'model_output': model_output_code,  # The extracted code
				'full_response': full_llm_response,  # The complete LLM response including any text/reasoning
			},
			'result': [result_entry],  # Always a list
			'state': state_entry,  # Add state entry for eval system
			'metadata': metadata_entry,  # Add metadata for eval system
			'screenshot_path': screenshot_path,  # Keep this for backward compatibility
		}

		self.complete_history.append(history_entry)

	def screenshot_paths(self, n_last: int | None = None) -> list[str | None]:
		"""
		Get screenshot paths from complete_history for eval system.

		Args:
			n_last: Optional number of last screenshots to return

		Returns:
			List of screenshot file paths (or None for missing screenshots)
		"""
		paths = [step.get('screenshot_path') for step in self.complete_history]

		if n_last is not None:
			return paths[-n_last:] if len(paths) > n_last else paths

		return paths

	@property
	def message_manager(self):
		"""
		Compatibility property for eval system.
		Returns a mock object with last_input_messages attribute.
		"""

		class MockMessageManager:
			def __init__(self, llm_messages):
				# Convert code-use LLM messages to format expected by eval system
				self.last_input_messages = llm_messages

		return MockMessageManager(self._llm_messages)

	@property
	def history(self):
		"""
		Compatibility property for eval system.
		Returns a mock AgentHistoryList object with history attribute containing complete_history.
		This is what the eval system expects when it does: agent_history = agent.history
		"""

		class DictToObject:
			"""Convert dict to object with attribute access for eval compatibility."""

			def __init__(self, data):
				for key, value in data.items():
					if isinstance(value, dict):
						setattr(self, key, DictToObject(value))
					elif isinstance(value, list):
						setattr(self, key, [DictToObject(item) if isinstance(item, dict) else item for item in value])
					else:
						setattr(self, key, value)

			def __getattr__(self, name):
				"""Provide safe attribute access with defaults for missing attributes."""
				# Return None for missing attributes instead of raising AttributeError
				# This handles cases where eval system checks attributes that CodeUseAgent doesn't set
				return None

			def model_dump(self):
				"""Support model_dump() calls from eval system."""
				result = {}
				for key, value in self.__dict__.items():
					if isinstance(value, DictToObject):
						result[key] = value.model_dump()
					elif isinstance(value, list):
						result[key] = [item.model_dump() if isinstance(item, DictToObject) else item for item in value]
					else:
						result[key] = value
				return result

			def get_screenshot(self):
				"""Support get_screenshot() calls for state objects."""
				# CodeUseAgent stores screenshot paths, not base64 data
				return None

		class MockAgentHistoryList:
			def __init__(self, complete_history):
				# Convert each dict in complete_history to objects with attribute access
				self.history = [DictToObject(item) for item in complete_history]
				self.usage = None

		return MockAgentHistoryList(self.complete_history)

	async def close(self):
		"""Close the browser session."""
		if self.browser_session:
			# Check if we should close the browser based on keep_alive setting
			if not self.browser_session.browser_profile.keep_alive:
				await self.browser_session.kill()
			else:
				logger.debug('Browser keep_alive is True, not closing browser session')

	async def __aenter__(self):
		"""Async context manager entry."""
		return self

	async def __aexit__(self, exc_type, exc_val, exc_tb):
		"""Async context manager exit."""
		await self.close()
