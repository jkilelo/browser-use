"""ChatBrowserUse - A standalone wrapper around ChatGoogle with GatewayService logic.

This module provides a LangChain-compatible chat model that wraps ChatGoogle with
the unstructured output parsing and prompt formatting logic from GatewayService,
but without FastAPI or billing dependencies.

Usage:
    from chat_browser_use import ChatBrowserUse

    llm = ChatBrowserUse(api_key="your-google-api-key", fast=True)

    # Use like any BaseChatModel
    messages = [
        {"role": "system", "content": "You are a helpful assistant"},
        {"role": "user", "content": "Hello!"}
    ]

    response = await llm.ainvoke(
        messages=messages,
        output_format=schema,  # Optional: for structured output
    )
"""

import logging
import os
import re
from typing import Any, Optional

from browser_use.llm.base import BaseChatModel
from browser_use.llm.google.chat import ChatGoogle
from browser_use.llm.messages import (
	AssistantMessage,
	BaseMessage,
	SystemMessage,
	UserMessage,
)
from browser_use.llm.views import ChatInvokeCompletion, ChatInvokeUsage

logger = logging.getLogger(__name__)


class PricingConfig:
	"""Pricing configuration for token cost calculation"""

	def __init__(
		self,
		price_input_per_1m: float = 0.50,
		price_output_per_1m: float = 3.00,
		price_cached_per_1m: float = 0.10,
		model_fast: str = 'gemini-flash-lite-latest',
		model_smart: str = 'gemini-flash-latest',
	):
		self.price_input_per_1m = price_input_per_1m
		self.price_output_per_1m = price_output_per_1m
		self.price_cached_per_1m = price_cached_per_1m
		self.model_fast = model_fast
		self.model_smart = model_smart


class UnstructuredOutputParser:
	"""Parser for unstructured plain text output format"""

	@staticmethod
	def parse_with_schema(text: str, schema: dict[str, Any]) -> dict[str, Any]:
		"""Parse plain text output using a JSON schema directly."""
		# Extract memory section (optional - use empty string if not found)
		memory_match = re.search(r'<memory>(.*?)</memory>', text, re.DOTALL | re.IGNORECASE)
		if memory_match:
			memory = memory_match.group(1).strip()
			# Detect repetitive text (same sentence repeated many times)
			if len(memory) > 500:
				sentences = memory.split('. ')
				if len(sentences) > 10:
					# Check if most sentences are identical
					from collections import Counter

					sentence_counts = Counter(sentences)
					most_common = sentence_counts.most_common(1)[0]
					if most_common[1] > len(sentences) * 0.5:  # More than 50% identical
						memory = f'[Repetitive output detected] {most_common[0]}'
		else:
			# Allow missing memory section - use empty string
			memory = ''

		# Extract action section
		action_match = re.search(r'<action>(.*?)</action>', text, re.DOTALL | re.IGNORECASE)
		if not action_match:
			raise ValueError('No <action> section found in output')

		action_text = action_match.group(1).strip()

		# Parse actions using the schema
		actions, debug_info = UnstructuredOutputParser._parse_actions_from_schema(action_text, schema)

		if not actions:
			# Provide helpful debug info
			action_preview = action_text[:200] + ('...' if len(action_text) > 200 else '')
			error_msg = f'No valid actions parsed from action section. Action text preview: {action_preview}'
			if debug_info:
				error_msg += f'. Debug: {debug_info}'
			raise ValueError(error_msg)

		return {'memory': memory, 'action': actions}

	@staticmethod
	def _normalize_quotes(text: str) -> str:
		"""Normalize fancy/smart quotes to straight quotes.

		Converts fancy quotes (" " ' ') to straight quotes (" ').
		Does NOT auto-escape - LLM should escape quotes properly.
		"""
		# Replace all fancy quote variants with straight quotes
		text = text.replace('"', '"').replace('"', '"')  # Smart double quotes
		text = text.replace(""", "'").replace(""", "'")  # Smart single quotes
		return text

	@staticmethod
	def _parse_actions_from_schema(action_text: str, schema: dict[str, Any]) -> tuple[list[dict[str, Any]], str]:
		"""Parse action function calls from text using a schema dict."""
		# Normalize quotes before parsing
		action_text = UnstructuredOutputParser._normalize_quotes(action_text)

		actions = []

		# Extract action schemas from the schema dict
		action_schemas = {}

		if '$defs' not in schema:
			return [], 'No $defs in schema'

		# Extract all actions from ActionModel definitions
		for def_name, def_schema in schema['$defs'].items():
			if def_name.endswith('ActionModel') and 'properties' in def_schema:
				for prop_name, prop_schema in def_schema['properties'].items():
					# Store the action name and its parameter structure
					action_schemas[prop_name] = prop_schema

		# Parse function calls
		actions_parsed = []
		skipped_actions = []
		i = 0
		while i < len(action_text):
			# Skip whitespace
			while i < len(action_text) and action_text[i].isspace():
				i += 1
			if i >= len(action_text):
				break

			# Try to match an action name
			match = re.match(r'(\w+)\s*\(', action_text[i:])
			if not match:
				i += 1
				continue

			action_name = match.group(1)
			# Check if this is a valid action
			if action_name not in action_schemas:
				skipped_actions.append(action_name)
				i += match.end()
				continue

			# Find the opening parenthesis position
			paren_start = i + match.end() - 1

			# Count parentheses to find the matching closing parenthesis
			depth = 1
			j = paren_start + 1
			in_string = False
			string_char = None
			escape_next = False

			while j < len(action_text) and depth > 0:
				char = action_text[j]

				if escape_next:
					escape_next = False
					j += 1
					continue

				if char == '\\':
					escape_next = True
					j += 1
					continue

				if char in ('"', "'") and not in_string:
					in_string = True
					string_char = char
				elif char == string_char and in_string:
					in_string = False
					string_char = None
				elif char == '(' and not in_string:
					depth += 1
				elif char == ')' and not in_string:
					depth -= 1

				j += 1

			if depth == 0:
				# Found matching closing parenthesis
				args_str = action_text[paren_start + 1 : j - 1].strip()
				actions_parsed.append((action_name, args_str))
				i = j
			else:
				i += 1

		# Parse each action into a dict
		failed_actions = []
		for action_name, args_str in actions_parsed:
			try:
				action_schema = action_schemas[action_name]

				# Parse the arguments
				if args_str:
					params = UnstructuredOutputParser._parse_args_for_action(args_str, action_name, action_schema)
				else:
					params = {}

				# Create action dict: {action_name: params}
				actions.append({action_name: params})

			except (ValueError, Exception) as e:
				failed_actions.append((action_name, str(e)[:100]))
				continue

		# Build debug info
		debug_parts = []
		if skipped_actions:
			debug_parts.append(f'Skipped (not in schema): {", ".join(set(skipped_actions))}')
		if failed_actions:
			debug_parts.append(f'Failed to parse: {", ".join(f"{name}({err})" for name, err in failed_actions[:3])}')
		debug_info = '; '.join(debug_parts) if debug_parts else ''

		return actions, debug_info

	@staticmethod
	def _parse_args_for_action(args_str: str, _action_name: str, param_type: Any) -> dict[str, Any] | None:
		"""Parse function arguments for a specific action."""
		if not args_str:
			return None

		# Try to parse as JSON object first
		if args_str.strip().startswith('{'):
			try:
				import json

				return json.loads(args_str)
			except json.JSONDecodeError:
				# Try to handle object literal syntax
				try:
					import re

					fixed_str = args_str
					pattern = r'([,{]\s*)([a-zA-Z_]\w*)(\s*:)'
					fixed_str = re.sub(pattern, r'\1"\2"\3', fixed_str)
					if not fixed_str.strip().startswith('{'):
						fixed_str = '{' + fixed_str
					if not fixed_str.strip().endswith('}'):
						fixed_str = fixed_str + '}'
					pattern_start = r'^(\s*)([a-zA-Z_]\w*)(\s*:)'
					fixed_str = re.sub(pattern_start, r'\1"\2"\3', fixed_str)

					# Convert Python boolean literals to JSON
					fixed_str = re.sub(r':\s*True\b', ': true', fixed_str)
					fixed_str = re.sub(r':\s*False\b', ': false', fixed_str)
					fixed_str = re.sub(r':\s*None\b', ': null', fixed_str)

					return json.loads(fixed_str)
				except (json.JSONDecodeError, Exception):
					pass

		# Check if we have named arguments (key=value format)
		if '=' in args_str:
			# Parse as key=value pairs
			params = {}
			args_list = UnstructuredOutputParser._split_args(args_str)
			for arg in args_list:
				if '=' in arg:
					key, value = arg.split('=', 1)
					params[key.strip()] = UnstructuredOutputParser._parse_value(value.strip())
			return params if params else None

		# Otherwise parse as positional args and map to known param names
		args_list = UnstructuredOutputParser._split_args(args_str)

		# Extract parameter names from the schema
		param_names: list[str] = []
		if isinstance(param_type, dict):
			if 'properties' in param_type:
				param_names = list(param_type['properties'].keys())
			elif 'anyOf' in param_type:
				for option in param_type['anyOf']:
					if isinstance(option, dict) and 'properties' in option:
						param_names = list(option['properties'].keys())
						break

		params: dict[str, Any] = {}

		# Map positional arguments to parameter names
		for i, arg in enumerate(args_list):
			if i < len(param_names):
				param_name = param_names[i]
				params[param_name] = UnstructuredOutputParser._parse_value(arg.strip())
			else:
				# Extra args beyond expected
				params[f'arg_{i}'] = UnstructuredOutputParser._parse_value(arg.strip())

		return params if params else None

	@staticmethod
	def _split_args(args_str: str) -> list[str]:
		"""Split arguments by comma, respecting quotes and nesting.

		Handles escape sequences including backslash-escaped quotes.
		"""
		args = []
		current = []
		depth = 0
		in_quotes = False
		quote_char = None
		escape_next = False

		for char in args_str:
			if escape_next:
				# This character is escaped, add it literally
				current.append(char)
				escape_next = False
			elif char == '\\':
				# Start escape sequence
				current.append(char)
				escape_next = True
			elif char in ('"', "'") and (not in_quotes or char == quote_char):
				in_quotes = not in_quotes
				quote_char = char if in_quotes else None
				current.append(char)
			elif char in ('(', '[', '{') and not in_quotes:
				depth += 1
				current.append(char)
			elif char in (')', ']', '}') and not in_quotes:
				depth -= 1
				current.append(char)
			elif char == ',' and depth == 0 and not in_quotes:
				args.append(''.join(current).strip())
				current = []
			else:
				current.append(char)

		if current:
			args.append(''.join(current).strip())

		return args

	@staticmethod
	def _parse_value(value_str: str) -> Any:
		"""Parse a single value from string."""
		value_str = value_str.strip()

		# Handle arrays [...]
		if value_str.startswith('[') and value_str.endswith(']'):
			try:
				import json

				return json.loads(value_str)
			except json.JSONDecodeError:
				# Try parsing as simple list
				inner = value_str[1:-1].strip()
				if not inner:
					return []
				items = []
				for item in UnstructuredOutputParser._split_args(inner):
					items.append(UnstructuredOutputParser._parse_value(item))
				return items

		# Handle objects {...}
		if value_str.startswith('{') and value_str.endswith('}'):
			try:
				import json

				return json.loads(value_str)
			except json.JSONDecodeError:
				return value_str

		# Handle quoted strings
		if (value_str.startswith('"') and value_str.endswith('"')) or (value_str.startswith("'") and value_str.endswith("'")):
			return value_str[1:-1]

		# Handle booleans
		if value_str.lower() in ('true', '1', 'yes'):
			return True
		if value_str.lower() in ('false', '0', 'no'):
			return False

		# Handle None/null
		if value_str.lower() in ('none', 'null'):
			return None

		# Try integer
		try:
			return int(value_str)
		except ValueError:
			pass

		# Try float
		try:
			return float(value_str)
		except ValueError:
			pass

		# Return as string
		return value_str


class ChatBrowserUse(BaseChatModel):
	"""
	A wrapper around ChatGoogle that implements GatewayService logic without billing.

	This class provides the same functionality as GatewayService but as a standalone
	LangChain-compatible chat model that can be used directly in browser-use without
	FastAPI dependencies.

	Features:
	- Unstructured output parsing with <memory> and <action> tags
	- Automatic prompt formatting for structured outputs
	- Token usage tracking and cost calculation
	- Fast/smart model selection

	Args:
	    api_key: Google API key for Gemini models
	    fast: If True, use fast model, else smart model
	    pricing_config: Optional custom pricing configuration
	"""

	@property
	def provider(self) -> str:
		return 'browser-use'

	@property
	def name(self) -> str:
		return f'browser-use/{self.model}'

	def __init__(
		self,
		api_key: Optional[str] = None,
		g_api_key: Optional[str] = None,
		fast: bool = False,
		base_url: Optional[str] = None,
		pricing_config: Optional[PricingConfig] = None,
	):
		self.api_key = g_api_key or os.getenv('GOOGLE_API_KEY')
		if not self.api_key:
			raise ValueError('GOOGLE_API_KEY environment variable must be set')

		self.fast = fast
		self.pricing_config = pricing_config or PricingConfig()

		# Select model
		self.model = self.pricing_config.model_fast if fast else self.pricing_config.model_smart

		# Initialize underlying ChatGoogle instance
		self._llm = ChatGoogle(model=self.model, api_key=self.api_key)

	async def ainvoke(
		self,
		messages: list[dict[str, Any]] | list[BaseMessage],
		output_format: Optional[Any] = None,
	) -> ChatInvokeCompletion[Any]:
		"""
		Invoke the chat model with optional structured output.

		Args:
		    messages: List of message dicts or BaseMessage objects
		    output_format: Optional Pydantic model class for structured output

		Returns:
		    ChatInvokeCompletion object containing:
		        - completion: Parsed output (dict if output_format provided, else str)
		        - usage: Token usage information
		"""
		# Convert messages to BaseMessage objects if needed
		converted_messages = self._convert_messages(messages)

		# Convert output_format to JSON schema if it's a Pydantic model
		schema = None
		if output_format is not None:
			if hasattr(output_format, 'model_json_schema'):
				schema = output_format.model_json_schema()
			else:
				schema = output_format

		# Apply unstructured prompt if output_format is provided
		if schema is not None:
			converted_messages = self._apply_unstructured_prompt(converted_messages, schema)

		# Call the underlying LLM
		try:
			response = await self._llm.ainvoke(messages=converted_messages, output_format=None)
		except Exception as e:
			logger.error(f'LLM call failed: {e}', exc_info=True)
			raise ValueError(f'LLM call failed: {e}')

		# Parse the response if we have schema
		if schema is not None and output_format is not None:
			raw_text = response.completion
			try:
				parsed_dict = UnstructuredOutputParser.parse_with_schema(raw_text, schema)
				# Create an instance of the output_format model class using the parsed dictionary
				parsed_output = output_format.model_validate(parsed_dict)
				logger.info(f'Output parsed successfully: {list(parsed_dict.keys())}')
			except Exception as e:
				logger.error(f'Failed to parse output: {e}')
				raise ValueError(f'Failed to parse output: {e}')
		else:
			parsed_output = response.completion

		# Calculate cost using pricing config
		usage = response.usage or ChatInvokeUsage(
			prompt_tokens=0,
			prompt_cached_tokens=None,
			prompt_cache_creation_tokens=None,
			prompt_image_tokens=None,
			completion_tokens=0,
			total_tokens=0,
		)

		uncached_input_tokens = usage.prompt_tokens - (usage.prompt_cached_tokens or 0)
		input_cost_usd = (uncached_input_tokens / 1_000_000) * self.pricing_config.price_input_per_1m
		output_cost_usd = (usage.completion_tokens / 1_000_000) * self.pricing_config.price_output_per_1m
		cached_cost_usd = ((usage.prompt_cached_tokens or 0) / 1_000_000) * self.pricing_config.price_cached_per_1m

		total_cost_usd = input_cost_usd + output_cost_usd + cached_cost_usd

		logger.info(
			f'💰 Tokens: {uncached_input_tokens} input, {usage.completion_tokens} output, '
			f'{usage.prompt_cached_tokens or 0} cached | Cost: ${total_cost_usd:.4f}'
		)

		return ChatInvokeCompletion(
			completion=parsed_output,
			usage=usage,
		)

	def _convert_messages(self, messages: list[dict[str, Any]] | list[BaseMessage]) -> list[BaseMessage]:
		"""Convert dict messages to BaseMessage objects"""
		converted = []
		for msg in messages:
			if isinstance(msg, dict):
				role = msg.get('role')
				content = msg.get('content', '')
				if role == 'system' and content:
					converted.append(SystemMessage(content=content))
				elif role == 'user' and content:
					converted.append(UserMessage(content=content))
				elif role == 'assistant' and content:
					converted.append(AssistantMessage(content=content))
				else:
					converted.append(msg)
			else:
				converted.append(msg)
		return converted

	def _apply_unstructured_prompt(
		self,
		messages: list[BaseMessage],
		schema: dict[str, Any],
	) -> list[BaseMessage]:
		"""Apply unstructured prompt template to system message"""

		action_description = self._generate_action_descriptions(schema)

		# Get incoming system prompt and remove <output> section
		original_system_content = ''
		for msg in messages:
			if isinstance(msg, SystemMessage):
				# Handle both string and list content
				if isinstance(msg.content, str):
					original_system_content = msg.content
				elif isinstance(msg.content, list):
					# Join text parts if it's a list
					text_parts = []
					for part in msg.content:
						if isinstance(part, dict) and part.get('type') == 'text':
							text_parts.append(part.get('text', ''))
						elif isinstance(part, str):
							text_parts.append(part)
					original_system_content = '\n'.join(text_parts)
				break

		# Remove <output>...</output> section from incoming prompt
		system_without_output = re.sub(r'<output>.*?</output>', '', original_system_content, flags=re.DOTALL).strip()

		# Add unstructured output format and tools
		optimized_system_prompt = f"""{system_without_output}

<output>
Every response MUST include both <memory> and <action> sections in this format:

<memory>
Up to 5 sentences: Was previous step successful? What to remember from current state? What are the next actions? What's the immediate goal? Keep it concise unless complex reasoning needed.
</memory>
<action>
click(index=1)
input(index=2, text="hello")
</action>

REQUIREMENTS:
- Use key=value format: done(text="result", success=True)
- Use straight quotes " not fancy quotes " "
- Escape inner quotes with backslash: text="She said \\"hello\\""
- Never invent parameters not in <tools>
- for interactive indices only use indexes that are explicitly provided in the <browser_state> - dont use None for an index.

Examples:
navigate(url="https://google.com")
click(index=5)
input(index=3, text="hello", clear=True)
scroll(down=True, pages=1)
done(text="Task completed successfully", success=True)
</output>


<tools>
{action_description}
</tools>"""

		# Replace the system message
		modified_messages = []
		for msg in messages:
			if isinstance(msg, SystemMessage):
				modified_messages.append(SystemMessage(content=optimized_system_prompt))
			else:
				modified_messages.append(msg)

		return modified_messages

	def _generate_action_descriptions(self, schema: dict[str, Any]) -> str:
		"""Generate token-optimized action descriptions from AgentOutput schema.

		Extracts tool descriptions and parameter info directly from the schema without hardcoding.
		"""
		if '$defs' not in schema:
			return ''

		descriptions = []

		# Extract all actions from ActionModel definitions
		for def_name, def_schema in schema['$defs'].items():
			if not def_name.endswith('ActionModel') or 'properties' not in def_schema:
				continue

			for action_name, action_schema in def_schema['properties'].items():
				# Get action description from schema
				action_desc = action_schema.get('description', '').rstrip('.')

				# Extract parameter schema reference
				params = []
				param_ref = None

				if '$ref' in action_schema:
					param_ref = action_schema['$ref'].split('/')[-1]
				elif 'anyOf' in action_schema:
					for variant in action_schema['anyOf']:
						if '$ref' in variant:
							param_ref = variant['$ref'].split('/')[-1]
							break

				# Get parameters from referenced schema
				if param_ref and param_ref in schema['$defs']:
					param_schema = schema['$defs'][param_ref]
					if 'properties' in param_schema:
						required_fields = set(param_schema.get('required', []))

						for param_name, param_info in param_schema['properties'].items():
							# Check if this parameter is a nested object reference
							nested_ref = None
							if '$ref' in param_info:
								nested_ref = param_info['$ref'].split('/')[-1]

							# If it's a nested object, expand it as JSON structure
							if nested_ref and nested_ref in schema['$defs']:
								nested_schema = schema['$defs'][nested_ref]
								if 'properties' in nested_schema:
									# Build JSON-like structure for nested object
									nested_fields = []
									nested_required = set(nested_schema.get('required', []))
									for nested_name, nested_info in nested_schema['properties'].items():
										# Get type (handle anyOf for optional params)
										nested_type = nested_info.get('type')
										if not nested_type and 'anyOf' in nested_info:
											# Extract non-null type from anyOf
											for option in nested_info['anyOf']:
												if option.get('type') and option['type'] != 'null':
													nested_type = option['type']
													break
										nested_type = nested_type or 'any'

										nested_desc = nested_info.get('description', '')
										is_required = nested_name in nested_required

										# Format: name=type or name=type (description) or name?=type
										if is_required:
											if nested_desc:
												nested_fields.append(f'{nested_name}={nested_type} ({nested_desc})')
											else:
												nested_fields.append(f'{nested_name}={nested_type}')
										else:
											if nested_desc:
												nested_fields.append(f'{nested_name}?={nested_type} ({nested_desc})')
											else:
												nested_fields.append(f'{nested_name}?={nested_type}')

									# Format as JSON object
									param_desc = f'{param_name}={{{", ".join(nested_fields)}}}'
									params.append(param_desc)
									continue

							# Regular parameter (not nested object)
							# Get type (handle anyOf for optional params)
							param_type = param_info.get('type')
							if not param_type and 'anyOf' in param_info:
								# Extract non-null type from anyOf
								for option in param_info['anyOf']:
									if option.get('type') and option['type'] != 'null':
										param_type = option['type']
										break
							param_type = param_type or 'any'

							# Extract constraints (ge, le, min_length, max_length, etc.)
							constraints = []
							if 'minimum' in param_info:
								constraints.append(f'≥{param_info["minimum"]}')
							elif 'ge' in param_info:
								constraints.append(f'≥{param_info["ge"]}')

							if 'exclusiveMinimum' in param_info:
								constraints.append(f'>{param_info["exclusiveMinimum"]}')
							elif 'gt' in param_info:
								constraints.append(f'>{param_info["gt"]}')

							if 'maximum' in param_info:
								constraints.append(f'≤{param_info["maximum"]}')
							elif 'le' in param_info:
								constraints.append(f'≤{param_info["le"]}')

							if 'exclusiveMaximum' in param_info:
								constraints.append(f'<{param_info["exclusiveMaximum"]}')
							elif 'lt' in param_info:
								constraints.append(f'<{param_info["lt"]}')

							if 'minLength' in param_info:
								constraints.append(f'len≥{param_info["minLength"]}')
							elif 'min_length' in param_info:
								constraints.append(f'len≥{param_info["min_length"]}')

							if 'maxLength' in param_info:
								constraints.append(f'len≤{param_info["maxLength"]}')
							elif 'max_length' in param_info:
								constraints.append(f'len≤{param_info["max_length"]}')

							# Build parameter description
							if param_name not in required_fields:
								param_desc = f'{param_name}?={param_type}'
							else:
								param_desc = f'{param_name}={param_type}'

							# Add constraints if present
							if constraints:
								param_desc += f' [{",".join(constraints)}]'

							# Add description from schema if present
							desc = param_info.get('description', '')
							if desc:
								param_desc += f' ({desc})'

							params.append(param_desc)

				# Format: action_name(params): description
				# Or:     action_name(): description (if no params but has description)
				# Or:     action_name(params) (if has params but no description)
				# Or:     action_name() (if neither params nor description)
				params_str = f'({", ".join(params)})' if params else '()'

				if action_desc:
					action_text = f'{action_name}{params_str}: {action_desc}'
				else:
					action_text = f'{action_name}{params_str}'

				descriptions.append(action_text)

		return '\n'.join(descriptions)
