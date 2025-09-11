import logging
import os
from typing import Generic, TypeVar

try:
	from lmnr import Laminar  # type: ignore
except ImportError:
	Laminar = None  # type: ignore
from pydantic import BaseModel

from browser_use.agent.views import ActionModel, ActionResult
from browser_use.browser import BrowserSession
from browser_use.browser.events import (
	ClickElementEvent,
	CloseTabEvent,
	GoBackEvent,
	NavigateToUrlEvent,
	ScrollEvent,
	SwitchTabEvent,
	TypeTextEvent,
	UploadFileEvent,
)
from browser_use.browser.views import BrowserError
from browser_use.dom.service import EnhancedDOMTreeNode
from browser_use.filesystem.file_system import FileSystem
from browser_use.llm.base import BaseChatModel
from browser_use.observability import observe_debug
from browser_use.tools.registry.service import Registry
from browser_use.tools.views import (
	ClickElementAction,
	CloseTabAction,
	ExecuteCDPAction,
	GetDropdownOptionsAction,
	GoToUrlAction,
	InputTextAction,
	NoParamsAction,
	SearchGoogleAction,
	SwitchTabAction,
	UploadFileAction,
)
from browser_use.utils import _log_pretty_url, time_execution_sync

logger = logging.getLogger(__name__)

# Import EnhancedDOMTreeNode and rebuild event models that have forward references to it
# This must be done after all imports are complete
ClickElementEvent.model_rebuild()
TypeTextEvent.model_rebuild()
ScrollEvent.model_rebuild()
UploadFileEvent.model_rebuild()

Context = TypeVar('Context')

T = TypeVar('T', bound=BaseModel)


def handle_browser_error(e: BrowserError) -> ActionResult:
	if e.long_term_memory is not None:
		if e.short_term_memory is not None:
			return ActionResult(
				extracted_content=e.short_term_memory, error=e.long_term_memory, include_extracted_content_only_once=True
			)
		else:
			return ActionResult(error=e.long_term_memory)
	# Fallback to original error handling if long_term_memory is None
	logger.warning(
		'⚠️ A BrowserError was raised without long_term_memory - always set long_term_memory when raising BrowserError to propagate right messages to LLM.'
	)
	raise e


class Tools(Generic[Context]):
	# To use only 'done' and 'execute_js' actions, pass this to exclude_actions parameter:
	MINIMAL_ACTIONS_EXCLUDE_LIST = [
		'search_google',
		'go_back',
		'wait',
		'click_element_by_index',
		'input_text',
		'upload_file_to_element',
		'switch_tab',
		'close_tab',
		'extract_structured_data',
		'scroll',
		'send_keys',
		'scroll_to_text',
		'get_dropdown_options',
		'select_dropdown_option',
		'write_file',
		'replace_file_str',
		'read_file',
	]

	def __init__(
		self,
		exclude_actions: list[str] = MINIMAL_ACTIONS_EXCLUDE_LIST,
		output_model: type[T] | None = None,
		display_files_in_done_text: bool = True,
	):
		self.registry = Registry[Context](exclude_actions)
		self.display_files_in_done_text = display_files_in_done_text

		"""Register all default browser actions"""

		self._register_done_action(output_model)

		# Basic Navigation Actions
		@self.registry.action(
			'Search the query in Google, the query should be a search query like humans search in Google, concrete and not vague or super long.',
			param_model=SearchGoogleAction,
		)
		async def search_google(params: SearchGoogleAction, browser_session: BrowserSession):
			search_url = f'https://www.google.com/search?q={params.query}&udm=14'

			# Check if there's already a tab open on Google or agent's about:blank
			use_new_tab = True
			try:
				tabs = await browser_session.get_tabs()
				# Get last 4 chars of browser session ID to identify agent's tabs
				browser_session_label = str(browser_session.id)[-4:]
				logger.debug(f'Checking {len(tabs)} tabs for reusable tab (browser_session_label: {browser_session_label})')

				for i, tab in enumerate(tabs):
					logger.debug(f'Tab {i}: url="{tab.url}", title="{tab.title}"')
					# Check if tab is on Google domain
					if tab.url and tab.url.strip('/').lower() in ('https://www.google.com', 'https://google.com'):
						# Found existing Google tab, navigate in it
						logger.debug(f'Found existing Google tab at index {i}: {tab.url}, reusing it')

						# Switch to this tab first if it's not the current one
						from browser_use.browser.events import SwitchTabEvent

						if browser_session.agent_focus and tab.target_id != browser_session.agent_focus.target_id:
							try:
								switch_event = browser_session.event_bus.dispatch(SwitchTabEvent(target_id=tab.target_id))
								await switch_event
								await switch_event.event_result(raise_if_none=False)
							except Exception as e:
								logger.warning(f'Failed to switch to existing Google tab: {e}, will use new tab')
								continue

						use_new_tab = False
						break
					# Check if it's an agent-owned about:blank page (has "Starting agent XXXX..." title)
					# IMPORTANT: about:blank is also used briefly for new tabs the agent is trying to open, dont take over those!
					elif tab.url == 'about:blank' and tab.title:
						# Check if this is our agent's about:blank page with DVD animation
						# The title should be "Starting agent XXXX..." where XXXX is the browser_session_label
						if browser_session_label in tab.title:
							# This is our agent's about:blank page
							logger.debug(f'Found agent-owned about:blank tab at index {i} with title: "{tab.title}", reusing it')

							# Switch to this tab first
							from browser_use.browser.events import SwitchTabEvent

							if browser_session.agent_focus and tab.target_id != browser_session.agent_focus.target_id:
								try:
									switch_event = browser_session.event_bus.dispatch(SwitchTabEvent(target_id=tab.target_id))
									await switch_event
									await switch_event.event_result()
								except Exception as e:
									logger.warning(f'Failed to switch to agent-owned tab: {e}, will use new tab')
									continue

							use_new_tab = False
							break
			except Exception as e:
				logger.debug(f'Could not check for existing tabs: {e}, using new tab')

			# Dispatch navigation event
			try:
				event = browser_session.event_bus.dispatch(
					NavigateToUrlEvent(
						url=search_url,
						new_tab=use_new_tab,
					)
				)
				await event
				await event.event_result(raise_if_any=True, raise_if_none=False)
				memory = f"Searched Google for '{params.query}'"
				msg = f'🔍  {memory}'
				logger.info(msg)
				return ActionResult(extracted_content=memory, long_term_memory=memory)
			except Exception as e:
				logger.error(f'Failed to search Google: {e}')
				return ActionResult(error=f'Failed to search Google for "{params.query}": {str(e)}')

		@self.registry.action(
			'Navigate to URL, set new_tab=True to open in new tab, False to navigate in current tab', param_model=GoToUrlAction
		)
		async def go_to_url(params: GoToUrlAction, browser_session: BrowserSession):
			try:
				# Dispatch navigation event
				event = browser_session.event_bus.dispatch(NavigateToUrlEvent(url=params.url, new_tab=params.new_tab))
				await event
				await event.event_result(raise_if_any=True, raise_if_none=False)

				if params.new_tab:
					memory = f'Opened new tab with URL {params.url}'
					msg = f'🔗  Opened new tab with url {params.url}'
				else:
					memory = f'Navigated to {params.url}'
					msg = f'🔗 {memory}'

				logger.info(msg)
				return ActionResult(extracted_content=msg, long_term_memory=memory)
			except Exception as e:
				error_msg = str(e)
				# Always log the actual error first for debugging
				browser_session.logger.error(f'❌ Navigation failed: {error_msg}')

				# Check if it's specifically a RuntimeError about CDP client
				if isinstance(e, RuntimeError) and 'CDP client not initialized' in error_msg:
					browser_session.logger.error('❌ Browser connection failed - CDP client not properly initialized')
					return ActionResult(error=f'Browser connection error: {error_msg}')
				# Check for network-related errors
				elif any(
					err in error_msg
					for err in [
						'ERR_NAME_NOT_RESOLVED',
						'ERR_INTERNET_DISCONNECTED',
						'ERR_CONNECTION_REFUSED',
						'ERR_TIMED_OUT',
						'net::',
					]
				):
					site_unavailable_msg = f'Navigation failed - site unavailable: {params.url}'
					browser_session.logger.warning(f'⚠️ {site_unavailable_msg} - {error_msg}')
					return ActionResult(error=site_unavailable_msg)
				else:
					# Return error in ActionResult instead of re-raising
					return ActionResult(error=f'Navigation failed: {str(e)}')

		@self.registry.action('Go back', param_model=NoParamsAction)
		async def go_back(_: NoParamsAction, browser_session: BrowserSession):
			try:
				event = browser_session.event_bus.dispatch(GoBackEvent())
				await event
				memory = 'Navigated back'
				msg = f'🔙  {memory}'
				logger.info(msg)
				return ActionResult(extracted_content=memory)
			except Exception as e:
				logger.error(f'Failed to dispatch GoBackEvent: {type(e).__name__}: {e}')
				error_msg = f'Failed to go back: {str(e)}'
				return ActionResult(error=error_msg)

		# Element Interaction Actions

		@self.registry.action(
			'Click element by index. Only indices from your browser_state are allowed. Never use an index that is not inside your current browser_state. Set while_holding_ctrl=True to open any resulting navigation in a new tab.',
			param_model=ClickElementAction,
		)
		async def click_element_by_index(params: ClickElementAction, browser_session: BrowserSession):
			# Dispatch click event with node
			try:
				assert params.index != 0, (
					'Cannot click on element with index 0. If there are no interactive elements use scroll(), wait(), refresh(), etc. to troubleshoot'
				)

				# Look up the node from the selector map
				node = await browser_session.get_element_by_index(params.index)
				if node is None:
					raise ValueError(f'Element index {params.index} not found in browser state')

				event = browser_session.event_bus.dispatch(
					ClickElementEvent(node=node, while_holding_ctrl=params.while_holding_ctrl or False)
				)
				await event
				# Wait for handler to complete and get any exception or metadata
				click_metadata = await event.event_result(raise_if_any=True, raise_if_none=False)
				memory = f'Clicked element with index {params.index}'

				if params.while_holding_ctrl:
					memory += ' and opened in new tab'

				# Check if a new tab was opened (from watchdog metadata)
				elif isinstance(click_metadata, dict) and click_metadata.get('new_tab_opened'):
					memory += ' - which opened a new tab'

				msg = f'🖱️ {memory}'
				logger.info(msg)

				# Include click coordinates in metadata if available
				return ActionResult(
					long_term_memory=memory,
					metadata=click_metadata if isinstance(click_metadata, dict) else None,
				)
			except BrowserError as e:
				if 'Cannot click on <select> elements.' in str(e):
					try:
						return await get_dropdown_options(
							params=GetDropdownOptionsAction(index=params.index), browser_session=browser_session
						)
					except Exception as dropdown_error:
						logger.error(
							f'Failed to get dropdown options as shortcut during click_element_by_index on dropdown: {type(dropdown_error).__name__}: {dropdown_error}'
						)

				return handle_browser_error(e)
			except Exception as e:
				error_msg = f'Failed to click element {params.index}: {str(e)}'
				return ActionResult(error=error_msg)

		@self.registry.action(
			'Input text into an input interactive element. Only input text into indices that are inside your current browser_state. Never input text into indices that are not inside your current browser_state.',
			param_model=InputTextAction,
		)
		async def input_text(params: InputTextAction, browser_session: BrowserSession, has_sensitive_data: bool = False):
			# Look up the node from the selector map
			node = await browser_session.get_element_by_index(params.index)
			if node is None:
				raise ValueError(f'Element index {params.index} not found in browser state')

			# Dispatch type text event with node
			try:
				event = browser_session.event_bus.dispatch(
					TypeTextEvent(node=node, text=params.text, clear_existing=params.clear_existing)
				)
				await event
				input_metadata = await event.event_result(raise_if_any=True, raise_if_none=False)
				msg = f"Input '{params.text}' into element {params.index}."
				logger.debug(msg)

				# Include input coordinates in metadata if available
				return ActionResult(
					extracted_content=msg,
					long_term_memory=f"Input '{params.text}' into element {params.index}.",
					metadata=input_metadata if isinstance(input_metadata, dict) else None,
				)
			except BrowserError as e:
				return handle_browser_error(e)
			except Exception as e:
				# Log the full error for debugging
				logger.error(f'Failed to dispatch TypeTextEvent: {type(e).__name__}: {e}')
				error_msg = f'Failed to input text into element {params.index}: {e}'
				return ActionResult(error=error_msg)

		@self.registry.action('Upload file to interactive element with file path', param_model=UploadFileAction)
		async def upload_file_to_element(
			params: UploadFileAction, browser_session: BrowserSession, available_file_paths: list[str], file_system: FileSystem
		):
			# Check if file is in available_file_paths (user-provided or downloaded files)
			# For remote browsers (is_local=False), we allow absolute remote paths even if not tracked locally
			if params.path not in available_file_paths:
				# Also check if it's a recently downloaded file that might not be in available_file_paths yet
				downloaded_files = browser_session.downloaded_files
				if params.path not in downloaded_files:
					# Finally, check if it's a file in the FileSystem service
					if file_system and file_system.get_dir():
						# Check if the file is actually managed by the FileSystem service
						# The path should be just the filename for FileSystem files
						file_obj = file_system.get_file(params.path)
						if file_obj:
							# File is managed by FileSystem, construct the full path
							file_system_path = str(file_system.get_dir() / params.path)
							params = UploadFileAction(index=params.index, path=file_system_path)
						else:
							# If browser is remote, allow passing a remote-accessible absolute path
							if not browser_session.is_local:
								pass
							else:
								msg = f'File path {params.path} is not available. Upload files must be in available_file_paths, downloaded_files, or a file managed by file_system.'
								logger.error(f'❌ {msg}')
								return ActionResult(error=msg)
					else:
						# If browser is remote, allow passing a remote-accessible absolute path
						if not browser_session.is_local:
							pass
						else:
							msg = f'File path {params.path} is not available. Upload files must be in available_file_paths, downloaded_files, or a file managed by file_system.'
							raise BrowserError(message=msg, long_term_memory=msg)

			# For local browsers, ensure the file exists on the local filesystem
			if browser_session.is_local:
				if not os.path.exists(params.path):
					msg = f'File {params.path} does not exist'
					return ActionResult(error=msg)

			# Get the selector map to find the node
			selector_map = await browser_session.get_selector_map()
			if params.index not in selector_map:
				msg = f'Element with index {params.index} does not exist.'
				return ActionResult(error=msg)

			node = selector_map[params.index]

			# Helper function to find file input near the selected element
			def find_file_input_near_element(
				node: EnhancedDOMTreeNode, max_height: int = 3, max_descendant_depth: int = 3
			) -> EnhancedDOMTreeNode | None:
				"""Find the closest file input to the selected element."""

				def find_file_input_in_descendants(n: EnhancedDOMTreeNode, depth: int) -> EnhancedDOMTreeNode | None:
					if depth < 0:
						return None
					if browser_session.is_file_input(n):
						return n
					for child in n.children_nodes or []:
						result = find_file_input_in_descendants(child, depth - 1)
						if result:
							return result
					return None

				current = node
				for _ in range(max_height + 1):
					# Check the current node itself
					if browser_session.is_file_input(current):
						return current
					# Check all descendants of the current node
					result = find_file_input_in_descendants(current, max_descendant_depth)
					if result:
						return result
					# Check all siblings and their descendants
					if current.parent_node:
						for sibling in current.parent_node.children_nodes or []:
							if sibling is current:
								continue
							if browser_session.is_file_input(sibling):
								return sibling
							result = find_file_input_in_descendants(sibling, max_descendant_depth)
							if result:
								return result
					current = current.parent_node
					if not current:
						break
				return None

			# Try to find a file input element near the selected element
			file_input_node = find_file_input_near_element(node)

			# If not found near the selected element, fallback to finding the closest file input to current scroll position
			if file_input_node is None:
				logger.info(
					f'No file upload element found near index {params.index}, searching for closest file input to scroll position'
				)

				# Get current scroll position
				cdp_session = await browser_session.get_or_create_cdp_session()
				try:
					scroll_info = await cdp_session.cdp_client.send.Runtime.evaluate(
						params={'expression': 'window.scrollY || window.pageYOffset || 0'}, session_id=cdp_session.session_id
					)
					current_scroll_y = scroll_info.get('result', {}).get('value', 0)
				except Exception:
					current_scroll_y = 0

				# Find all file inputs in the selector map and pick the closest one to scroll position
				closest_file_input = None
				min_distance = float('inf')

				for idx, element in selector_map.items():
					if browser_session.is_file_input(element):
						# Get element's Y position
						if element.absolute_position:
							element_y = element.absolute_position.y
							distance = abs(element_y - current_scroll_y)
							if distance < min_distance:
								min_distance = distance
								closest_file_input = element

				if closest_file_input:
					file_input_node = closest_file_input
					logger.info(f'Found file input closest to scroll position (distance: {min_distance}px)')
				else:
					msg = 'No file upload element found on the page'
					logger.error(msg)
					raise BrowserError(msg)
					# TODO: figure out why this fails sometimes + add fallback hail mary, just look for any file input on page

			# Dispatch upload file event with the file input node
			try:
				event = browser_session.event_bus.dispatch(UploadFileEvent(node=file_input_node, file_path=params.path))
				await event
				await event.event_result(raise_if_any=True, raise_if_none=False)
				msg = f'Successfully uploaded file to index {params.index}'
				logger.info(f'📁 {msg}')
				return ActionResult(
					extracted_content=msg,
					long_term_memory=f'Uploaded file {params.path} to element {params.index}',
				)
			except Exception as e:
				logger.error(f'Failed to upload file: {e}')
				raise BrowserError(f'Failed to upload file: {e}')

		# Tab Management Actions

		@self.registry.action('Switch tab', param_model=SwitchTabAction)
		async def switch_tab(params: SwitchTabAction, browser_session: BrowserSession):
			# Dispatch switch tab event
			try:
				target_id = await browser_session.get_target_id_from_tab_id(params.tab_id)

				event = browser_session.event_bus.dispatch(SwitchTabEvent(target_id=target_id))
				await event
				new_target_id = await event.event_result(raise_if_any=True, raise_if_none=False)
				assert new_target_id, 'SwitchTabEvent did not return a TargetID for the new tab that was switched to'
				memory = f'Switched to Tab with ID {new_target_id[-4:]}'
				logger.info(f'🔄  {memory}')
				return ActionResult(extracted_content=memory, long_term_memory=memory)
			except Exception as e:
				logger.error(f'Failed to switch tab: {type(e).__name__}: {e}')
				return ActionResult(error=f'Failed to switch to tab {params.tab_id}.')

		@self.registry.action('Close an existing tab', param_model=CloseTabAction)
		async def close_tab(params: CloseTabAction, browser_session: BrowserSession):
			# Dispatch close tab event
			try:
				target_id = await browser_session.get_target_id_from_tab_id(params.tab_id)
				cdp_session = await browser_session.get_or_create_cdp_session()
				target_info = await cdp_session.cdp_client.send.Target.getTargetInfo(
					params={'targetId': target_id}, session_id=cdp_session.session_id
				)
				tab_url = target_info['targetInfo']['url']
				event = browser_session.event_bus.dispatch(CloseTabEvent(target_id=target_id))
				await event
				await event.event_result(raise_if_any=True, raise_if_none=False)
				memory = f'Closed tab # {params.tab_id} ({_log_pretty_url(tab_url)})'
				logger.info(f'🗑️  {memory}')
				return ActionResult(
					extracted_content=memory,
					long_term_memory=memory,
				)
			except Exception as e:
				logger.error(f'Failed to close tab: {e}')
				return ActionResult(error=f'Failed to close tab {params.tab_id}.')

		# General CDP execution tool
		@self.registry.action(
			"""Execute JavaScript - SINGLE LINE ONLY. Auto-fixes syntax errors.

Use rich attributes from browser_state for precise selectors:

ONE LINE EXAMPLES:
- By name: document.querySelector('input[name="firstName"]').value
- By ID: document.querySelector('#submit-btn').click()  
- By class: document.querySelectorAll('.product-card').length
- Extract: JSON.stringify(Array.from(document.querySelectorAll('input[required="true"]')).map(el => el.name))
- Navigate: window.location.href = 'https://example.com/page'
- Scroll: window.scrollBy(0, 500)

ANTI-LOOP RULE: If same code fails twice, MUST try different approach. Never repeat failing code.""",
			param_model=ExecuteCDPAction,
		)
		async def execute_js(params: ExecuteCDPAction, browser_session: BrowserSession):
			# Pre-process JavaScript to fix common issues
			original_code = params.javascript_code
			enhanced_code = self._fix_common_js_issues(original_code)

			# Log the transformation for debugging
			if enhanced_code != original_code:
				logger.debug(f'🔧 JS Auto-fix applied:\nOriginal: {original_code[:100]}...\nFixed: {enhanced_code[:100]}...')

			cdp_session = await browser_session.get_or_create_cdp_session()
			try:
				result = await cdp_session.cdp_client.send.Runtime.evaluate(
					params={'expression': enhanced_code}, session_id=cdp_session.session_id
				)

				if result.get('exceptionDetails'):
					exception = result['exceptionDetails']

					# Check for CSP or security policy errors
					error_text = exception.get('text', '')
					error_description = exception.get('exception', {}).get('description', '')
					combined_error = f'{error_text} {error_description}'.lower()

					if any(
						csp_term in combined_error
						for csp_term in ['content security policy', 'refused to execute', 'unsafe-eval']
					):
						return ActionResult(
							error=f'Content Security Policy (CSP) blocked JavaScript execution. Website prevents running custom JavaScript.\n\nFailed code: {params.javascript_code[:150]}...'
						)

					# Extract comprehensive error information
					error_parts = []

					# Basic error info
					error_type = exception.get('exception', {}).get('className', 'Error')
					error_description = exception.get('text', exception.get('exception', {}).get('description', 'Unknown error'))
					error_parts.append(f'{error_type}: {error_description}')

					# Location information
					line_num = exception.get('lineNumber', 0)
					column_num = exception.get('columnNumber', 0)
					if line_num > 0:
						error_parts.append(f'at line {line_num + 1}, column {column_num + 1}')

					# Stack trace if available
					stack_trace = exception.get('exception', {}).get('description')
					if stack_trace and stack_trace != error_description:
						lines = stack_trace.split('\n')
						if len(lines) > 1:
							stack_info = lines[1].strip()
							if stack_info and 'at ' in stack_info:
								error_parts.append(f'Stack: {stack_info}')

					# Add debugging tips
					debugging_tips = self._get_javascript_debugging_tips(error_type, error_description, params.javascript_code)
					if debugging_tips:
						error_parts.append(f'Tip: {debugging_tips}')

					# Compile error message
					detailed_error = ' | '.join(error_parts)
					code_preview = params.javascript_code[:1000] + ('...' if len(params.javascript_code) > 1000 else '')
					full_error_msg = f'{detailed_error}\n\nFailed code: {code_preview}'

					logger.error(f'❌ JavaScript execution failed: {detailed_error}')
					return ActionResult(error=f'JavaScript execution failed: {full_error_msg}')

				# Handle successful execution
				result_obj = result.get('result', {})
				value = result_obj.get('value')

				if value is None:
					result_type = result_obj.get('type', 'undefined')
					if result_type == 'undefined':
						response_msg = 'Executed successfully (returned undefined)'
					elif result_type == 'object' and result_obj.get('subtype') == 'null':
						response_msg = 'Executed successfully (returned null)'
					else:
						response_msg = f'Executed successfully (returned {result_type})'
				else:
					response_msg = str(value)

				logger.info('✅ CDP execution completed successfully')
				return ActionResult(
					extracted_content=f'Executed JavaScript: {params.javascript_code} Result: {response_msg}',
				)
			except Exception as e:
				logger.error(f'❌ CDP execution failed with exception: {e}')
				return ActionResult(error=f'CDP execution failed: {str(e)}')

	def _get_javascript_debugging_tips(self, error_type: str, error_description: str, code: str) -> str:
		"""Provide debugging tips based on the error type."""
		error_lower = f'{error_type} {error_description}'.lower()

		if 'cannot read' in error_lower and 'null' in error_lower:
			return 'Element not found. Check if selector exists and page is loaded.'
		elif 'cannot read' in error_lower and 'undefined' in error_lower:
			return 'Property/method does not exist. Check spelling and object structure.'
		elif 'permission denied' in error_lower or 'access denied' in error_lower:
			return 'Cross-origin or iframe access blocked. Use getIframeDocument() helper.'
		elif 'form.submit is not a function' in error_lower:
			return 'Form may be overridden. Try form.dispatchEvent(new Event("submit")).'
		elif 'click' in code.lower() and 'function' in error_lower:
			return 'Element may not be clickable. Try element.dispatchEvent(new MouseEvent("click")).'
		elif 'queryselector' in error_lower:
			return 'Invalid CSS selector. Check syntax and escape special characters.'

		return ''

	def _fix_common_js_issues(self, code: str) -> str:
		"""Fix common JavaScript issues that cause SyntaxError: Uncaught."""
		import re

		# Remove optional chaining which isn't supported in older CDP
		code = re.sub(r'\?\.\s*', '.', code)

		# Fix missing quotes around selectors
		code = re.sub(r'querySelectorAll\(([a-zA-Z]\w*)\)', r"querySelectorAll('\1')", code)
		code = re.sub(r'querySelector\(([a-zA-Z]\w*)\)', r"querySelector('\1')", code)

		# Handle multiline code - convert to single expression or add return
		lines = [line.strip() for line in code.strip().split('\n') if line.strip()]

		if len(lines) > 1:
			# Check if last line is already a return or single expression
			last_line = lines[-1]

			# If last line ends with semicolon, it's a statement not expression
			if last_line.endswith(';'):
				# Convert last statement to return
				if last_line.startswith('JSON.stringify'):
					lines[-1] = f'return {last_line[:-1]}'  # Remove ; and add return
				elif not last_line.startswith('return'):
					lines[-1] = f'return {last_line[:-1]}'  # Remove ; and add return

			# Join with semicolons for multiple statements
			if any(line.startswith('return') for line in lines):
				code = '; '.join(lines[:-1]) + '; ' + lines[-1]
			else:
				# If no return, make it a single expression
				if lines[-1].startswith('JSON.stringify'):
					code = '; '.join(lines)
				else:
					code = '; '.join(lines[:-1]) + '; return ' + lines[-1]

		return code

	# Act --------------------------------------------------------------------
	@observe_debug(ignore_input=True, ignore_output=True, name='act')
	@time_execution_sync('--act')
	async def act(
		self,
		action: ActionModel,
		browser_session: BrowserSession,
		#
		page_extraction_llm: BaseChatModel | None = None,
		sensitive_data: dict[str, str | dict[str, str]] | None = None,
		available_file_paths: list[str] | None = None,
		file_system: FileSystem | None = None,
	) -> ActionResult:
		"""Execute an action"""

		for action_name, params in action.model_dump(exclude_unset=True).items():
			if params is not None:
				# Use Laminar span if available, otherwise use no-op context manager
				if Laminar is not None:
					span_context = Laminar.start_as_current_span(
						name=action_name,
						input={
							'action': action_name,
							'params': params,
						},
						span_type='TOOL',
					)
				else:
					# No-op context manager when lmnr is not available
					from contextlib import nullcontext

					span_context = nullcontext()

				with span_context:
					try:
						result = await self.registry.execute_action(
							action_name=action_name,
							params=params,
							browser_session=browser_session,
							page_extraction_llm=page_extraction_llm,
							file_system=file_system,
							sensitive_data=sensitive_data,
							available_file_paths=available_file_paths,
						)
					except BrowserError as e:
						logger.error(f'❌ Action {action_name} failed with BrowserError: {str(e)}')
						result = handle_browser_error(e)
					except TimeoutError as e:
						logger.error(f'❌ Action {action_name} failed with TimeoutError: {str(e)}')
						result = ActionResult(error=f'{action_name} was not executed due to timeout.')
					except Exception as e:
						# Log the original exception with traceback for observability
						logger.error(f"Action '{action_name}' failed with error: {str(e)}")
						result = ActionResult(error=str(e))

					if Laminar is not None:
						Laminar.set_span_output(result)

				if isinstance(result, str):
					return ActionResult(extracted_content=result)
				elif isinstance(result, ActionResult):
					return result
				elif result is None:
					return ActionResult()
				else:
					raise ValueError(f'Invalid action result type: {type(result)} of {result}')
		return ActionResult()


# Alias for backwards compatibility
Controller = Tools
