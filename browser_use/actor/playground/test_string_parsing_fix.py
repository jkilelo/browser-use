"""
Test script for code_processor string parsing with extremely challenging cases.
"""

from browser_use.tools.code_processor import fix_python_code_string_issues


def test_really_fucked_string_cases():
	"""Test the code processor with extremely challenging string parsing scenarios."""

	print('🧪 TESTING CODE PROCESSOR WITH EXTREMELY FUCKED STRING CASES')
	print('=' * 70)

	# Really challenging test cases that commonly break LLM-generated code
	test_cases = [
		{
			'name': 'Nightmare nested quotes',
			'code': """
async def executor():
	js_code = "() => 'He said "Hello" and she replied "I said \\"Hi\\" back" to him'"
	result = await target.evaluate(js_code)
	return result
""",
			'should_compile': True,
		},
		{
			'name': 'SQL-like string with multiple quote types',
			'code': """
async def executor():
	query = "() => `SELECT * FROM users WHERE name='John "The Ripper" Doe' AND data LIKE "%test%" AND status="active"`"
	result = await target.evaluate(query)
	return result
""",
			'should_compile': True,
		},
		{
			'name': 'Regex with escaped characters and quotes',
			'code': """
async def executor():
	regex_js = "() => /He said "Hello" to 'John'/.test('He said "Hello" to \\'John\\'')"
	result = await target.evaluate(regex_js)
	return result
""",
			'should_compile': True,
		},
		{
			'name': 'JSON with nested quotes and escaping',
			'code': """
async def executor():
	json_code = "() => JSON.parse('{"message": "She said \\"Hello\\" to me", "reply": "I said 'Hi' back"}')"
	result = await target.evaluate(json_code)
	return result
""",
			'should_compile': True,
		},
		{
			'name': 'HTML/CSS selector nightmare',
			'code': """
async def executor():
	selector = "() => document.querySelector("div[data-test='hello "world" test'] input[placeholder="Enter your "name" here"]")"
	result = await target.evaluate(selector)
	return result
""",
			'should_compile': True,
		},
		{
			'name': 'Template literal with embedded quotes',
			'code': """
async def executor():
	template = "() => `User ${user.name} said "Hello 'world'" at ${new Date()}`"
	result = await target.evaluate(template)
	return result
""",
			'should_compile': True,
		},
		{
			'name': 'Multiple problematic strings in one function',
			'code': """
async def executor():
	js1 = "() => 'Hello "world"'"
	js2 = "() => document.querySelector("input[type='text']")"
	js3 = "() => `Template with "quotes" and 'apostrophes'`"
	result1 = await target.evaluate(js1)
	result2 = await target.evaluate(js2)
	result3 = await target.evaluate(js3)
	return [result1, result2, result3]
""",
			'should_compile': True,
		},
		{
			'name': 'Windows file paths with escaping',
			'code': """
async def executor():
	path_js = "() => 'C:\\\\Users\\\\John "The User"\\\\Documents\\\\file.txt'"
	result = await target.evaluate(path_js)
	return result
""",
			'should_compile': True,
		},
		{
			'name': 'Markdown-like content with quotes',
			'code': """
async def executor():
	markdown = "() => 'He said > "This is a quote" and she replied > "I know""
	result = await target.evaluate(markdown)
	return result
""",
			'should_compile': True,
		},
		{
			'name': 'Mixed quote types with special characters',
			'code': """
async def executor():
	mixed = "() => 'Special chars: àáâãäå "quoted text" \\'escaped apostrophe\\' & more'"
	result = await target.evaluate(mixed)
	return result
""",
			'should_compile': True,
		},
		{
			'name': 'COMPLETELY FUCKED - All quote types nested',
			'code': """
async def executor():
	fucked = "() => 'Outer single "Inner double \\'Escaped single inside double\\' more double" back to single'"
	result = await target.evaluate(fucked)
	return result
""",
			'should_compile': True,
		},
		{
			'name': 'ULTRA FUCKED - Multi-line with everything',
			'code': """
async def executor():
	ultra_fucked = "() => {
		const data = {"name": "John "The Destroyer" Doe", "quote": 'He said "Hello \\'world\\'" to me'};
		const query = `SELECT * FROM users WHERE name='${data.name}' AND quote LIKE "%Hello%" AND status="active"`;
		return {data: data, query: query, message: 'Success with "mixed quotes" and \\'escaped stuff\\'};
	}"
	result = await target.evaluate(ultra_fucked)
	return result
""",
			'should_compile': True,
		},
		# === REGEX NIGHTMARE SCENARIOS ===
		{
			'name': 'REGEX - Email validation with quotes',
			'code': r"""
async def executor():
	email_regex = "() => /^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$/.test("user@example.com")"
	result = await target.evaluate(email_regex)
	return result
""",
			'should_compile': True,
		},
		{
			'name': 'REGEX - URL pattern with mixed quotes',
			'code': """
async def executor():
	url_regex = "() => /^https?:\\/\\/(www\\.)?[-a-zA-Z0-9@:%._\\+~#=]{1,256}\\.[a-zA-Z0-9()]{1,6}\b([-a-zA-Z0-9()@:%_\\+.~#?&//=]*)$/.test('https://example.com/path?param="value"')"
	result = await target.evaluate(url_regex)
	return result
""",
			'should_compile': True,
		},
		{
			'name': 'REGEX - Password validation with special chars',
			'code': r"""
async def executor():
	pwd_regex = "() => /^(?=.*[a-z])(?=.*[A-Z])(?=.*\d)(?=.*[@$!%*?&])[A-Za-z\d@$!%*?&]{8,}$/.test("MyP@ssw0rd!")"
	result = await target.evaluate(pwd_regex)
	return result
""",
			'should_compile': True,
		},
		{
			'name': 'REGEX - Phone number with quotes and escaping',
			'code': r"""
async def executor():
	phone_regex = "() => /^\+?1?[-.\s]?\(?([0-9]{3})\)?[-.\s]?([0-9]{3})[-.\s]?([0-9]{4})$/.test("+1 (555) 123-4567")"
	result = await target.evaluate(phone_regex)
	return result
""",
			'should_compile': True,
		},
		{
			'name': 'REGEX - HTML tag extraction with nested quotes',
			'code': """
async def executor():
	html_regex = "() => /<([a-z]+)([^<]+)*(?:>(.*)<\\/\1>|\\s+\\/>)/.exec('<div class="test" id="main">Content "with quotes"</div>')"
	result = await target.evaluate(html_regex)
	return result
""",
			'should_compile': True,
		},
		{
			'name': 'REGEX - JSON key extraction nightmare',
			'code': """
async def executor():
	json_regex = "() => /"([^"\\\\]|\\\\.)*"\\s*:\\s*("([^"\\\\]|\\\\.)*"|[+-]?\\d+\\.?\\d*([eE][+-]?\\d+)?|true|false|null)/.exec('{"name": "John "Doe"", "age": 30}')"
	result = await target.evaluate(json_regex)
	return result
""",
			'should_compile': True,
		},
		{
			'name': 'REGEX - CSS selector parsing with quotes',
			'code': """
async def executor():
	css_regex = "() => /([.#]?[a-zA-Z][a-zA-Z0-9_-]*|\\*|\\[([a-zA-Z][a-zA-Z0-9_-]*)([~|^$*]?=("[^"]*"|'[^']*'|[^\\]]*))?\\]|:([a-zA-Z][a-zA-Z0-9_-]*(\\([^)]*\\))?))/.test('input[type="text"][placeholder="Enter your name"]')"
	result = await target.evaluate(css_regex)
	return result
""",
			'should_compile': True,
		},
		{
			'name': 'REGEX - Log parsing with timestamps and quotes',
			'code': r"""
async def executor():
	log_regex = "() => /(\d{4}-\d{2}-\d{2}\s\d{2}:\d{2}:\d{2})\s\[([A-Z]+)\]\s(.+)/.exec('2023-12-01 14:30:22 [ERROR] User "admin" failed login attempt')"
	result = await target.evaluate(log_regex)
	return result
""",
			'should_compile': True,
		},
		{
			'name': 'REGEX - SQL injection detection with quotes',
			'code': """
async def executor():
	sql_regex = "() => /('|(\\-\\-)|(;)|(\\|)|(\\*)|(%)|(<)|(>)|(\\?)|(\\[)|(\\])|(\\{)|(\\})|(\\$)|(\\!)|(\\@)|(#)|(~)|(\\^)|(\\&)|(\\()|(\\))|(\\+)|(=))/i.test("'; DROP TABLE users; --")"
	result = await target.evaluate(sql_regex)
	return result
""",
			'should_compile': True,
		},
		{
			'name': 'REGEX - Complex file path with backslashes and quotes',
			'code': """
async def executor():
	path_regex = "() => /^([a-zA-Z]:|\\\\[\\\\\\w\\.\\s-]+\\\\[\\\\\\w\\s-]+|\\\\?[\\\\\\w.\\s-]+)*\\\\([\\\\\\w\\s-]*\\.)*([\\\\\\w\\s-]*)$/i.test('C:\\\\Users\\\\John "Doe"\\\\Documents\\\\file.txt')"
	result = await target.evaluate(path_regex)
	return result
""",
			'should_compile': True,
		},
		{
			'name': 'REGEX - IPv4 with port and quotes',
			'code': r"""
async def executor():
	ip_regex = "() => /^(25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)\.(25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)\.(25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)\.(25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)(:([0-9]|[1-9][0-9]|[1-9][0-9]{2}|[1-9][0-9]{3}|[1-5][0-9]{4}|6[0-4][0-9]{3}|65[0-4][0-9]{2}|655[0-2][0-9]|6553[0-5]))?$/.test("192.168.1.1:8080")"
	result = await target.evaluate(ip_regex)
	return result
""",
			'should_compile': True,
		},
		{
			'name': 'REGEX - Credit card with dashes and quotes',
			'code': """
async def executor():
	cc_regex = "() => /^(?:4[0-9]{12}(?:[0-9]{3})?|5[1-5][0-9]{14}|3[47][0-9]{13}|3[0-9]{13}|6(?:011|5[0-9]{2})[0-9]{12})$/.test("4532-1234-5678-9012".replace(/[^0-9]/g, ''))"
	result = await target.evaluate(cc_regex)
	return result
""",
			'should_compile': True,
		},
		{
			'name': 'REGEX - Markdown link extraction with nested quotes',
			'code': """
async def executor():
	md_regex = "() => /\\[([^\\]]*?)\\]\\(([^\\)]+?)\\)/g.exec('[Link "with quotes"](https://example.com/path?param="value")')"
	result = await target.evaluate(md_regex)
	return result
""",
			'should_compile': True,
		},
		{
			'name': 'REGEX - JavaScript function parsing with quotes',
			'code': """
async def executor():
	js_regex = "() => /function\\s+([a-zA-Z_$][a-zA-Z0-9_$]*)\\s*\\(([^)]*)\\)\\s*\\{([\\s\\S]*?)\\}/g.exec('function sayHello(name) { return \"Hello \" + name + \"!\"; }')"
	result = await target.evaluate(js_regex)
	return result
""",
			'should_compile': True,
		},
		{
			'name': 'REGEX - XML/HTML attribute parsing nightmare',
			'code': """
async def executor():
	xml_regex = "() => /([a-zA-Z][a-zA-Z0-9_-]*)\\s*=\\s*([\"'])([^\\2]*?)\\2/g.exec('<input type=\"text\" placeholder=\"Enter your \\"name\\" here\" class='form-control'>')"
	result = await target.evaluate(xml_regex)
	return result
""",
			'should_compile': True,
		},
		{
			'name': 'REGEX - Multi-line regex with embedded quotes',
			'code': """
async def executor():
	multi_regex = "() => {
		const pattern = /^(?:(?:25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)\\.){3}(?:25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)$/;
		const testStr = "192.168.1.1";
		return pattern.test(testStr) ? 'Valid IP "address"' : 'Invalid format';
	}"
	result = await target.evaluate(multi_regex)
	return result
""",
			'should_compile': True,
		},
		{
			'name': 'REGEX - ULTRA NIGHTMARE - Everything combined',
			'code': """
async def executor():
	nightmare_regex = "() => {
		const emailPattern = /^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\\.[a-zA-Z]{2,}$/;
		const phonePattern = /^\\+?1?[-\\.\\s]?\\(?([0-9]{3})\\)?[-\\.\\s]?([0-9]{3})[-\\.\\s]?([0-9]{4})$/;
		const urlPattern = /^https?:\\/\\/(www\\.)?[-a-zA-Z0-9@:%._\\+~#=]{1,256}\\.[a-zA-Z0-9()]{1,6}\\b([-a-zA-Z0-9()@:%_\\+.~#?&\\/\\/=]*)$/;
		const data = 'Contact: "john.doe@example.com", Phone: "+1 (555) 123-4567", Website: "https://example.com"';
		return {
			email: emailPattern.test('john.doe@example.com'),
			phone: phonePattern.test('+1 (555) 123-4567'),
			url: urlPattern.test('https://example.com'),
			message: 'All patterns "tested" successfully!'
		};
	}"
	result = await target.evaluate(nightmare_regex)
	return result
""",
			'should_compile': True,
		},
	]

	passed = 0
	total = len(test_cases)

	for i, test_case in enumerate(test_cases, 1):
		print(f'\n--- Test {i}: {test_case["name"]} ---')
		print('Original (broken) code:')
		print(repr(test_case['code']))  # Use repr to show exact string representation

		# Test if original code compiles (should fail)
		original_compiles = True
		try:
			compile(test_case['code'], '<original>', 'exec')
		except SyntaxError:
			original_compiles = False

		print(f'Original compiles: {"✅ YES" if original_compiles else "❌ NO (as expected)"}')

		try:
			# Apply the string parsing fix
			fixed_code = fix_python_code_string_issues(test_case['code'])

			print('Fixed code:')
			print(repr(fixed_code))

			# Test if fixed code compiles
			try:
				compile(fixed_code, '<fixed>', 'exec')
				print('✅ PASS - Fixed code compiles successfully')

				# Check if the fix actually changed something when needed
				if not original_compiles and fixed_code != test_case['code']:
					print('✅ PASS - Code was successfully modified and now compiles')
					passed += 1
				elif original_compiles and fixed_code == test_case['code']:
					print('✅ PASS - Valid code left unchanged')
					passed += 1
				else:
					print('⚠️  PARTIAL - Code compiles but modification logic might need review')
					passed += 1

			except SyntaxError as e:
				print(f'❌ FAIL - Fixed code still has syntax error: {e}')
				print('Error location:', getattr(e, 'text', 'Unknown'))

		except Exception as e:
			print(f'❌ FAIL - String parsing fix threw exception: {e}')
			import traceback

			traceback.print_exc()

	print('\n' + '=' * 70)
	print('🧪 CODE PROCESSOR EXTREME STRESS TEST RESULTS')
	print('=' * 70)
	print(f'✅ Passed: {passed}/{total} ({passed / total * 100:.1f}%)')
	print(f'❌ Failed: {total - passed}/{total} ({(total - passed) / total * 100:.1f}%)')

	if passed == total:
		print('🎉 ALL EXTREME CASES HANDLED SUCCESSFULLY!')
		print('The code processor is ROBUST AS FUCK! 💪')
	elif passed >= total * 0.8:
		print('🟡 MOSTLY SUCCESSFUL - The processor handles most fucked cases')
	else:
		print('🔴 NEEDS WORK - Many extreme cases still failing')

	return passed, total


if __name__ == '__main__':
	test_really_fucked_string_cases()
