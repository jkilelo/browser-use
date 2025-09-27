import ast
import base64
import inspect
import os
import pickle
from collections.abc import Awaitable, Callable
from functools import wraps
from typing import Any, TypeVar, Union, cast, get_args, get_origin

import httpx
from pydantic import BaseModel

T = TypeVar('T')


class RemoteExecutionError(Exception):
	pass


class CodeRequest(BaseModel):
	code: str
	BROWSER_USE_API_KEY: str
	env: dict = {}


_DEFAULT_SERVER_URL = 'https://code-execution-use-production.up.railway.app'
# _DEFAULT_SERVER_URL = 'http://localhost:8080'


class RemoteExecutor:
	def __init__(
		self,
		BROWSER_USE_API_KEY: str | None = None,
		server_url: str | None = None,
		timeout: float = 3_000.0,  # no timeout by default
		**env_vars: str | None,
	):
		self.BROWSER_USE_API_KEY = BROWSER_USE_API_KEY or os.getenv('BROWSER_USE_API_KEY')
		self.server_url = server_url or _DEFAULT_SERVER_URL
		self.timeout = timeout
		self.env_vars = env_vars

	def execute(self, **extra_env_vars: str | None):
		"""Execute a function remotely, if you want to pass extra env vars, use the **extra_env_vars parameter"""

		def decorator(func: Callable[..., Awaitable[T]]) -> Callable[..., Awaitable[T]]:
			@wraps(func)
			async def wrapper(*_args, **_kwargs) -> T:
				# Get API key
				api_key = self.BROWSER_USE_API_KEY or os.getenv('BROWSER_USE_API_KEY')
				if not api_key:
					raise RemoteExecutionError('BROWSER_USE_API_KEY is required')

				# Extract function source and create execution code
				source = inspect.getsource(func)
				tree = ast.parse(source)

				# Find and clean the function
				for node in tree.body:
					if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
						node.decorator_list = []  # Remove decorators
						break

				# Extract imports and classes used in the function
				local_classes = self._extract_local_classes(func)

				# Get combined source (function + classes) for import detection
				class_sources = [ast.unparse(cls) for cls in local_classes]
				combined_source = source + '\n'.join(class_sources)
				used_imports = self._extract_used_imports(combined_source)

				# Add necessary imports
				imports = [
					ast.ImportFrom(module='browser_use', names=[ast.alias(name='Browser')], level=0),
					ast.ImportFrom(module='browser_use', names=[ast.alias(name='Agent')], level=0),
				]

				# Add extracted imports
				imports.extend(used_imports)

				function_code = ast.unparse(ast.Module(body=imports + local_classes + tree.body, type_ignores=[]))

				# Create execution wrapper
				execution_code = f"""{function_code}

import asyncio
import pickle
import base64

async def run():
    browser = Browser(use_cloud=True, keep_alive=True)
    try:
        await browser.start()
        result = await {func.__name__}(browser)

        # Serialize result - just dump as-is, let client handle reconstruction
        try:
            from pydantic import BaseModel
            if isinstance(result, BaseModel):
                serialized = result.model_dump()
            else:
                serialized = result
        except ImportError:
            serialized = result

        print("RESULT:" + base64.b64encode(pickle.dumps(serialized)).decode())
    finally:
        await browser.stop()
"""

				# Send to server
				payload: CodeRequest = CodeRequest(
					code=base64.b64encode(execution_code.encode()).decode(),
					BROWSER_USE_API_KEY=api_key,
				)
				if self.env_vars:
					payload.env = self.env_vars

				if extra_env_vars:
					payload.env = extra_env_vars

				# Use custom server URL or default to localhost
				url = self.server_url.rstrip('/') + '/execute'

				async with httpx.AsyncClient(timeout=self.timeout) as client:
					try:
						response = await client.post(url, json=payload.model_dump())
					except httpx.TimeoutException as e:
						raise RemoteExecutionError(f'Request timed out after {self.timeout}s: {e}') from e
					except httpx.RequestError as e:
						raise RemoteExecutionError(f'Request failed: {e}') from e
				data = response.json()

				if not data.get('success'):
					raise RemoteExecutionError(f'Execution failed: {data.get("error")}')

				# Extract result
				stdout = data.get('stdout', '')
				if 'RESULT:' in stdout:
					result_b64 = stdout.split('RESULT:')[1].strip().split()[0]
					result = pickle.loads(base64.b64decode(result_b64))

					# Reconstruct based on return type annotation (FastAPI-style)
					return_annotation = func.__annotations__.get('return')
					if return_annotation:
						return self._parse_with_type_annotation(result, return_annotation)

					return result

				return stdout

			# Preserve type info
			wrapper.__annotations__ = func.__annotations__.copy()
			if 'browser' in wrapper.__annotations__:
				del wrapper.__annotations__['browser']

			# Update signature to remove browser parameter
			sig = inspect.signature(func)
			params = [p for p in sig.parameters.values() if p.name != 'browser']
			wrapper.__signature__ = sig.replace(parameters=params)  # type: ignore

			return cast(Callable[..., Awaitable[T]], wrapper)

		return decorator

	def _parse_with_type_annotation(self, data: Any, annotation: Any) -> Any:
		"""Parse data with type annotation (FastAPI-style parsing)"""
		try:
			# Handle None
			if data is None:
				return None

			# Get origin and args for generic types
			origin = get_origin(annotation)
			args = get_args(annotation)

			# Handle Union types (both typing.Union and | syntax)
			if origin is Union or (hasattr(annotation, '__class__') and annotation.__class__.__name__ == 'UnionType'):
				# Try each union member until one works
				union_args = args or getattr(annotation, '__args__', [])
				for arg in union_args:
					if arg is type(None) and data is None:
						return None
					if arg is not type(None):
						try:
							return self._parse_with_type_annotation(data, arg)
						except Exception:
							continue
				return data

			# Handle List types
			if origin is list:
				if not isinstance(data, list):
					return data
				if args:
					return [self._parse_with_type_annotation(item, args[0]) for item in data]
				return data

			# Handle Dict types
			if origin is dict:
				if not isinstance(data, dict):
					return data
				if len(args) == 2:
					# Dict[key_type, value_type]
					return {
						self._parse_with_type_annotation(k, args[0]): self._parse_with_type_annotation(v, args[1])
						for k, v in data.items()
					}
				return data

			# Handle Optional (which is Union[T, None])
			if hasattr(annotation, '__origin__') and annotation.__origin__ is Union:
				union_args = annotation.__args__
				if len(union_args) == 2 and type(None) in union_args:
					# This is Optional[T]
					non_none_type = union_args[0] if union_args[1] is type(None) else union_args[1]
					return self._parse_with_type_annotation(data, non_none_type)

			# Handle Pydantic models
			if hasattr(annotation, 'model_validate'):
				return annotation.model_validate(data)

			# Handle regular classes with constructor
			if inspect.isclass(annotation) and isinstance(data, dict):
				return annotation(**data)

			# Return as-is for basic types
			return data

		except Exception:
			# If parsing fails, return original data
			return data

	def _extract_local_classes(self, func: Callable) -> list:
		"""Extract local class definitions used by the function"""
		classes = []

		# Get the module where the function is defined
		module = inspect.getmodule(func)
		if not module:
			return classes

		# Get function source to find referenced classes
		source = inspect.getsource(func)

		# Parse the entire module to find class definitions and imports
		try:
			module_source = inspect.getsource(module)
			module_tree = ast.parse(module_source)

			# Find all class definitions in the current module
			for node in ast.walk(module_tree):
				if isinstance(node, ast.ClassDef):
					# Check if this class is referenced in the function
					if node.name in source:
						classes.append(node)

			# Handle imports like "from views import HackernewsPosts"
			import_files = []
			for node in ast.walk(module_tree):
				if isinstance(node, ast.ImportFrom) and node.module and not node.module.startswith(('.', 'pydantic', 'typing')):
					# Try to find the module file in the same directory
					try:
						module_dir = os.path.dirname(module.__file__)  # type: ignore
						import_file = os.path.join(module_dir, f'{node.module}.py')
						if os.path.exists(import_file):
							import_files.append((import_file, [alias.name for alias in node.names]))
					except Exception:
						pass

			# Extract classes from imported files
			for import_file, imported_names in import_files:
				try:
					with open(import_file) as f:
						imported_source = f.read()
					imported_tree = ast.parse(imported_source)

					for node in ast.walk(imported_tree):
						if isinstance(node, ast.ClassDef):
							if node.name in imported_names or node.name in source:
								classes.append(node)

				except Exception:
					pass

		except Exception:
			pass

		return classes

	def _extract_used_imports(self, source: str) -> list:
		"""Extract imports that are actually used in the function"""
		imports = []

		# Common patterns to look for
		patterns = {
			'pydantic': ['BaseModel', 'Field', 'validator', 'root_validator'],
			'typing': ['Dict', 'List', 'Optional', 'Union', 'Any', 'Tuple'],
			'requests': ['requests'],
			'json': ['json'],
			'datetime': ['datetime', 'date', 'time'],
		}

		for module, items in patterns.items():
			used_items = []
			for item in items:
				if item in source:
					used_items.append(ast.alias(name=item))

			if used_items:
				if module in ['requests', 'json', 'datetime']:
					# For these, add as regular import
					imports.append(ast.Import(names=[ast.alias(name=module)]))
				else:
					# For others, add as from import
					imports.append(ast.ImportFrom(module=module, names=used_items, level=0))

		return imports
