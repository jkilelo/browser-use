"""
Code processing utilities for fixing common Python string issues in LLM-generated code.
"""

import ast
import re


def fix_python_code_string_issues(code: str) -> str:
	"""Fix common Python string issues in LLM-generated code."""

	# Try to parse the code first to see if it's already valid
	try:
		ast.parse(code)
		return code  # Already valid, no need to fix
	except SyntaxError:
		pass  # Code has issues, proceed with fixing

	# First try to fix multi-line string assignments that span multiple lines
	code = _fix_multiline_string_assignments(code)

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
				fixed_value = _fix_string_value(value.strip())
				if fixed_value != value.strip():
					fixed_lines.append(f'{indent}{assignment}{fixed_value}')
					continue

		# Fix template string issues
		# Pattern: "() => 'text with "quotes" in it'"
		if '=>' in line and ('"' in line or "'" in line):
			# This looks like a JavaScript string assignment
			fixed_line = _fix_js_string_assignment(line)
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
		return _aggressive_string_fix(code, e)


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
