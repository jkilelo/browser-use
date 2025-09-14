from collections.abc import Iterable, Mapping
from dataclasses import dataclass, field
from typing import Any, Literal, TypeVar, cast, overload

import httpx
from openai import APIConnectionError, APIStatusError, AsyncOpenAI, RateLimitError
from openai.types.chat import ChatCompletionContentPartTextParam
from openai.types.chat.chat_completion import ChatCompletion
from openai.types.responses import Response, ResponseInputParam
from openai.types.responses.easy_input_message_param import EasyInputMessageParam
from openai.types.responses.function_tool_param import FunctionToolParam
from openai.types.responses.response_input_image_param import ResponseInputImageParam
from openai.types.responses.response_input_message_content_list_param import (
	ResponseInputContentParam,
	ResponseInputMessageContentListParam,
)
from openai.types.responses.response_input_text_param import ResponseInputTextParam
from openai.types.responses.tool_param import ToolParam
from openai.types.shared.chat_model import ChatModel
from openai.types.shared_params.reasoning_effort import ReasoningEffort
from openai.types.shared_params.response_format_json_schema import JSONSchema, ResponseFormatJSONSchema
from pydantic import BaseModel

from browser_use.llm.base import BaseChatModel
from browser_use.llm.exceptions import ModelProviderError
from browser_use.llm.messages import BaseMessage
from browser_use.llm.openai.serializer import OpenAIMessageSerializer
from browser_use.llm.schema import SchemaOptimizer
from browser_use.llm.views import ChatInvokeCompletion, ChatInvokeUsage

T = TypeVar('T', bound=BaseModel)


@dataclass
class ChatOpenAI(BaseChatModel):
	"""
	A wrapper around AsyncOpenAI that implements the BaseLLM protocol.

	This class accepts all AsyncOpenAI parameters while adding model
	and temperature parameters for the LLM interface (if temperature it not `None`).
	"""

	# Model configuration
	model: ChatModel | str

	# Model params
	temperature: float | None = 0.2
	frequency_penalty: float | None = 0.3  # this avoids infinite generation of \t for models like 4.1-mini
	reasoning_effort: ReasoningEffort = 'low'
	seed: int | None = None
	service_tier: Literal['auto', 'default', 'flex', 'priority', 'scale'] | None = None
	top_p: float | None = None
	add_schema_to_system_prompt: bool = False  # Add JSON schema to system prompt instead of using response_format

	# Client initialization parameters
	api_key: str | None = None
	organization: str | None = None
	project: str | None = None
	base_url: str | httpx.URL | None = None
	websocket_base_url: str | httpx.URL | None = None
	timeout: float | httpx.Timeout | None = None
	max_retries: int = 5  # Increase default retries for automation reliability
	default_headers: Mapping[str, str] | None = None
	default_query: Mapping[str, object] | None = None
	http_client: httpx.AsyncClient | None = None
	_strict_response_validation: bool = False
	max_completion_tokens: int | None = 4096
	response_api: bool = True
	reasoning_models: list[ChatModel | str] | None = field(
		default_factory=lambda: [
			'o4-mini',
			'o3',
			'o3-mini',
			'o1',
			'o1-pro',
			'o3-pro',
			'gpt-5',
			'gpt-5-mini',
			'gpt-5-nano',
		]
	)

	# Static
	@property
	def provider(self) -> str:
		return 'openai'

	def _get_client_params(self) -> dict[str, Any]:
		"""Prepare client parameters dictionary."""
		# Define base client params
		base_params = {
			'api_key': self.api_key,
			'organization': self.organization,
			'project': self.project,
			'base_url': self.base_url,
			'websocket_base_url': self.websocket_base_url,
			'timeout': self.timeout,
			'max_retries': self.max_retries,
			'default_headers': self.default_headers,
			'default_query': self.default_query,
			'_strict_response_validation': self._strict_response_validation,
		}

		# Create client_params dict with non-None values
		client_params = {k: v for k, v in base_params.items() if v is not None}

		# Add http_client if provided
		if self.http_client is not None:
			client_params['http_client'] = self.http_client

		return client_params

	def get_client(self) -> AsyncOpenAI:
		"""
		Returns an AsyncOpenAI client.

		Returns:
			AsyncOpenAI: An instance of the AsyncOpenAI client.
		"""
		client_params = self._get_client_params()
		return AsyncOpenAI(**client_params)

	@property
	def name(self) -> str:
		return str(self.model)

	def _get_usage_from_response(self, response: Any) -> ChatInvokeUsage | None:
		"""Extract usage from Response API response"""
		try:
			if hasattr(response, 'usage') and response.usage is not None:
				usage_data = response.usage
				completion_tokens = getattr(usage_data, 'completion_tokens', 0)
				prompt_tokens = getattr(usage_data, 'prompt_tokens', 0)
				total_tokens = getattr(usage_data, 'total_tokens', prompt_tokens + completion_tokens)

				return ChatInvokeUsage(
					prompt_tokens=prompt_tokens,
					prompt_cached_tokens=None,
					prompt_cache_creation_tokens=None,
					prompt_image_tokens=None,
					completion_tokens=completion_tokens,
					total_tokens=total_tokens,
				)
		except Exception:
			pass
		return None

	def _get_usage(self, response: ChatCompletion) -> ChatInvokeUsage | None:
		if response.usage is not None:
			completion_tokens = response.usage.completion_tokens
			completion_token_details = response.usage.completion_tokens_details
			if completion_token_details is not None:
				reasoning_tokens = completion_token_details.reasoning_tokens
				if reasoning_tokens is not None:
					completion_tokens += reasoning_tokens

			usage = ChatInvokeUsage(
				prompt_tokens=response.usage.prompt_tokens,
				prompt_cached_tokens=response.usage.prompt_tokens_details.cached_tokens
				if response.usage.prompt_tokens_details is not None
				else None,
				prompt_cache_creation_tokens=None,
				prompt_image_tokens=None,
				# Completion
				completion_tokens=completion_tokens,
				total_tokens=response.usage.total_tokens,
			)
		else:
			usage = None

		return usage

	@overload
	async def ainvoke(self, messages: list[BaseMessage], output_format: None = None) -> ChatInvokeCompletion[str]: ...

	@overload
	async def ainvoke(self, messages: list[BaseMessage], output_format: type[T]) -> ChatInvokeCompletion[T]: ...

	async def ainvoke(
		self, messages: list[BaseMessage], output_format: type[T] | None = None
	) -> ChatInvokeCompletion[T] | ChatInvokeCompletion[str]:
		"""
		Invoke the model with the given messages.

		Args:
			messages: List of chat messages
			output_format: Optional Pydantic model class for structured output

		Returns:
			Either a string response or an instance of output_format
		"""

		openai_messages = OpenAIMessageSerializer.serialize_messages(messages)

		try:
			model_params: dict[str, Any] = {}

			if self.temperature is not None:
				model_params['temperature'] = self.temperature

			if self.frequency_penalty is not None:
				model_params['frequency_penalty'] = self.frequency_penalty

			if self.max_completion_tokens is not None:
				model_params['max_completion_tokens'] = self.max_completion_tokens

			if self.top_p is not None:
				model_params['top_p'] = self.top_p

			if self.seed is not None:
				model_params['seed'] = self.seed

			if self.service_tier is not None:
				model_params['service_tier'] = self.service_tier

			if self.reasoning_models and any(str(m).lower() in str(self.model).lower() for m in self.reasoning_models):
				model_params['reasoning_effort'] = self.reasoning_effort
				del model_params['temperature']
				del model_params['frequency_penalty']

			if output_format is None:
				# Return string response
				response = await self.get_client().chat.completions.create(
					model=self.model,
					messages=openai_messages,
					**model_params,
				)

				usage = self._get_usage(response)
				return ChatInvokeCompletion(
					completion=response.choices[0].message.content or '',
					usage=usage,
				)

			elif self.response_api:
				# Extract system message as instructions and user messages as input
				system_messages = [msg for msg in messages if msg.role == 'system']
				user_messages = [msg for msg in messages if msg.role != 'system']

				# Use instructions for system prompt, input for conversation
				instructions = system_messages[0].text if system_messages else None

				# Convert messages to proper ResponseInputParam format with multi-modal support
				input_items: list[EasyInputMessageParam] = []
				for message in user_messages:
					# Check if message has multi-modal content (images + text)
					if hasattr(message, 'content') and isinstance(message.content, list):
						# Multi-modal message with content parts
						content_items: list[ResponseInputContentParam] = []

						# Process each content part
						for part in message.content:
							if hasattr(part, 'type'):
								if part.type == 'text':
									# Text content
									text_item: ResponseInputTextParam = {
										'type': 'input_text',
										'text': part.text,
									}
									content_items.append(text_item)
								elif part.type == 'image_url':
									# Image content
									image_item: ResponseInputImageParam = {
										'type': 'input_image',
										'detail': getattr(part.image_url, 'detail', 'auto'),
									}
									# Add image URL
									if hasattr(part.image_url, 'url'):
										image_item['image_url'] = part.image_url.url

									content_items.append(image_item)

						content_list: ResponseInputMessageContentListParam = cast(
							ResponseInputMessageContentListParam, content_items
						)
						input_items.append(
							{
								'role': message.role,  # type: ignore
								'content': content_list,
								'type': 'message',
							}
						)
					else:
						# Text-only message
						text_content = message.text if hasattr(message, 'text') else str(message.content)
						input_items.append(
							{
								'role': message.role,  # type: ignore
								'content': text_content,
								'type': 'message',
							}
						)

				input_param: ResponseInputParam = cast(ResponseInputParam, input_items)

				# Create function tools - flatten AgentOutput into separate tools for each action
				tools: list[ToolParam] = []
				if output_format and hasattr(output_format, 'model_json_schema'):
					# Check if this is AgentOutput - if so, flatten into individual action tools
					if 'action' in output_format.model_json_schema().get('properties', {}):
						# This is AgentOutput - flatten into individual action tools
						tools = self._create_flattened_action_tools(output_format)
					else:
						# Regular schema - create single tool
						tool_name = output_format.__name__
						schema = SchemaOptimizer.create_optimized_json_schema(output_format)

						# Remove title from schema if present
						if 'title' in schema:
							del schema['title']

						# Create function tool from schema
						schema_tool: FunctionToolParam = {
							'type': 'function',
							'name': tool_name,
							'description': f'Extract or generate information in the format of {tool_name}',
							'parameters': {
								**schema,
								'additionalProperties': False,  # Required by Response API
							},
							'strict': True,
						}
						tools.append(schema_tool)

				# Prepare model parameters - GPT-5 Mini only supports default temperature
				model_params = {
					'model': self.model,
					'instructions': instructions,
					'input': input_param,
					'tools': tools,
					'tool_choice': 'auto' if output_format else 'auto',
					'parallel_tool_calls': True,  # Allow multiple tool calls
					'text': {'format': {'type': 'text'}},
					'max_output_tokens': self.max_completion_tokens,
				}

				# Only add temperature if it's not the default (GPT-5 Mini constraint)
				if self.temperature is not None and self.temperature != 1.0:
					# For GPT-5 Mini, only default temperature (1) is supported
					if 'gpt-5' not in str(self.model).lower():
						model_params['temperature'] = self.temperature

				response: Response = await self.get_client().responses.create(**model_params)

				usage = self._get_usage_from_response(response)

				# Handle structured output from Response API
				if output_format and tools:
					# Check if this is AgentOutput that was flattened into individual action tools
					if 'action' in output_format.model_json_schema().get('properties', {}):
						# This is AgentOutput - reconstruct from multiple function calls
						reconstructed_output = self._reconstruct_agent_output_from_function_calls(response, output_format)
						return ChatInvokeCompletion(
							completion=reconstructed_output,
							usage=usage,
						)
					else:
						# Regular schema - look for single function call
						for item in response.output:
							if hasattr(item, 'type') and getattr(item, 'type') == 'function_call':
								if hasattr(item, 'function') and item.function.name == output_format.__name__:
									# Parse function call result into structured output
									import json

									try:
										args = json.loads(item.function.arguments)
										parsed_output = output_format.model_validate(args)
										return ChatInvokeCompletion(
											completion=parsed_output,
											usage=usage,
										)
									except Exception as e:
										# If validation fails, raise proper error
										raise ModelProviderError(
											message=f'Failed to parse structured output from Response API: {e}. Raw args: {item.function.arguments}',
											status_code=500,
											model=self.name,
										) from e

						# If no function call found for regular schema
						raise ModelProviderError(
							message='Expected function call in Response API output but none found for structured output',
							status_code=500,
							model=self.name,
						)

				# Extract content from Response API - different structure than chat completions
				content = ''
				try:
					if hasattr(response, 'output') and response.output:
						# Response API has 'output' field with list of ResponseOutputItem
						if isinstance(response.output, list) and len(response.output) > 0:
							# Look for message items first
							for item in response.output:
								if hasattr(item, 'type') and getattr(item, 'type', None) == 'message':
									if hasattr(item, 'content'):
										content_attr = getattr(item, 'content', None)
										if isinstance(content_attr, list):
											content_parts = []
											for part in content_attr:
												if hasattr(part, 'text'):
													content_parts.append(str(getattr(part, 'text')))
												else:
													content_parts.append(str(part))
											content = ' '.join(content_parts)
										else:
											content = str(content_attr)
										break
							if not content:
								# No message found, try first item
								content = str(response.output[0])
						else:
							content = str(response.output)
					else:
						content = str(response)
				except Exception as e:
					# Fallback with proper error
					raise ModelProviderError(
						message=f'Failed to parse Response API output: {e}. Raw response: {str(response)[:500]}',
						status_code=500,
						model=self.name,
					) from e

				# If we get here with output_format, something went wrong
				if output_format:
					raise ModelProviderError(
						message=f'Response API did not return structured output as expected. Got content: {content[:200]}',
						status_code=500,
						model=self.name,
					)

				return ChatInvokeCompletion(
					completion=content,
					usage=usage,
				)

			else:
				response_format: JSONSchema = {
					'name': 'agent_output',
					'strict': False,
					'schema': output_format.model_json_schema(),
				}

				old = SchemaOptimizer.create_optimized_json_schema(output_format)

				# Add JSON schema to system prompt if requested
				if self.add_schema_to_system_prompt and openai_messages and openai_messages[0]['role'] == 'system':
					schema_text = f'\n<json_schema>\n{response_format}\n</json_schema>'
					if isinstance(openai_messages[0]['content'], str):
						openai_messages[0]['content'] += schema_text
					elif isinstance(openai_messages[0]['content'], Iterable):
						openai_messages[0]['content'] = list(openai_messages[0]['content']) + [
							ChatCompletionContentPartTextParam(text=schema_text, type='text')
						]

				# Return structured response
				response: ChatCompletion = await self.get_client().chat.completions.create(
					model=self.model,
					messages=openai_messages,
					response_format=ResponseFormatJSONSchema(json_schema=response_format, type='json_schema'),
					**model_params,
				)

				if response.choices[0].message.content is None:
					raise ModelProviderError(
						message='Failed to parse structured output from model response',
						status_code=500,
						model=self.name,
					)

				usage = self._get_usage(response)

				parsed = output_format.model_validate_json(response.choices[0].message.content)

				return ChatInvokeCompletion(
					completion=parsed,
					usage=usage,
				)

		except RateLimitError as e:
			error_message = e.response.json().get('error', {})
			error_message = (
				error_message.get('message', 'Unknown model error') if isinstance(error_message, dict) else error_message
			)
			raise ModelProviderError(
				message=error_message,
				status_code=e.response.status_code,
				model=self.name,
			) from e

		except APIConnectionError as e:
			raise ModelProviderError(message=str(e), model=self.name) from e

		except APIStatusError as e:
			try:
				error_message = e.response.json().get('error', {})
			except Exception:
				error_message = e.response.text
			error_message = (
				error_message.get('message', 'Unknown model error') if isinstance(error_message, dict) else error_message
			)
			raise ModelProviderError(
				message=error_message,
				status_code=e.response.status_code,
				model=self.name,
			) from e

		except Exception as e:
			raise ModelProviderError(message=str(e), model=self.name) from e

	def _create_flattened_action_tools(self, output_format: type[BaseModel]) -> list[ToolParam]:
		"""Create separate function tools for each action type instead of one large AgentOutput schema"""
		tools: list[ToolParam] = []

		# Get the schema from AgentOutput
		schema = output_format.model_json_schema()

		# Look for action models in $defs (e.g., DoneActionModel, ClickElementActionModel, etc.)
		defs = schema.get('$defs', {})

		for def_name, def_schema in defs.items():
			# Look for action models (they end with 'ActionModel')
			if def_name.endswith('ActionModel') and 'properties' in def_schema:
				# Extract the action name and parameters from the action model
				for action_name, action_ref in def_schema['properties'].items():
					# Get the actual action schema from the reference
					if '$ref' in action_ref:
						# Extract reference name (e.g., '#/$defs/DoneAction' -> 'DoneAction')
						ref_name = action_ref['$ref'].split('/')[-1]
						if ref_name in defs:
							action_schema = defs[ref_name]

							# Create individual tool for this action
							# Clean up the schema for Response API strict requirements
							properties = action_schema.get('properties', {})
							required_fields = action_schema.get('required', [])

							# For Response API strict mode, we need to handle optional fields properly
							# Remove properties that have defaults and aren't required
							clean_properties = {}
							for prop_name, prop_def in properties.items():
								if prop_name in required_fields:
									# Required field - include as is but remove defaults
									clean_prop = dict(prop_def)
									if 'default' in clean_prop:
										del clean_prop['default']
									clean_properties[prop_name] = clean_prop
								elif 'default' not in prop_def:
									# Optional field without default - make it required for strict mode
									clean_properties[prop_name] = prop_def
									required_fields.append(prop_name)
								# Skip fields with defaults that aren't required (like files_to_display)

							tool: FunctionToolParam = {
								'type': 'function',
								'name': action_name,
								'description': action_ref.get('description', f'Execute {action_name} action'),
								'parameters': {
									'type': 'object',
									'properties': clean_properties,
									'required': required_fields,
									'additionalProperties': False,
								},
								'strict': True,
							}
							tools.append(tool)

		return tools

	def _reconstruct_agent_output_from_function_calls(self, response: Response, output_format: type[BaseModel]) -> Any:
		"""Reconstruct AgentOutput from multiple function calls in response.output"""
		import json

		output_text = ''

		# Collect all function calls (skip reasoning blocks)
		function_calls = []
		for item in response.output:
			item_type = getattr(item, 'type', 'unknown')
			if item_type == 'function_call' and hasattr(item, 'name') and hasattr(item, 'arguments'):
				function_calls.append(item)
			elif item_type == 'message':
				try:
					output_text += item.content[0].text
				except Exception:
					pass

		if not function_calls:
			raise ModelProviderError(
				message='No function calls found in Response API output for AgentOutput reconstruction',
				status_code=500,
				model=self.name,
			)

		# Reconstruct the actions list from individual function calls
		# Each action needs to be in the exact format that the ActionModel Union expects
		actions = []
		for func_call in function_calls:
			action_name = func_call.name  # Direct attribute, not func_call.function.name
			args_str = func_call.arguments  # Direct attribute, not func_call.function.arguments
			args = json.loads(args_str)

			# Create action object in the format expected by ActionModel Union
			# The ActionModel is a Union of different action types, each with a single field
			action_obj = {action_name: args}
			actions.append(action_obj)

		# Construct AgentOutput with empty memory as requested
		agent_output_data = {
			'evaluation_previous_goal': '',  # Can be empty for Response API
			'memory': output_text,  # Set to empty string as requested
			'next_goal': '',  # Can be empty for Response API
			'action': actions,
		}

		# Add thinking if present in schema
		if 'thinking' in output_format.model_json_schema().get('properties', {}):
			agent_output_data['thinking'] = None

		try:
			# Use the output_format class directly instead of model_validate with dict
			if hasattr(output_format, 'model_validate'):
				return output_format.model_validate(agent_output_data)
			else:
				# Fallback construction
				return output_format(**agent_output_data)
		except Exception as e:
			# Enhanced error reporting
			error_details = f"""
Failed to reconstruct AgentOutput from function calls.
Function calls found: {len(function_calls)}
Actions created: {actions}
AgentOutput data: {agent_output_data}
Error: {e}
			""".strip()
			raise ModelProviderError(
				message=error_details,
				status_code=500,
				model=self.name,
			) from e
