"""
Code processing utilities for fixing common Python string issues and JavaScript evaluation in LLM-generated code.
"""

import ast
import re


class CodeProcessor:
	"""Handles code processing for both Python and browser actor JavaScript code"""

	@staticmethod
	def fix_python_code_string_issues(code: str) -> str:
		"""Fix Python code issues, but preserve JavaScript strings in target.evaluate()"""

		# If code contains target.evaluate, handle specially to preserve JavaScript strings
		if 'target.evaluate(' in code:
			return CodeProcessor.fix_browser_actor_python_code(code)

		# Regular Python code fixing for non-browser-actor code
		# Try to parse the code first to see if it's already valid
		try:
			ast.parse(code)
			return code  # Already valid, no need to fix
		except SyntaxError:
			pass  # Code has issues, proceed with fixing

		# First try to fix multi-line string assignments that span multiple lines
		code = CodeProcessor._fix_multiline_string_assignments(code)

		# Try parsing again after multi-line fix
		try:
			ast.parse(code)
			return code
		except SyntaxError:
			pass  # Still has issues, continue with line-by-line fixes

		# Common fixes for Python string issues
		lines = code.split('\n')
		fixed_lines = []

		for line in lines:
			original_line = line

			# Skip comments and empty lines
			if line.strip().startswith('#') or not line.strip():
				fixed_lines.append(line)
				continue

			# Fix common quote escaping issues in string assignments
			# Pattern: variable = "string with "inner quotes""
			if '=' in line and ('"' in line or "'" in line):
				# Find string assignments
				match = re.match(r'(\s*)(\w+\s*=\s*)(.*)', line)
				if match:
					indent, assignment, value = match.groups()

					# Try to fix the string value
					fixed_value = CodeProcessor._fix_string_value(value.strip())
					if fixed_value != value.strip():
						fixed_lines.append(f'{indent}{assignment}{fixed_value}')
						continue

			# Fix template string issues
			# Pattern: "() => 'text with "quotes" in it'"
			if '=>' in line and ('"' in line or "'" in line):
				# This looks like a JavaScript string assignment
				fixed_line = CodeProcessor._fix_js_string_assignment(line)
				if fixed_line != line:
					fixed_lines.append(fixed_line)
					continue

			# If no fixes applied, keep original
			fixed_lines.append(original_line)

		fixed_code = '\n'.join(fixed_lines)

		# Final validation - try to parse the fixed code
		try:
			ast.parse(fixed_code)
			return fixed_code
		except SyntaxError as e:
			# If still invalid, try a more aggressive fix
			return CodeProcessor._aggressive_string_fix(code, e)

	@staticmethod
	def fix_browser_actor_python_code(code: str) -> str:
		"""Fix Python code that contains browser actor target.evaluate() calls"""

		# Try to parse the code first to see if it's already valid
		try:
			ast.parse(code)
			return code  # Already valid, no need to fix
		except SyntaxError:
			pass  # Code has issues, proceed with fixing

		# For browser actor code, we need to be careful not to break JavaScript strings
		lines = code.split('\n')
		fixed_lines = []

		for line in lines:
			original_line = line

			# Skip comments and empty lines
			if line.strip().startswith('#') or not line.strip():
				fixed_lines.append(line)
				continue

			# Special handling for lines containing target.evaluate()
			if 'target.evaluate(' in line:
				# Preserve the JavaScript strings inside target.evaluate() calls
				fixed_line = CodeProcessor._fix_target_evaluate_line(line)
				fixed_lines.append(fixed_line)
			else:
				# Apply regular Python fixes to non-JavaScript lines
				if '=' in line and ('"' in line or "'" in line):
					# Find string assignments
					match = re.match(r'(\s*)(\w+\s*=\s*)(.*)', line)
					if match:
						indent, assignment, value = match.groups()

						# Try to fix the string value
						fixed_value = CodeProcessor._fix_string_value(value.strip())
						if fixed_value != value.strip():
							fixed_lines.append(f'{indent}{assignment}{fixed_value}')
							continue

				# If no fixes applied, keep original
				fixed_lines.append(original_line)

		return '\n'.join(fixed_lines)

	@staticmethod
	def fix_browser_actor_code_issues(code: str) -> str:
		"""Fix code issues specifically for browser actor execution"""
		# Don't apply Python string fixes to JavaScript evaluation calls
		if 'target.evaluate(' in code:
			# Extract and preserve JavaScript strings in target.evaluate calls
			return CodeProcessor._preserve_js_strings_in_target_evaluate(code)
		else:
			# Regular Python code fixes for non-JavaScript code
			return CodeProcessor.fix_python_code_string_issues(code)

	@staticmethod
	def fix_js_code_for_evaluate(js_code: str) -> str:
		"""Fix JavaScript code specifically for target.evaluate() execution"""

		# Remove excessive escaping that might have been added by LLM
		js_code = re.sub(r'\\{4,}', r'\\', js_code)  # Replace 4+ backslashes with single
		js_code = re.sub(r'\\{3}', r'\\', js_code)  # Replace triple backslashes with single
		js_code = re.sub(r'\\{2}', r'\\', js_code)  # Replace double backslashes with single

		# Fix CSS selector escaping issues
		js_code = re.sub(r'\\+"', r'"', js_code)  # Fix over-escaped quotes
		js_code = re.sub(r"\\'", r"'", js_code)  # Fix escaped single quotes

		# Fix hex-encoded characters back to normal
		js_code = re.sub(r'\\x3d', r'=', js_code)  # \x3d -> =
		js_code = re.sub(r'\\x22', r'"', js_code)  # \x22 -> "
		js_code = re.sub(r'\\x27', r"'", js_code)  # \x27 -> '

		# Validate CSS selectors in the JavaScript code before execution
		js_code = CodeProcessor._validate_and_fix_css_selectors_in_js(js_code)

		# Ensure proper arrow function format for evaluate
		if not js_code.strip().startswith('(') and '=>' in js_code:
			# Wrap in parentheses if it's an arrow function but not properly wrapped
			if js_code.strip().startswith('() =>'):
				pass  # Already correct format
			elif '=>' in js_code and not js_code.strip().startswith('('):
				js_code = f'() => {js_code.strip()}'

		return js_code

	@staticmethod
	def validate_css_selector(selector: str) -> bool:
		"""Validate CSS selector syntax"""
		try:
			# Basic validation - check for balanced quotes
			if selector.count('"') % 2 != 0 or selector.count("'") % 2 != 0:
				return False

			# Check for common malformed patterns
			malformed_patterns = [
				r'\\{2,}',  # Multiple consecutive backslashes
				r'\\x[0-9a-fA-F]{2}',  # Hex escape sequences (shouldn't be in CSS)
				r'\\[\'"]',  # Escaped quotes (usually incorrect in CSS selectors)
			]

			for pattern in malformed_patterns:
				if re.search(pattern, selector):
					return False

			# Check for unbalanced brackets
			brackets = {'[': ']', '(': ')'}
			stack = []

			for char in selector:
				if char in brackets:
					stack.append(char)
				elif char in brackets.values():
					if not stack:
						return False
					if brackets[stack.pop()] != char:
						return False

			return len(stack) == 0

		except Exception:
			return False

	@staticmethod
	def fix_css_selector(selector: str) -> str:
		"""Fix common CSS selector issues"""

		# Remove excessive escaping
		selector = re.sub(r'\\{2,}', r'', selector)  # Remove multiple backslashes

		# Fix hex-encoded characters
		selector = re.sub(r'\\x3d', r'=', selector)  # \x3d -> =
		selector = re.sub(r'\\x22', r'"', selector)  # \x22 -> "
		selector = re.sub(r'\\x27', r"'", selector)  # \x27 -> '

		# Fix escaped quotes that shouldn't be escaped in CSS selectors
		selector = re.sub(r'\\"', r'"', selector)  # \" -> "
		selector = re.sub(r"\\'", r"'", selector)  # \' -> '

		# Ensure proper attribute selector format
		selector = re.sub(r'(\w+)\s*=\s*([^"\'\]\s]+)', r'\1="\2"', selector)  # Add quotes to unquoted attribute values

		return selector

	# Private helper methods
	@staticmethod
	def _preserve_js_strings_in_target_evaluate(code: str) -> str:
		"""Preserve JavaScript strings in target.evaluate() calls to prevent over-escaping"""

		# Pattern to match target.evaluate('...') calls
		pattern = r"(target\.evaluate\s*\(\s*['\"])(.*?)(['\"](?:\s*,.*?)?\s*\))"

		def fix_js_string(match):
			prefix = match.group(1)
			js_code = match.group(2)
			suffix = match.group(3)

			# Fix common JavaScript string issues without over-escaping
			fixed_js = CodeProcessor.fix_js_code_for_evaluate(js_code)

			return f'{prefix}{fixed_js}{suffix}'

		# Apply fixes to all target.evaluate calls
		fixed_code = re.sub(pattern, fix_js_string, code, flags=re.DOTALL)

		# Apply basic Python fixes to the rest of the code
		lines = fixed_code.split('\n')
		fixed_lines = []

		for line in lines:
			# Skip lines with target.evaluate - they're already fixed
			if 'target.evaluate(' in line:
				fixed_lines.append(line)
			else:
				# Basic Python syntax fixes for non-JS lines
				fixed_lines.append(line)

		return '\n'.join(fixed_lines)

	@staticmethod
	def _validate_and_fix_css_selectors_in_js(js_code: str) -> str:
		"""Validate and fix CSS selectors in JavaScript code"""

		# Pattern to find querySelector/querySelectorAll calls with string selectors
		pattern = r'(querySelector(?:All)?\s*\(\s*[\'"])([^\'\"]+)([\'\"]\s*\))'

		def fix_selector(match):
			prefix = match.group(1)
			selector = match.group(2)
			suffix = match.group(3)

			# Validate and fix the CSS selector
			if not CodeProcessor.validate_css_selector(selector):
				# Try to fix common issues
				fixed_selector = CodeProcessor.fix_css_selector(selector)
				return f'{prefix}{fixed_selector}{suffix}'

			return match.group(0)  # Return original if valid

		# Apply fixes to all querySelector calls
		return re.sub(pattern, fix_selector, js_code)

	@staticmethod
	def _fix_multiline_string_assignments(code: str) -> str:
		"""Fix multi-line string assignments that span multiple lines."""

		# Look for patterns like:
		# variable = "() => {
		#     content across multiple lines
		# }"

		# Find assignments that start with quotes but span multiple lines
		lines = code.split('\n')
		fixed_lines = []
		i = 0

		while i < len(lines):
			line = lines[i]

			# Look for variable assignment with opening quote but no closing quote on same line
			match = re.match(r'(\s*)(\w+\s*=\s*)"([^"]*(?:(?!").)*)\s*$', line)
			if match and '=>' in line:
				indent, assignment, content = match.groups()

				# This looks like the start of a multi-line JS assignment
				# Collect all lines until we find the closing quote
				collected_content = [content]
				j = i + 1
				found_closing = False

				while j < len(lines):
					next_line = lines[j]
					if '"' in next_line and next_line.strip().endswith('"'):
						# Found the closing quote
						collected_content.append(next_line.strip()[:-1])  # Remove closing quote
						found_closing = True
						break
					else:
						collected_content.append(next_line)
					j += 1

				if found_closing:
					# Reconstruct as a proper multi-line string with triple quotes
					full_content = '\n'.join(collected_content)
					fixed_lines.append(f'{indent}{assignment}"""{full_content}"""')
					i = j + 1  # Skip all the lines we just processed
					continue

			# If no multi-line fix applied, keep the original line
			fixed_lines.append(line)
			i += 1

		return '\n'.join(fixed_lines)

	@staticmethod
	def _fix_string_value(value: str) -> str:
		"""Fix a string value with quote issues."""
		# If it starts and ends with quotes, check for issues inside
		if (value.startswith('"') and value.endswith('"')) or (value.startswith("'") and value.endswith("'")):
			outer_quote = value[0]
			inner_content = value[1:-1]

			# If the inner content has unescaped quotes of the same type
			if outer_quote == '"' and '"' in inner_content:
				# Try using triple quotes instead
				if '"""' not in value:
					return f'"""{inner_content}"""'
				# Or switch to single quotes
				elif "'" not in inner_content:
					return f"'{inner_content}'"
				# Or escape the inner quotes
				else:
					escaped_content = inner_content.replace('"', '\\"')
					return f'"{escaped_content}"'

			elif outer_quote == "'" and "'" in inner_content:
				# Try using triple quotes instead
				if "'''" not in value:
					return f"'''{inner_content}'''"
				# Or switch to double quotes
				elif '"' not in inner_content:
					return f'"{inner_content}"'
				# Or escape the inner quotes
				else:
					escaped_content = inner_content.replace("'", "\\'")
					return f"'{escaped_content}'"

		return value

	@staticmethod
	def _fix_js_string_assignment(line: str) -> str:
		"""Fix JavaScript string assignments in Python code."""

		# Pattern: js_code = "() => 'text with "quotes"'"
		match = re.match(r'(\s*)(\w+\s*=\s*)(.*)', line)
		if not match:
			return line

		indent, assignment, value = match.groups()

		# If this looks like a JS arrow function in quotes
		if '=>' in value and ('"' in value or "'" in value):
			# Handle multi-line JavaScript inside quotes
			if '\n' in value or '\t' in value:
				# This is a multi-line JS string - need special handling
				if value.startswith('"') and value.count('"') > 2:
					# Extract the JavaScript content without outer quotes
					inner = value[1:] if value.startswith('"') else value
					# Remove trailing quote if it exists
					if inner.endswith('"'):
						inner = inner[:-1]
					# Use triple quotes and preserve the structure
					return f'{indent}{assignment}"""{inner}"""'
			else:
				# Single line case - use triple quotes to avoid escaping issues
				if value.startswith('"') and value.endswith('"'):
					inner = value[1:-1]
					if '"""' not in value:
						return f'{indent}{assignment}"""{inner}"""'
				elif value.startswith("'") and value.endswith("'"):
					inner = value[1:-1]
					if "'''" not in value:
						return f"{indent}{assignment}'''{inner}'''"

		return line

	@staticmethod
	def _aggressive_string_fix(code: str, syntax_error: SyntaxError) -> str:
		"""Last resort aggressive string fixing."""
		# Get error location
		error_line_no = syntax_error.lineno - 1 if syntax_error.lineno else 0
		lines = code.split('\n')

		if error_line_no < len(lines):
			error_line = lines[error_line_no]

			# If the error is about quotes, try wrapping in triple quotes
			if 'quote' in str(syntax_error).lower() or 'string' in str(syntax_error).lower():
				# Find the assignment and wrap the value in triple quotes
				if '=' in error_line:
					parts = error_line.split('=', 1)
					if len(parts) == 2:
						indent_and_var = parts[0]
						value = parts[1].strip()

						# Remove existing quotes and wrap in triple quotes
						value = value.strip('"\'')
						lines[error_line_no] = f'{indent_and_var}= """{value}"""'

						return '\n'.join(lines)

		# If all else fails, return original code (let the error bubble up)
		return code

	@staticmethod
	def _fix_target_evaluate_line(line: str) -> str:
		"""Fix a line containing target.evaluate() without breaking JavaScript strings"""

		# Pattern to match target.evaluate() calls
		pattern = r"(.*target\.evaluate\s*\(\s*['\"])(.*?)(['\"].*)"

		match = re.match(pattern, line, re.DOTALL)
		if not match:
			return line  # No target.evaluate found or malformed

		prefix = match.group(1)
		js_code = match.group(2)
		suffix = match.group(3)

		# Don't apply Python string fixes to the JavaScript code part
		# Only ensure the JavaScript is properly formatted
		fixed_js = CodeProcessor._ensure_proper_js_format(js_code)

		return f'{prefix}{fixed_js}{suffix}'

	@staticmethod
	def _ensure_proper_js_format(js_code: str) -> str:
		"""Ensure JavaScript code is properly formatted for target.evaluate()"""

		# Remove excessive Python-style escaping that might interfere with JavaScript
		js_code = re.sub(r'\\{2,}', '\\', js_code)  # Reduce multiple backslashes

		# Ensure arrow function format if it contains '=>'
		if '=>' in js_code and not js_code.strip().startswith('('):
			if not js_code.strip().startswith('() =>'):
				js_code = f'() => {js_code.strip()}'

		return js_code


# Backward compatibility functions
def fix_python_code_string_issues(code: str) -> str:
	"""Backward compatibility wrapper"""
	return CodeProcessor.fix_python_code_string_issues(code)
