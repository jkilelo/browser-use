"""
Test the exact LLM response format provided by the user.

This test validates that the specific format shown in the user's example works correctly
with all regex patterns preserved through the JavaScript processing pipeline.
"""

from browser_use.tools.code_processor import CodeProcessor


class TestUserExampleFormat:
	"""Test the exact user-provided example format"""

	def test_exact_user_example_format(self):
		"""Test the exact format from user's example with /\\n+/g regex"""

		# This is the exact format the user provided
		user_example = {
			'memory': "Ran search results page for 'climate change'. Plan: extract the first five article headlines from the NBC News search results and return them. If fewer than five returned, will scroll and fetch more next step.",
			'action': [
				{
					'execute_browser_use_code': {
						'code': """async def executor():
    js_code = \"\"\"() => {
        const nodes = Array.from(document.querySelectorAll('#content a'))
            .filter(a => a.closest('div') && a.innerText.trim().length>10);
        const texts = nodes.map(a=>a.innerText.replace(/\\n+/g,' ').trim()).slice(0,5);
        return JSON.stringify(texts);
    }\"\"\"
    result = await target.evaluate(js_code)
    return result
"""
					}
				}
			],
		}

		# Extract the code from the action
		code = user_example['action'][0]['execute_browser_use_code']['code']

		# Process it through our JavaScript fixing pipeline
		processed_code = CodeProcessor.fix_python_code_string_issues(code)

		# Critical assertion: the /\\n+/g pattern must be preserved exactly
		assert '/\\n+/g' in processed_code, 'The /\\n+/g regex pattern was not preserved!'
		assert '/n+/g' not in processed_code, 'The regex pattern was corrupted to /n+/g!'

		# Verify the CSS selector is also clean
		assert '#content a' in processed_code
		assert 'querySelectorAll(' in processed_code

		# Ensure no excessive escaping was introduced
		assert '\\\\\\\\' not in processed_code

		print('✅ User example format processed correctly with /\\n+/g preserved')

	def test_multiple_user_format_variations(self):
		"""Test variations of the user format with different regex patterns"""

		variations = [
			# Variation 1: Multiple regex patterns
			"""async def executor():
    js_code = \"\"\"() => {
        const content = document.body.innerText
            .replace(/\\n+/g, ' ')
            .replace(/\\s{2,}/g, ' ')
            .replace(/^\\s+|\\s+$/g, '');
        return content;
    }\"\"\"
    result = await target.evaluate(js_code)
    return result""",
			# Variation 2: Complex extraction with regex
			"""async def executor():
    js_code = \"\"\"() => {
        const headlines = Array.from(document.querySelectorAll('article h2'))
            .map(h => h.innerText
                .replace(/\\n+/g, ' ')
                .replace(/[\\u0000-\\u001F]/g, '')
                .trim()
            )
            .filter(text => text.length > 5 && /[a-zA-Z]/.test(text));
        return JSON.stringify(headlines);
    }\"\"\"
    result = await target.evaluate(js_code)
    return result""",
			# Variation 3: Form validation with regex
			"""async def executor():
    js_code = \"\"\"() => {
        const inputs = Array.from(document.querySelectorAll('input[type=\"email\"]'));
        const validEmails = inputs
            .map(input => input.value.replace(/^\\s+|\\s+$/g, ''))
            .filter(email => /^[\\w._%+-]+@[\\w.-]+\\.[A-Za-z]{2,}$/.test(email));
        return JSON.stringify(validEmails);
    }\"\"\"
    result = await target.evaluate(js_code)
    return result""",
			# Variation 4: Text processing with multiple regex patterns
			"""async def executor():
    js_code = \"\"\"() => {
        const text = document.querySelector('.content').innerText;
        const processed = text
            .replace(/\\r\\n/g, '\\n')
            .replace(/\\n{3,}/g, '\\n\\n')
            .replace(/\\t+/g, ' ')
            .replace(/ {2,}/g, ' ')
            .replace(/[\\u200B-\\u200D\\uFEFF]/g, '');
        const sentences = processed.split(/[.!?]+/).filter(s => s.trim().length > 10);
        return JSON.stringify(sentences.slice(0, 3));
    }\"\"\"
    result = await target.evaluate(js_code)
    return result""",
		]

		for i, variation in enumerate(variations, 1):
			processed = CodeProcessor.fix_python_code_string_issues(variation)

			# Count regex patterns in original vs processed
			import re

			original_regexes = re.findall(r'/[^/]+/[gimuy]*', variation)
			processed_regexes = re.findall(r'/[^/]+/[gimuy]*', processed)

			assert len(original_regexes) == len(processed_regexes), (
				f'Variation {i}: Regex count mismatch - original: {len(original_regexes)}, processed: {len(processed_regexes)}'
			)

			# Check specific patterns are preserved
			critical_patterns = ['/\\n+/g', '/\\s+/g', '/\\d+/g', '/[a-zA-Z]/', '/^\\s+|\\s+$/g']
			for pattern in critical_patterns:
				if pattern in variation:
					assert pattern in processed, f'Variation {i}: Pattern {pattern} not preserved'

			# Ensure CSS selectors are clean
			if 'input[type="email"]' in variation:
				assert 'input[type="email"]' in processed
			if 'article h2' in variation:
				assert 'article h2' in processed

		print(f'✅ All {len(variations)} user format variations processed correctly')

	def test_user_format_with_edge_cases(self):
		"""Test user format with edge case regex patterns that could break"""

		edge_cases = [
			# Forward slashes in regex
			"""async def executor():
    js_code = \"\"\"() => {
        const url = window.location.href.replace(/\\/+/g, '/');
        return url;
    }\"\"\"
    result = await target.evaluate(js_code)
    return result""",
			# Special character escaping
			"""async def executor():
    js_code = \"\"\"() => {
        const text = document.body.innerText;
        const escaped = text.replace(/[.*+?^${}()|\\[\\]\\\\]/g, '\\\\$&');
        return escaped;
    }\"\"\"
    result = await target.evaluate(js_code)
    return result""",
			# Mixed quotes in regex
			"""async def executor():
    js_code = \"\"\"() => {
        const content = document.body.innerText;
        const normalized = content
            .replace(/[""'']/g, '"')
            .replace(/[–—]/g, '-')
            .replace(/\\u2026/g, '...');
        return normalized;
    }\"\"\"
    result = await target.evaluate(js_code)
    return result""",
		]

		for i, edge_case in enumerate(edge_cases, 1):
			processed = CodeProcessor.fix_python_code_string_issues(edge_case)

			# These specific patterns should be preserved
			if '/\\/+/g' in edge_case:
				assert '/\\/+/g' in processed, f'Edge case {i}: Forward slash regex not preserved'

			if '/[.*+?^${}()|\\[\\]\\\\]/g' in edge_case:
				assert '/[.*+?^${}()|\\[\\]\\\\]/g' in processed, f'Edge case {i}: Special chars regex not preserved'

			# Unicode patterns might be converted but structure should remain
			if '/[""]/g' in edge_case or '/[""]/g' in processed:
				# Either original or converted form should exist
				assert '/[""]/g' in processed or '/[""]/g' in processed, f'Edge case {i}: Unicode quote regex not preserved'

		print(f'✅ All {len(edge_cases)} edge case user formats processed correctly')

	def test_real_world_news_extraction_format(self):
		"""Test real-world news headline extraction formats"""

		real_world_examples = [
			# BBC News format
			"""async def executor():
    js_code = \"\"\"() => {
        const headlines = Array.from(document.querySelectorAll('h3[class*=\"gs-c-promo-heading\"]'))
            .map(h => h.innerText
                .replace(/\\n+/g, ' ')
                .replace(/\\s{2,}/g, ' ')
                .replace(/^\\s+|\\s+$/g, '')
            )
            .filter(text => text.length > 10)
            .slice(0, 5);
        return JSON.stringify(headlines);
    }\"\"\"
    result = await target.evaluate(js_code)
    return result""",
			# CNN format
			"""async def executor():
    js_code = \"\"\"() => {
        const articles = Array.from(document.querySelectorAll('[data-module-name=\"story\"] h3'));
        const headlines = articles
            .map(h => h.innerText
                .replace(/\\n+/g, ' ')
                .replace(/[\\u0000-\\u001F\\u007F-\\u009F]/g, '')
                .replace(/\\u00A0/g, ' ')
                .trim()
            )
            .filter(text => text.length > 15 && !/^\\s*$/.test(text))
            .slice(0, 5);
        return JSON.stringify(headlines);
    }\"\"\"
    result = await target.evaluate(js_code)
    return result""",
			# Reuters format
			"""async def executor():
    js_code = \"\"\"() => {
        const stories = document.querySelectorAll('[data-testid=\"Body\"] a[data-testid=\"Heading\"]');
        const headlines = Array.from(stories)
            .map(a => a.innerText
                .replace(/\\n+/g, ' ')
                .replace(/\\s{2,}/g, ' ')
                .replace(/^\\s+|\\s+$/g, '')
                .replace(/[""'']/g, '"')
                .replace(/[–—]/g, '-')
            )
            .filter(text => text.length > 5 && /[a-zA-Z]/.test(text))
            .slice(0, 5);
        return JSON.stringify(headlines);
    }\"\"\"
    result = await target.evaluate(js_code)
    return result""",
		]

		for i, example in enumerate(real_world_examples, 1):
			processed = CodeProcessor.fix_python_code_string_issues(example)

			# All examples should preserve core regex patterns
			core_patterns = ['/\\n+/g', '/\\s{2,}/g', '/^\\s+|\\s+$/g']
			for pattern in core_patterns:
				if pattern in example:
					assert pattern in processed, f'Real-world example {i}: Core pattern {pattern} not preserved'

			# CSS selectors should be clean
			if 'data-module-name="story"' in example:
				assert 'data-module-name="story"' in processed
			if 'data-testid="Body"' in example:
				assert 'data-testid="Body"' in processed
			if 'data-testid="Heading"' in example:
				assert 'data-testid="Heading"' in processed

			# Advanced patterns
			if '/[a-zA-Z]/' in example:
				assert '/[a-zA-Z]/' in processed
			if '/^\\s*$/' in example:
				assert '/^\\s*$/' in processed

		print(f'✅ All {len(real_world_examples)} real-world news extraction formats processed correctly')
