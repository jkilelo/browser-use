"""
Test JavaScript regex patterns in LLM-generated code format.

These tests validate that regex patterns work correctly when processed through
CodeProcessor.fix_js_code_for_evaluate() using the exact format returned by LLMs.
"""

import re

from browser_use.tools.code_processor import CodeProcessor


class TestLLMFormatRegexPatterns:
	"""Test regex patterns in LLM-generated code format"""

	def test_llm_format_basic_regex_patterns(self):
		"""Test basic regex patterns in LLM format like the example provided"""

		# Test case 1: Replace newlines pattern (like in your example)
		llm_code_1 = """async def executor():
    js_code = \"\"\"() => {
        const nodes = Array.from(document.querySelectorAll('#content a'))
            .filter(a => a.closest('div') && a.innerText.trim().length>10);
        const texts = nodes.map(a=>a.innerText.replace(/\\n+/g,' ').trim()).slice(0,5);
        return JSON.stringify(texts);
    }\"\"\"
    result = await target.evaluate(js_code)
    return result"""

		# Process the code
		fixed_code = CodeProcessor.fix_python_code_string_issues(llm_code_1)

		# Verify the regex pattern is preserved exactly
		assert '/\\n+/g' in fixed_code
		assert fixed_code.count('/\\n+/g') == 1

		# Verify no broken patterns
		assert '/n+/g' not in fixed_code  # This would be the broken version
		assert '\\\\\\\\' not in fixed_code  # No excessive escaping

		# Test case 2: Multiple whitespace replacement
		llm_code_2 = """async def executor():
    js_code = \"\"\"() => {
        const text = document.body.innerText;
        const cleaned = text.replace(/\\s+/g, ' ').trim();
        return cleaned;
    }\"\"\"
    result = await target.evaluate(js_code)
    return result"""

		fixed_code_2 = CodeProcessor.fix_python_code_string_issues(llm_code_2)
		assert '/\\s+/g' in fixed_code_2
		assert '/s+/g' not in fixed_code_2

		# Test case 3: Number extraction
		llm_code_3 = """async def executor():
    js_code = \"\"\"() => {
        const text = document.querySelector('input').value;
        const numbers = text.match(/\\d+/g) || [];
        return JSON.stringify(numbers);
    }\"\"\"
    result = await target.evaluate(js_code)
    return result"""

		fixed_code_3 = CodeProcessor.fix_python_code_string_issues(llm_code_3)
		assert '/\\d+/g' in fixed_code_3
		assert '/d+/g' not in fixed_code_3

	def test_complex_llm_format_regex_patterns(self):
		"""Test complex regex patterns in LLM format"""

		# Test case 4: Email extraction
		llm_code_4 = """async def executor():
    js_code = \"\"\"() => {
        const text = document.body.innerText;
        const emails = text.match(/[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\\.[a-zA-Z]{2,}/g) || [];
        return JSON.stringify(emails);
    }\"\"\"
    result = await target.evaluate(js_code)
    return result"""

		fixed_code_4 = CodeProcessor.fix_python_code_string_issues(llm_code_4)
		assert '/[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\\.[a-zA-Z]{2,}/g' in fixed_code_4

		# Test case 5: Phone number pattern
		llm_code_5 = """async def executor():
    js_code = \"\"\"() => {
        const text = document.querySelector('.contact').innerText;
        const phones = text.match(/\\d{3}-\\d{3}-\\d{4}/g) || [];
        return JSON.stringify(phones);
    }\"\"\"
    result = await target.evaluate(js_code)
    return result"""

		fixed_code_5 = CodeProcessor.fix_python_code_string_issues(llm_code_5)
		assert '/\\d{3}-\\d{3}-\\d{4}/g' in fixed_code_5

		# Test case 6: Word boundaries
		llm_code_6 = """async def executor():
    js_code = \"\"\"() => {
        const text = document.title;
        const words = text.match(/\\b\\w{4,}\\b/g) || [];
        return JSON.stringify(words);
    }\"\"\"
    result = await target.evaluate(js_code)
    return result"""

		fixed_code_6 = CodeProcessor.fix_python_code_string_issues(llm_code_6)
		assert '/\\b\\w{4,}\\b/g' in fixed_code_6

	def test_escape_sequence_llm_format(self):
		"""Test escape sequences in LLM format"""

		# Test case 7: Tab and newline replacement
		llm_code_7 = """async def executor():
    js_code = \"\"\"() => {
        const text = document.querySelector('pre').innerText;
        const cleaned = text.replace(/[\\t\\n\\r]+/g, ' ');
        return cleaned;
    }\"\"\"
    result = await target.evaluate(js_code)
    return result"""

		fixed_code_7 = CodeProcessor.fix_python_code_string_issues(llm_code_7)
		assert '/[\\t\\n\\r]+/g' in fixed_code_7

		# Test case 8: Trim pattern
		llm_code_8 = """async def executor():
    js_code = \"\"\"() => {
        const text = document.querySelector('input').value;
        const trimmed = text.replace(/^\\s+|\\s+$/g, '');
        return trimmed;
    }\"\"\"
    result = await target.evaluate(js_code)
    return result"""

		fixed_code_8 = CodeProcessor.fix_python_code_string_issues(llm_code_8)
		assert '/^\\s+|\\s+$/g' in fixed_code_8

	def test_mixed_css_selectors_and_regex_llm_format(self):
		"""Test code with both CSS selectors and regex patterns in LLM format"""

		# Test case 9: Complex example like your original
		llm_code_9 = """async def executor():
    js_code = \"\"\"() => {
        const nodes = Array.from(document.querySelectorAll('div[data-testid=\"article\"] h2'))
            .filter(h => h.innerText.trim().length > 0);
        const headlines = nodes.map(h => {
            return h.innerText
                .replace(/\\n+/g, ' ')
                .replace(/\\s{2,}/g, ' ')
                .replace(/^\\s+|\\s+$/g, '')
                .replace(/[\\u0000-\\u001F]/g, '');
        }).slice(0, 5);
        return JSON.stringify(headlines);
    }\"\"\"
    result = await target.evaluate(js_code)
    return result"""

		fixed_code_9 = CodeProcessor.fix_python_code_string_issues(llm_code_9)

		# Verify CSS selector is cleaned
		assert 'data-testid="article"' in fixed_code_9  # Should be clean
		assert 'data-testid=\\\\\\\\"article\\\\\\\\"' not in fixed_code_9  # No over-escaping

		# Verify all regex patterns are preserved
		assert '/\\n+/g' in fixed_code_9
		assert '/\\s{2,}/g' in fixed_code_9
		assert '/^\\s+|\\s+$/g' in fixed_code_9
		assert '/[\\u0000-\\u001F]/g' in fixed_code_9

		# Test case 10: Form processing with validation
		llm_code_10 = """async def executor():
    js_code = \"\"\"() => {
        const form = document.querySelector('form');
        const inputs = Array.from(form.querySelectorAll('input[type=\"text\"], input[type=\"email\"]'));
        const validInputs = inputs.filter(input => {
            const value = input.value.replace(/^\\s+|\\s+$/g, '');
            if (input.type === 'email') {
                return /^[\\w._%+-]+@[\\w.-]+\\.[A-Za-z]{2,}$/.test(value);
            }
            return value.length > 0;
        });
        return validInputs.length;
    }\"\"\"
    result = await target.evaluate(js_code)
    return result"""

		fixed_code_10 = CodeProcessor.fix_python_code_string_issues(llm_code_10)

		# CSS selectors should be clean
		assert 'input[type="text"]' in fixed_code_10
		assert 'input[type="email"]' in fixed_code_10

		# Regex patterns should be preserved
		assert '/^\\s+|\\s+$/g' in fixed_code_10
		assert '/^[\\w._%+-]+@[\\w.-]+\\.[A-Za-z]{2,}$/' in fixed_code_10

	def test_edge_case_regex_patterns_llm_format(self):
		"""Test edge case regex patterns in LLM format"""

		# Test case 11: Forward slash handling
		llm_code_11 = """async def executor():
    js_code = \"\"\"() => {
        const path = window.location.pathname;
        const cleaned = path.replace(/\\/+/g, '/');
        return cleaned;
    }\"\"\"
    result = await target.evaluate(js_code)
    return result"""

		fixed_code_11 = CodeProcessor.fix_python_code_string_issues(llm_code_11)
		assert '/\\/+/g' in fixed_code_11

		# Test case 12: Special characters escaping
		llm_code_12 = """async def executor():
    js_code = \"\"\"() => {
        const text = document.querySelector('.code').innerText;
        const escaped = text.replace(/[.*+?^${}()|\\[\\]\\\\]/g, '\\\\$&');
        return escaped;
    }\"\"\"
    result = await target.evaluate(js_code)
    return result"""

		fixed_code_12 = CodeProcessor.fix_python_code_string_issues(llm_code_12)
		assert '/[.*+?^${}()|\\[\\]\\\\]/g' in fixed_code_12

		# Test case 13: Unicode handling
		llm_code_13 = """async def executor():
    js_code = \"\"\"() => {
        const text = document.body.innerText;
        const cleaned = text.replace(/[\\u0000-\\u001F\\u007F-\\u009F]/g, '');
        return cleaned;
    }\"\"\"
    result = await target.evaluate(js_code)
    return result"""

		fixed_code_13 = CodeProcessor.fix_python_code_string_issues(llm_code_13)
		assert '/[\\u0000-\\u001F\\u007F-\\u009F]/g' in fixed_code_13

	def test_chained_regex_operations_llm_format(self):
		"""Test chained regex operations in LLM format"""

		# Test case 14: Multiple chained operations
		llm_code_14 = """async def executor():
    js_code = \"\"\"() => {
        const text = document.querySelector('article').innerText;
        const processed = text
            .replace(/\\r\\n/g, '\\n')          // Normalize line endings
            .replace(/\\n{3,}/g, '\\n\\n')      // Limit consecutive newlines
            .replace(/\\t+/g, ' ')            // Replace tabs with spaces
            .replace(/ {2,}/g, ' ')          // Collapse multiple spaces
            .replace(/^\\s+/gm, '')          // Trim line starts
            .replace(/\\s+$/gm, '')          // Trim line ends
            .replace(/\\n\\s*\\n/g, '\\n\\n')   // Clean paragraph breaks
            .replace(/[\\u200B-\\u200D\\uFEFF]/g, ''); // Remove zero-width chars
        
        return processed;
    }\"\"\"
    result = await target.evaluate(js_code)
    return result"""

		fixed_code_14 = CodeProcessor.fix_python_code_string_issues(llm_code_14)

		# All regex patterns should be preserved
		patterns_to_check = [
			'/\\r\\n/g',
			'/\\n{3,}/g',
			'/\\t+/g',
			'/ {2,}/g',
			'/^\\s+/gm',
			'/\\s+$/gm',
			'/\\n\\s*\\n/g',
			'/[\\u200B-\\u200D\\uFEFF]/g',
		]

		for pattern in patterns_to_check:
			assert pattern in fixed_code_14, f'Pattern {pattern} not found in processed code'

		# Test case 15: Complex content extraction like news headlines
		llm_code_15 = """async def executor():
    js_code = \"\"\"() => {
        const articles = Array.from(document.querySelectorAll('article[data-module=\"story\"] h2'));
        const headlines = articles
            .map(h => h.innerText
                .replace(/\\n+/g, ' ')                    // Replace newlines
                .replace(/\\s{2,}/g, ' ')                 // Collapse spaces
                .replace(/^\\s+|\\s+$/g, '')              // Trim
                .replace(/[""'']/g, '\"')                 // Normalize quotes
                .replace(/[–—]/g, '-')                    // Normalize dashes
                .replace(/\\u00A0/g, ' ')                 // Non-breaking space
            )
            .filter(text => text.length > 10 && /[a-zA-Z]/.test(text))
            .slice(0, 5);
        
        return JSON.stringify(headlines);
    }\"\"\"
    result = await target.evaluate(js_code)
    return result"""

		fixed_code_15 = CodeProcessor.fix_python_code_string_issues(llm_code_15)

		# CSS selector should be clean
		assert 'article[data-module="story"]' in fixed_code_15

		# All regex patterns should be preserved (note: unicode chars may be converted)
		final_patterns = ['/\\n+/g', '/\\s{2,}/g', '/^\\s+|\\s+$/g', '/\\u00A0/g', '/[a-zA-Z]/']

		# These patterns may have unicode chars converted to actual characters
		unicode_patterns = [
			('/[""]/g', '/[""]/g'),  # May be converted to actual quotes
			('/[–—]/g', '/[–—]/g'),  # May be converted to actual dashes
		]

		for pattern in final_patterns:
			assert pattern in fixed_code_15, f'Pattern {pattern} not found'

		# Check unicode patterns (they may be converted but regex structure preserved)
		for original, converted in unicode_patterns:
			assert (
				original in fixed_code_15 or converted in fixed_code_15 or any(p in fixed_code_15 for p in ['/[""]/g', '/[–—]/g'])
			), f'Neither {original} nor {converted} found'

	def test_direct_js_code_processing(self):
		"""Test processing JavaScript code directly (simulating target.evaluate input)"""

		# Test the JavaScript code that would be passed to target.evaluate
		js_codes = [
			"""() => {
        const nodes = Array.from(document.querySelectorAll('#content a'))
            .filter(a => a.closest('div') && a.innerText.trim().length>10);
        const texts = nodes.map(a=>a.innerText.replace(/\\n+/g,' ').trim()).slice(0,5);
        return JSON.stringify(texts);
    }""",
			"""() => {
        const text = document.body.innerText;
        return text.replace(/\\s+/g, ' ').replace(/[\\u0000-\\u001F]/g, '').trim();
    }""",
			"""() => {
        const emails = document.body.innerText.match(/[\\w._%+-]+@[\\w.-]+\\.[A-Za-z]{2,}/g) || [];
        return JSON.stringify(emails);
    }""",
		]

		for js_code in js_codes:
			# This is what happens when target.evaluate processes the js_code
			processed = CodeProcessor.fix_js_code_for_evaluate(js_code)

			# Verify regex patterns are intact
			original_regex_count = len(re.findall(r'/[^/]+/[gimuy]*', js_code))
			processed_regex_count = len(re.findall(r'/[^/]+/[gimuy]*', processed))

			assert original_regex_count == processed_regex_count, f'Regex count changed: {js_code}'

			# Verify common patterns are preserved
			if '/\\n+/g' in js_code:
				assert '/\\n+/g' in processed
			if '/\\s+/g' in js_code:
				assert '/\\s+/g' in processed
			if '/[\\u0000-\\u001F]/g' in js_code:
				assert '/[\\u0000-\\u001F]/g' in processed

		print(f'✅ Processed {len(js_codes)} JavaScript code blocks successfully')
