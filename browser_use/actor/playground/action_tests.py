from cdp_use.client import asyncio

from browser_use.actor import Browser
from browser_use.browser.session import BrowserSession


async def run_js_test(target, test_name: str, js_code: str, *args, expected_type=str, should_fail=False):
	"""Helper to run a single JS test with error handling and validation."""
	print(f'\n--- {test_name} ---')
	print(f'Code: {js_code}')
	if args:
		print(f'Args: {args}')

	try:
		result = await target.evaluate(js_code, *args)
		if should_fail:
			print(f'❌ UNEXPECTED SUCCESS: {result}')
			return False
		else:
			print(f'✅ SUCCESS: {type(result).__name__} = {result}')
			if expected_type and not isinstance(result, expected_type):
				print(f'⚠️  TYPE MISMATCH: Expected {expected_type.__name__}, got {type(result).__name__}')
			return True
	except Exception as e:
		if should_fail:
			print(f'✅ EXPECTED FAILURE: {e}')
			return True
		else:
			print(f'❌ UNEXPECTED FAILURE: {e}')
			return False


async def test_javascript_evaluation():
	"""Comprehensive JavaScript evaluation tests."""
	browser_session = BrowserSession()
	await browser_session.start()

	browser = Browser(browser_session.cdp_client)
	target = await browser.newTarget('about:blank')

	# Wait for target to be ready
	await asyncio.sleep(1)

	print('🧪 STARTING COMPREHENSIVE JAVASCRIPT EVALUATION TESTS')

	passed = 0
	total = 0

	# === BASIC SYNTAX TESTS ===

	tests = [
		# Basic return types
		('Simple string', "() => 'hello world'"),
		('Simple number', '() => 42'),
		('Simple boolean true', '() => true'),
		('Simple boolean false', '() => false'),
		('Simple null', '() => null'),
		('Simple undefined', '() => undefined'),
		# Math operations
		('Math addition', '() => 2 + 3'),
		('Math multiplication', '() => 6 * 7'),
		('Math.max', '() => Math.max(1, 5, 3)'),
		('Math.random', '() => Math.random() > 0'),
		# String operations
		('String concatenation', "() => 'hello' + ' ' + 'world'"),
		('String length', "() => 'javascript'.length"),
		('String substring', "() => 'javascript'.substring(0, 4)"),
		('String includes', "() => 'javascript'.includes('script')"),
		# Arrays (should become JSON)
		('Simple array', '() => [1, 2, 3]'),
		('String array', "() => ['a', 'b', 'c']"),
		('Mixed array', "() => [1, 'two', true, null]"),
		('Array length', '() => [1, 2, 3, 4].length'),
		('Array join', "() => ['a', 'b', 'c'].join('-')"),
		# Objects (should become JSON)
		('Simple object', "() => ({name: 'test', value: 123})"),
		('Nested object', "() => ({user: {name: 'john', age: 30}, active: true})"),
		('Object keys', '() => Object.keys({a: 1, b: 2})'),
		# Date operations
		('Date now', '() => Date.now()'),
		('Date string', '() => new Date().toString()'),
		('Date ISO', '() => new Date().toISOString()'),
		# JSON operations
		('JSON stringify', "() => JSON.stringify({test: 'value'})"),
		('JSON parse', '() => JSON.parse(\'{"key": "value"}\')'),
		# DOM basic tests (even on blank page)
		('Document exists', '() => !!document'),
		('Document title', '() => document.title'),
		('Document URL', '() => document.URL'),
		('Document ready state', '() => document.readyState'),
		('Window location href', '() => window.location.href'),
		('Window inner width', '() => window.innerWidth'),
		('Window inner height', '() => window.innerHeight'),
		# Regular expressions
		('Regex test', "() => /test/.test('this is a test')"),
		('Regex match', "() => 'abc123def'.match(/\\d+/)"),
		('Regex replace', "() => 'hello world'.replace(/world/, 'javascript')"),
	]

	# Run basic tests
	for test_name, js_code in tests:
		total += 1
		if await run_js_test(target, test_name, js_code):
			passed += 1

	# === PARAMETER TESTS ===

	param_tests = [
		('Single param', '(x) => x * 2', (21,)),
		('Two params', '(a, b) => a + b', (10, 5)),
		('Three params', '(a, b, c) => a * b + c', (2, 3, 4)),
		('String param', "(name) => 'Hello ' + name", ('World',)),
		('Array param', '(arr) => arr.length', ([1, 2, 3, 4],)),
		('Object param', '(obj) => obj.name', ({'name': 'test'},)),
		('Boolean param', "(flag) => flag ? 'yes' : 'no'", (True,)),
		('Null param', '(val) => val === null', (None,)),
		('Multiple types', '(str, num, bool) => `${str}-${num}-${bool}`', ('test', 42, True)),
	]

	for test_name, js_code, args in param_tests:
		total += 1
		if await run_js_test(target, test_name, js_code, *args):
			passed += 1

	# === COMPLEX JAVASCRIPT TESTS ===

	complex_tests = [
		# Control flow
		('If statement', "() => { if (true) return 'yes'; else return 'no'; }"),
		('For loop', '() => { let sum = 0; for (let i = 1; i <= 5; i++) sum += i; return sum; }'),
		('While loop', '() => { let i = 0, sum = 0; while (i < 3) { sum += i; i++; } return sum; }'),
		(
			'Switch statement',
			"() => { const x = 2; switch(x) { case 1: return 'one'; case 2: return 'two'; default: return 'other'; } }",
		),
		# Functions
		('Function declaration', '() => { function add(a, b) { return a + b; } return add(3, 4); }'),
		('Arrow function', '() => { const multiply = (a, b) => a * b; return multiply(6, 7); }'),
		('Closure', '() => { function outer(x) { return function(y) { return x + y; }; } return outer(5)(3); }'),
		('IIFE', "() => (function() { return 'immediate'; })()"),
		# Error handling
		('Try catch', "() => { try { JSON.parse('invalid'); } catch (e) { return 'caught error'; } }"),
		('Throw error', "() => { try { throw new Error('test'); } catch (e) { return e.message; } }"),
		# Advanced array operations
		('Array map', '() => [1, 2, 3].map(x => x * 2)'),
		('Array filter', '() => [1, 2, 3, 4, 5].filter(x => x % 2 === 0)'),
		('Array reduce', '() => [1, 2, 3, 4].reduce((sum, x) => sum + x, 0)'),
		('Array find', '() => [1, 2, 3, 4].find(x => x > 2)'),
		('Array some', '() => [1, 2, 3].some(x => x > 2)'),
		('Array every', '() => [2, 4, 6].every(x => x % 2 === 0)'),
		# String manipulation
		('Template literals', "() => { const name = 'World'; return `Hello ${name}!`; }"),
		('Multiline string', '() => `Line 1\nLine 2\nLine 3`'),
		('String split', "() => 'a,b,c,d'.split(',')"),
		# Object operations
		('Object destructuring', '() => { const obj = {a: 1, b: 2}; const {a, b} = obj; return a + b; }'),
		('Object spread', '() => { const obj1 = {a: 1}; const obj2 = {b: 2}; return {...obj1, ...obj2}; }'),
		('Object assign', '() => Object.assign({a: 1}, {b: 2})'),
		# Modern JS features
		('Array destructuring', '() => { const [a, b, c] = [1, 2, 3]; return a + b + c; }'),
		('Default parameters', '(x = 10, y = 20) => x + y', ()),
		('Rest parameters', '(...args) => args.length', (1, 2, 3, 4)),
		# Type checking
		('Typeof string', "() => typeof 'hello'"),
		('Typeof number', '() => typeof 42'),
		('Typeof boolean', '() => typeof true'),
		('Typeof object', '() => typeof {}'),
		('Typeof array', '() => typeof []'),
		('Array isArray', '() => Array.isArray([1, 2, 3])'),
		('Number isNaN', '() => Number.isNaN(NaN)'),
	]

	for test_name, js_code, *args in complex_tests:
		total += 1
		if await run_js_test(target, test_name, js_code, *(args[0] if args else ())):
			passed += 1

	# === EDGE CASES AND ERROR CONDITIONS ===

	edge_cases = [
		# String quoting issues
		('Single quotes', "() => 'It\\'s working'"),
		('Double quotes', '() => "He said \\"Hello\\""'),
		('Mixed quotes', '() => \'He said "Hello"\''),
		('Backticks', '() => `Template with \'single\' and "double" quotes`'),
		# Special characters
		('Unicode', "() => 'Hello 🌍 World'"),
		('Newlines', "() => 'Line 1\\nLine 2'"),
		('Tabs', "() => 'Col1\\tCol2'"),
		('Escape sequences', "() => 'Path: C:\\\\Users\\\\test'"),
		# Large data
		('Large array', '() => new Array(1000).fill(42).length'),
		('Large string', "() => 'x'.repeat(10000).length"),
		('Large object', '() => Object.keys(Object.fromEntries(Array.from({length: 100}, (_, i) => [i, i]))).length'),
		# Infinity and special numbers
		('Positive infinity', '() => Infinity'),
		('Negative infinity', '() => -Infinity'),
		('NaN', '() => NaN'),
		('Very large number', '() => Number.MAX_VALUE'),
		('Very small number', '() => Number.MIN_VALUE'),
	]

	for test_name, js_code, *args in edge_cases:
		total += 1
		if await run_js_test(target, test_name, js_code, *(args[0] if args else ())):
			passed += 1

	# === FAILURE TESTS (these should fail) ===

	failure_tests = [
		('Invalid syntax', '() => { invalid syntax', True),
		('Missing arrow', 'document.title', True),
		('Wrong format', "function() { return 'test'; }", True),
		('Empty string', '', True),
		('Just parentheses', '()', True),
		('No arrow function', "console.log('test')", True),
	]

	for test_name, js_code, should_fail in failure_tests:
		total += 1
		if await run_js_test(target, test_name, js_code, should_fail=should_fail):
			passed += 1

	# === BROWSER-SPECIFIC TESTS (with real page) ===

	print('\n🌐 LOADING REAL PAGE FOR BROWSER-SPECIFIC TESTS')
	web_target = await browser.newTarget('https://httpbin.org/html')
	await asyncio.sleep(3)  # Wait for page load

	browser_tests = [
		('Page title', '() => document.title'),
		('Page URL', '() => location.href'),
		('Body exists', '() => !!document.body'),
		('Body HTML', '() => document.body.innerHTML.length > 0'),
		('Query selector', "() => !!document.querySelector('body')"),
		('Get all elements', "() => document.querySelectorAll('*').length"),
		('Window object', '() => typeof window'),
		('Navigator user agent', "() => navigator.userAgent.includes('Chrome')"),
		('Screen dimensions', '() => screen.width > 0 && screen.height > 0'),
		('Local storage available', "() => typeof localStorage !== 'undefined'"),
		('Session storage available', "() => typeof sessionStorage !== 'undefined'"),
		('Console exists', "() => typeof console !== 'undefined'"),
	]

	for test_name, js_code in browser_tests:
		total += 1
		if await run_js_test(web_target, test_name, js_code):
			passed += 1

	# === PERFORMANCE TESTS ===

	print('\n⚡ PERFORMANCE TESTS')
	perf_tests = [
		('Fast execution', '() => 1 + 1'),
		('Medium computation', '() => Array.from({length: 1000}, (_, i) => i).reduce((sum, x) => sum + x, 0)'),
		('String processing', "() => 'test'.repeat(1000).split('').reverse().join('').length"),
	]

	for test_name, js_code in perf_tests:
		total += 1
		import time

		start_time = time.time()
		success = await run_js_test(web_target, test_name, js_code)
		duration = time.time() - start_time
		print(f'Duration: {duration:.3f}s')
		if success:
			passed += 1

	# === FINAL RESULTS ===

	print('\n' + '=' * 50)
	print('🧪 JAVASCRIPT EVALUATION TEST RESULTS')
	print('=' * 50)
	print(f'✅ Passed: {passed}/{total} ({passed / total * 100:.1f}%)')
	print(f'❌ Failed: {total - passed}/{total} ({(total - passed) / total * 100:.1f}%)')

	if passed == total:
		print('🎉 ALL TESTS PASSED!')
	elif passed / total >= 0.9:
		print('🟡 MOSTLY SUCCESSFUL - Some edge cases failed')
	else:
		print('🔴 SIGNIFICANT ISSUES - Many tests failed')

	await browser_session.stop()
	return passed, total


if __name__ == '__main__':
	asyncio.run(test_javascript_evaluation())
