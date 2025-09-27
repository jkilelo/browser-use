import asyncio
import json
import logging
import time
from dataclasses import dataclass
from typing import Any, Literal, TypeVar, overload

from google import genai
from google.auth.credentials import Credentials
from google.genai import types
from google.genai.types import MediaModality
from pydantic import BaseModel

from browser_use.llm.base import BaseChatModel
from browser_use.llm.exceptions import ModelProviderError
from browser_use.llm.google.serializer import GoogleMessageSerializer
from browser_use.llm.messages import BaseMessage
from browser_use.llm.schema import SchemaOptimizer
from browser_use.llm.views import ChatInvokeCompletion, ChatInvokeUsage

T = TypeVar('T', bound=BaseModel)


VerifiedGeminiModels = Literal[
	'gemini-2.0-flash',
	'gemini-2.0-flash-exp',
	'gemini-2.0-flash-lite-preview-02-05',
	'Gemini-2.0-exp',
	'gemini-2.5-flash',
	'gemini-2.5-flash-lite',
	'gemini-flash-latest',
	'gemini-flash-lite-latest',
	'gemini-2.5-pro',
	'gemma-3-27b-it',
	'gemma-3-4b',
	'gemma-3-12b',
	'gemma-3n-e2b',
	'gemma-3n-e4b',
]


@dataclass
class ChatGoogle(BaseChatModel):
	"""
	A wrapper around Google's Gemini chat model using the genai client.

	This class accepts all genai.Client parameters while adding model,
	temperature, and config parameters for the LLM interface.

	Args:
		model: The Gemini model to use
		temperature: Temperature for response generation
		config: Additional configuration parameters to pass to generate_content
			(e.g., tools, safety_settings, etc.).
		google_search: If True, enables Google Search grounding tool
		api_key: Google API key
		vertexai: Whether to use Vertex AI
		credentials: Google credentials object
		project: Google Cloud project ID
		location: Google Cloud location
		http_options: HTTP options for the client
		include_system_in_user: If True, system messages are included in the first user message
		supports_structured_output: If True, uses native JSON mode; if False, uses prompt-based fallback

	Example:
		from google.genai import types

		# With Google Search grounding
		llm = ChatGoogle(
			model='gemini-2.5-flash',
			google_search=True
		)

		# With custom tools
		llm = ChatGoogle(
			model='gemini-2.0-flash-exp',
			config={
				'tools': [types.Tool(code_execution=types.ToolCodeExecution())]
			}
		)
	"""

	# Model configuration
	model: VerifiedGeminiModels | str
	temperature: float | None = 0.2
	top_p: float | None = None
	seed: int | None = None
	thinking_budget: int | None = None  # for gemini-2.5 flash and flash-lite models, default will be set to 0
	max_output_tokens: int | None = 8192
	config: types.GenerateContentConfigDict | None = None
	google_search: bool = True  # Enable Google Search grounding
	include_system_in_user: bool = False
	supports_structured_output: bool = True  # New flag

	# Client initialization parameters
	api_key: str | None = None
	vertexai: bool | None = None
	credentials: Credentials | None = None
	project: str | None = None
	location: str | None = None
	http_options: types.HttpOptions | types.HttpOptionsDict | None = None

	# Internal client cache to prevent connection issues
	_client: genai.Client | None = None

	# Static
	@property
	def provider(self) -> str:
		return 'google'

	@property
	def logger(self) -> logging.Logger:
		"""Get logger for this chat instance"""
		return logging.getLogger(f'browser_use.llm.google.{self.model}')

	def _get_client_params(self) -> dict[str, Any]:
		"""Prepare client parameters dictionary."""
		# Define base client params
		base_params = {
			'api_key': self.api_key,
			'vertexai': self.vertexai,
			'credentials': self.credentials,
			'project': self.project,
			'location': self.location,
			'http_options': self.http_options,
		}

		# Create client_params dict with non-None values
		client_params = {k: v for k, v in base_params.items() if v is not None}

		return client_params

	def get_client(self) -> genai.Client:
		"""
		Returns a genai.Client instance.

		Returns:
			genai.Client: An instance of the Google genai client.
		"""
		if self._client is not None:
			return self._client

		client_params = self._get_client_params()
		self._client = genai.Client(**client_params)
		return self._client

	@property
	def name(self) -> str:
		return str(self.model)

	def _get_usage(self, response: types.GenerateContentResponse) -> ChatInvokeUsage | None:
		usage: ChatInvokeUsage | None = None

		if response.usage_metadata is not None:
			image_tokens = 0
			if response.usage_metadata.prompt_tokens_details is not None:
				image_tokens = sum(
					detail.token_count or 0
					for detail in response.usage_metadata.prompt_tokens_details
					if detail.modality == MediaModality.IMAGE
				)

			usage = ChatInvokeUsage(
				prompt_tokens=response.usage_metadata.prompt_token_count or 0,
				completion_tokens=(response.usage_metadata.candidates_token_count or 0)
				+ (response.usage_metadata.thoughts_token_count or 0),
				total_tokens=response.usage_metadata.total_token_count or 0,
				prompt_cached_tokens=response.usage_metadata.cached_content_token_count,
				prompt_cache_creation_tokens=None,
				prompt_image_tokens=image_tokens,
			)

		return usage

	def _get_grounding_metadata(self, response: types.GenerateContentResponse) -> str | None:
		"""Extract grounding metadata from the response as a formatted string."""

		# First check if we have any candidates
		if not response.candidates:
			self.logger.debug('🔍 No candidates in response')
			return None

		candidate = response.candidates[0]
		if not candidate.grounding_metadata:
			self.logger.debug('🔍 No grounding_metadata in candidate')
			return None

		grounding = candidate.grounding_metadata
		metadata_parts = []

		# Log all available fields for debugging
		self.logger.debug(f'🔍 Grounding object type: {type(grounding)}')
		if hasattr(grounding, '__dict__'):
			self.logger.debug(f'🔍 Grounding fields: {list(grounding.__dict__.keys())}')

		# Try to get all attributes from the grounding object
		attrs = dir(grounding)
		non_private_attrs = [attr for attr in attrs if not attr.startswith('_')]
		self.logger.debug(f'🔍 Available attributes: {non_private_attrs}')

		# Check all possible fields
		for attr in [
			'grounding_chunks',
			'grounding_supports',
			'web_search_queries',
			'retrieval_queries',
			'search_entry_point',
			'retrieval_metadata',
		]:
			if hasattr(grounding, attr):
				value = getattr(grounding, attr)
				self.logger.debug(f'🔍 {attr}: {value}')

		# Extract grounding chunks
		if hasattr(grounding, 'grounding_chunks') and grounding.grounding_chunks:
			metadata_parts.append(f'Grounding Sources ({len(grounding.grounding_chunks)} sources):')
			for i, chunk in enumerate(grounding.grounding_chunks, 1):
				if hasattr(chunk, 'web') and chunk.web:
					metadata_parts.append(f'  {i}. {chunk.web.title} - {chunk.web.uri}')

		# Extract grounding supports
		if hasattr(grounding, 'grounding_supports') and grounding.grounding_supports:
			metadata_parts.append(f'Grounded Segments ({len(grounding.grounding_supports)} segments):')
			for i, support in enumerate(grounding.grounding_supports, 1):
				if hasattr(support, 'segment') and support.segment:
					# Clean up the segment text - avoid JSON artifacts
					segment_text = support.segment.text
					if segment_text and not ('{' in segment_text and '}' in segment_text and '"' in segment_text):
						metadata_parts.append(f'  {i}. "{segment_text}"')
						if hasattr(support, 'grounding_chunk_indices') and support.grounding_chunk_indices:
							metadata_parts.append(f'     Sources: {support.grounding_chunk_indices}')

		# Extract search queries
		if hasattr(grounding, 'web_search_queries') and grounding.web_search_queries:
			metadata_parts.append(f'Search Queries: {", ".join(grounding.web_search_queries)}')

		if hasattr(grounding, 'retrieval_queries') and grounding.retrieval_queries:
			metadata_parts.append(f'Retrieval Queries: {", ".join(grounding.retrieval_queries)}')

		# Search entry point
		if hasattr(grounding, 'search_entry_point') and grounding.search_entry_point:
			metadata_parts.append('Search Entry Point: Available')

		# If no standard grounding data, try to extract from the full response
		if not metadata_parts:
			# Check if there's any indication of search/grounding in the response
			if hasattr(response, 'usage_metadata') and response.usage_metadata:
				if (
					hasattr(response.usage_metadata, 'tool_use_prompt_token_count')
					and response.usage_metadata.tool_use_prompt_token_count
				):
					metadata_parts.append(
						f'Google Search grounding used (tool tokens: {response.usage_metadata.tool_use_prompt_token_count})'
					)

			# Check if the response text contains indicators of current information
			if hasattr(response, 'candidates') and response.candidates:
				text = response.candidates[0].content.parts[0].text if response.candidates[0].content.parts else ''
				if any(indicator in text.lower() for indicator in ['current', 'today', 'latest', 'now', 'recent', 'as of']):
					metadata_parts.append('')

		result = '\n'.join(metadata_parts) if metadata_parts else None
		self.logger.debug(f'🔍 Final grounding metadata: {result}')
		return result

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

		# Serialize messages to Google format with the include_system_in_user flag
		contents, system_instruction = GoogleMessageSerializer.serialize_messages(
			messages, include_system_in_user=self.include_system_in_user
		)

		# Build config dictionary starting with user-provided config
		config: types.GenerateContentConfigDict = {}
		if self.config:
			config = self.config.copy()

		# Add Google Search grounding tool if enabled
		if self.google_search:
			grounding_tool = types.Tool(google_search=types.GoogleSearch())
			existing_tools = config.get('tools', [])
			config['tools'] = existing_tools + [grounding_tool]

		# Apply model-specific configuration (these can override config)
		if self.temperature is not None:
			config['temperature'] = self.temperature

		# Add system instruction if present
		if system_instruction:
			config['system_instruction'] = system_instruction

		if self.top_p is not None:
			config['top_p'] = self.top_p

		if self.seed is not None:
			config['seed'] = self.seed

		# set default for flash, flash-lite, gemini-flash-lite-latest, and gemini-flash-latest models
		if self.thinking_budget is None and ('gemini-2.5-flash' in self.model or 'gemini-flash' in self.model):
			self.thinking_budget = 0

		if self.thinking_budget is not None:
			thinking_config_dict: types.ThinkingConfigDict = {'thinking_budget': self.thinking_budget}
			config['thinking_config'] = thinking_config_dict

		if self.max_output_tokens is not None:
			config['max_output_tokens'] = self.max_output_tokens

		async def _make_api_call():
			start_time = time.time()
			self.logger.debug(f'🚀 Starting API call to {self.model}')

			try:
				if output_format is None:
					# Return string response
					self.logger.debug('📄 Requesting text response')

					response = await self.get_client().aio.models.generate_content(
						model=self.model,
						contents=contents,  # type: ignore
						config=config,
					)

					elapsed = time.time() - start_time
					self.logger.debug(f'✅ Got text response in {elapsed:.2f}s')

					# Handle case where response.text might be None
					text = response.text or ''
					if not text:
						self.logger.warning('⚠️ Empty text response received')

					usage = self._get_usage(response)
					grounding_metadata = self._get_grounding_metadata(response)

					return ChatInvokeCompletion(
						completion=text,
						usage=usage,
						grounding_metadata=grounding_metadata,
					)

				else:
					# Handle structured output
					if self.supports_structured_output:
						# Check if tools are present - Google API doesn't support tools + JSON mode
						has_tools = config.get('tools') and len(config.get('tools', [])) > 0

						if has_tools:
							# Fallback to prompt-based JSON when tools are present
							self.logger.debug(f'🔄 Using prompt-based JSON mode for {output_format.__name__} (tools present)')
							# Don't set response_mime_type when tools are present
						else:
							# Use native JSON mode when no tools
							self.logger.debug(f'🔧 Requesting structured output for {output_format.__name__}')
							config['response_mime_type'] = 'application/json'
							# Convert Pydantic model to Gemini-compatible schema
							optimized_schema = SchemaOptimizer.create_optimized_json_schema(output_format)

							gemini_schema = self._fix_gemini_schema(optimized_schema)
							config['response_schema'] = gemini_schema

						if has_tools:
							# When tools are present, use prompt-based approach
							# Create a copy of messages to modify
							modified_messages = [m.model_copy(deep=True) for m in messages]

							# Add JSON instruction to the last message
							if modified_messages and isinstance(modified_messages[-1].content, str):
								json_instruction = f'\n\nPlease respond with a valid JSON object that matches this schema: {SchemaOptimizer.create_optimized_json_schema(output_format)}'
								modified_messages[-1].content += json_instruction

							# Re-serialize with modified messages
							tools_contents, tools_system = GoogleMessageSerializer.serialize_messages(
								modified_messages, include_system_in_user=self.include_system_in_user
							)

							# Update config with system instruction if present
							tools_config = config.copy()
							if tools_system:
								tools_config['system_instruction'] = tools_system

							response = await self.get_client().aio.models.generate_content(
								model=self.model,
								contents=tools_contents,  # type: ignore
								config=tools_config,
							)
						else:
							# Native JSON mode without tools
							response = await self.get_client().aio.models.generate_content(
								model=self.model,
								contents=contents,
								config=config,
							)

						elapsed = time.time() - start_time
						self.logger.debug(f'✅ Got structured response in {elapsed:.2f}s')

						usage = self._get_usage(response)
						grounding_metadata = self._get_grounding_metadata(response)

						# Handle JSON parsing for both native and prompt-based approaches
						if response.parsed is None or has_tools:
							self.logger.debug('📝 Parsing JSON from text response')
							# Parse JSON from text (used for both tools+JSON and native JSON fallback)
							if response.text:
								try:
									text = response.text.strip()

									# Look for JSON in the text - handle various formats
									json_text = None

									# Method 1: Look for ```json blocks
									if '```json' in text:
										json_start = text.find('```json') + 7
										json_end = text.find('```', json_start)
										if json_end != -1:
											json_text = text[json_start:json_end].strip()
											self.logger.debug('🔧 Extracted from ```json``` block')

									# Method 2: Look for ``` blocks containing JSON
									elif '```' in text and '{' in text:
										json_start = text.find('```') + 3
										json_end = text.find('```', json_start)
										if json_end != -1:
											potential_json = text[json_start:json_end].strip()
											if potential_json.startswith('{') or potential_json.startswith('"'):
												json_text = potential_json
												self.logger.debug('🔧 Extracted from ``` block')

									# Method 3: Look for JSON object boundaries
									if json_text is None:
										json_start = text.find('{')
										if json_start != -1:
											# Find the matching closing brace
											brace_count = 0
											for i in range(json_start, len(text)):
												if text[i] == '{':
													brace_count += 1
												elif text[i] == '}':
													brace_count -= 1
													if brace_count == 0:
														json_text = text[json_start : i + 1].strip()
														self.logger.debug(
															f'🔧 Extracted JSON object from position {json_start}:{i + 1}'
														)
														break

									# Method 4: Handle malformed JSON - try to reconstruct
									if json_text is None:
										# Look for field patterns that indicate JSON content
										field_patterns = ['evaluation_previous_goal', 'memory', 'next_goal', 'action', 'thinking']

										# Find any field pattern in the text
										for field in field_patterns:
											# Pattern: field": "value" (missing opening quote and brace)
											pattern1 = f'{field}": "'
											# Pattern: "field": "value" (proper format)
											pattern2 = f'"{field}": "'

											if pattern1 in text and pattern2 not in text:
												self.logger.debug(f'🔧 Found malformed JSON starting with {field}')
												# Find the position and reconstruct
												start_pos = text.find(pattern1)
												if start_pos != -1:
													# Add the missing opening brace and quote
													json_text = '{' + '"' + text[start_pos:]
													# Clean up and ensure proper ending
													if not json_text.rstrip().endswith('}'):
														json_text = json_text.rstrip() + '}'
													self.logger.debug('🔧 Reconstructed malformed JSON')
													break
											elif pattern2 in text:
												# Standard format found, extract from this point
												start_pos = text.find(pattern2)
												if start_pos > 0:
													# Look backward for opening brace
													preceding = text[:start_pos].strip()
													if not preceding.endswith('{'):
														json_text = '{' + text[start_pos:]
													else:
														json_text = text[start_pos - 1 :]  # Include the brace
													self.logger.debug('🔧 Extracted JSON from field pattern')
													break

									# Fallback: use entire text
									if json_text is None:
										json_text = text
										self.logger.debug('🔧 Using entire text as JSON fallback')

									# Parse the JSON text and validate with the Pydantic model
									parsed_data = json.loads(json_text)
									return ChatInvokeCompletion(
										completion=output_format.model_validate(parsed_data),
										usage=usage,
										grounding_metadata=grounding_metadata,
									)
								except (json.JSONDecodeError, ValueError) as e:
									self.logger.error(f'❌ Failed to parse JSON response: {str(e)}')
									self.logger.debug(f'Raw response text: {response.text[:500]}...')
									raise ModelProviderError(
										message=f'Failed to parse or validate response {response}: {str(e)}',
										status_code=500,
										model=self.model,
									) from e
							else:
								self.logger.error('❌ No response text received')
								raise ModelProviderError(
									message=f'No response from model {response}',
									status_code=500,
									model=self.model,
								)

						# Ensure we return the correct type
						if isinstance(response.parsed, output_format):
							return ChatInvokeCompletion(
								completion=response.parsed,
								usage=usage,
								grounding_metadata=grounding_metadata,
							)
						else:
							# If it's not the expected type, try to validate it
							return ChatInvokeCompletion(
								completion=output_format.model_validate(response.parsed),
								usage=usage,
								grounding_metadata=grounding_metadata,
							)
					else:
						# Fallback: Request JSON in the prompt for models without native JSON mode
						self.logger.debug(f'🔄 Using fallback JSON mode for {output_format.__name__}')
						# Create a copy of messages to modify
						modified_messages = [m.model_copy(deep=True) for m in messages]

						# Add JSON instruction to the last message
						if modified_messages and isinstance(modified_messages[-1].content, str):
							json_instruction = f'\n\nPlease respond with a valid JSON object that matches this schema: {SchemaOptimizer.create_optimized_json_schema(output_format)}'
							modified_messages[-1].content += json_instruction

						# Re-serialize with modified messages
						fallback_contents, fallback_system = GoogleMessageSerializer.serialize_messages(
							modified_messages, include_system_in_user=self.include_system_in_user
						)

						# Update config with fallback system instruction if present
						fallback_config = config.copy()
						if fallback_system:
							fallback_config['system_instruction'] = fallback_system

						response = await self.get_client().aio.models.generate_content(
							model=self.model,
							contents=fallback_contents,  # type: ignore
							config=fallback_config,
						)

						elapsed = time.time() - start_time
						self.logger.debug(f'✅ Got fallback response in {elapsed:.2f}s')

						usage = self._get_usage(response)

						# Try to extract JSON from the text response
						if response.text:
							try:
								# Try to find JSON in the response
								text = response.text.strip()

								# Common patterns: JSON wrapped in markdown code blocks
								if text.startswith('```json') and text.endswith('```'):
									text = text[7:-3].strip()
								elif text.startswith('```') and text.endswith('```'):
									text = text[3:-3].strip()

								# Parse and validate
								parsed_data = json.loads(text)
								return ChatInvokeCompletion(
									completion=output_format.model_validate(parsed_data),
									usage=usage,
									grounding_metadata=grounding_metadata,
								)
							except (json.JSONDecodeError, ValueError) as e:
								self.logger.error(f'❌ Failed to parse fallback JSON: {str(e)}')
								self.logger.debug(f'Raw response text: {response.text[:200]}...')
								raise ModelProviderError(
									message=f'Model does not support JSON mode and failed to parse JSON from text response: {str(e)}',
									status_code=500,
									model=self.model,
								) from e
						else:
							self.logger.error('❌ No response text in fallback mode')
							raise ModelProviderError(
								message='No response from model',
								status_code=500,
								model=self.model,
							)
			except Exception as e:
				elapsed = time.time() - start_time
				self.logger.error(f'💥 API call failed after {elapsed:.2f}s: {type(e).__name__}: {e}')
				# Re-raise the exception
				raise

		try:
			# Let Google client handle retries internally with proper connection management
			self.logger.debug(f'🔄 Making API call to {self.model} (using built-in retry)')
			return await _make_api_call()

		except Exception as e:
			# Handle specific Google API errors with enhanced diagnostics
			error_message = str(e)
			status_code: int | None = None

			# Enhanced timeout error handling
			if 'timeout' in error_message.lower() or 'cancelled' in error_message.lower():
				if isinstance(e, asyncio.CancelledError) or 'CancelledError' in str(type(e)):
					enhanced_message = 'Gemini API request was cancelled (likely timeout). '
					enhanced_message += 'This suggests the API is taking too long to respond. '
					enhanced_message += (
						'Consider: 1) Reducing input size, 2) Using a different model, 3) Checking network connectivity.'
					)
					error_message = enhanced_message
					status_code = 504  # Gateway timeout
					self.logger.error(f'🕐 Timeout diagnosis: Model: {self.model}')
				else:
					status_code = 408  # Request timeout
			# Check if this is a rate limit error
			elif any(
				indicator in error_message.lower()
				for indicator in ['rate limit', 'resource exhausted', 'quota exceeded', 'too many requests', '429']
			):
				status_code = 429
			elif any(
				indicator in error_message.lower()
				for indicator in ['service unavailable', 'internal server error', 'bad gateway', '503', '502', '500']
			):
				status_code = 503

			# Try to extract status code if available
			if hasattr(e, 'response'):
				response_obj = getattr(e, 'response', None)
				if response_obj and hasattr(response_obj, 'status_code'):
					status_code = getattr(response_obj, 'status_code', None)

			raise ModelProviderError(
				message=error_message,
				status_code=status_code or 502,  # Use default if None
				model=self.name,
			) from e

	def _fix_gemini_schema(self, schema: dict[str, Any]) -> dict[str, Any]:
		"""
		Convert a Pydantic model to a Gemini-compatible schema.

		This function removes unsupported properties like 'additionalProperties' and resolves
		$ref references that Gemini doesn't support.
		"""

		# Handle $defs and $ref resolution
		if '$defs' in schema:
			defs = schema.pop('$defs')

			def resolve_refs(obj: Any) -> Any:
				if isinstance(obj, dict):
					if '$ref' in obj:
						ref = obj.pop('$ref')
						ref_name = ref.split('/')[-1]
						if ref_name in defs:
							# Replace the reference with the actual definition
							resolved = defs[ref_name].copy()
							# Merge any additional properties from the reference
							for key, value in obj.items():
								if key != '$ref':
									resolved[key] = value
							return resolve_refs(resolved)
						return obj
					else:
						# Recursively process all dictionary values
						return {k: resolve_refs(v) for k, v in obj.items()}
				elif isinstance(obj, list):
					return [resolve_refs(item) for item in obj]
				return obj

			schema = resolve_refs(schema)

		# Remove unsupported properties
		def clean_schema(obj: Any) -> Any:
			if isinstance(obj, dict):
				# Remove unsupported properties
				cleaned = {}
				for key, value in obj.items():
					if key not in ['additionalProperties', 'title', 'default']:
						cleaned_value = clean_schema(value)
						# Handle empty object properties - Gemini doesn't allow empty OBJECT types
						if (
							key == 'properties'
							and isinstance(cleaned_value, dict)
							and len(cleaned_value) == 0
							and isinstance(obj.get('type', ''), str)
							and obj.get('type', '').upper() == 'OBJECT'
						):
							# Convert empty object to have at least one property
							cleaned['properties'] = {'_placeholder': {'type': 'string'}}
						else:
							cleaned[key] = cleaned_value

				# If this is an object type with empty properties, add a placeholder
				if (
					isinstance(cleaned.get('type', ''), str)
					and cleaned.get('type', '').upper() == 'OBJECT'
					and 'properties' in cleaned
					and isinstance(cleaned['properties'], dict)
					and len(cleaned['properties']) == 0
				):
					cleaned['properties'] = {'_placeholder': {'type': 'string'}}

				# Also remove 'title' from the required list if it exists
				if 'required' in cleaned and isinstance(cleaned.get('required'), list):
					cleaned['required'] = [p for p in cleaned['required'] if p != 'title']

				return cleaned
			elif isinstance(obj, list):
				return [clean_schema(item) for item in obj]
			return obj

		return clean_schema(schema)
