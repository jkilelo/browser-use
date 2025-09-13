"""
Test JavaScript regex patterns by actually evaluating the JavaScript code.

These tests validate that processed JavaScript regex patterns execute correctly
using Node.js evaluation, simulating the browser environment.
"""

import json
import subprocess
import tempfile
from pathlib import Path

import pytest

from browser_use.tools.code_processor import CodeProcessor


class TestRegexJavaScriptEvaluation:
	"""Test regex patterns by evaluating JavaScript code"""

	def _execute_js(self, js_code: str) -> str:
		"""Execute JavaScript code using Node.js and return the result"""
		# Create a test HTML document in memory for DOM simulation
		full_js = f"""
// Mock DOM environment for testing
const document = {{
	querySelectorAll: function(selector) {{
		// Mock data based on selector
		if (selector === '#content a') {{
			return [
				{{
					innerText: 'Climate Change    Impact\\nOn Arctic Ice',
					closest: () => true
				}},
				{{
					innerText: 'Tech Giants\\n\\nReport Earnings\\t\\tToday',
					closest: () => true
				}},
				{{
					innerText: 'Sports: Team Wins   Championship',
					closest: () => true
				}},
				{{
					innerText: 'Breaking:   Major\\nEconomic\\tNews',
					closest: () => true
				}},
				{{
					innerText: 'Health Study Shows   Promising Results',
					closest: () => true
				}}
			];
		}}
		if (selector === '.contact-info') {{
			return [{{
				innerText: 'Contact us at news@example.com or call 123-456-7890. Also reach out via editor@newssite.org or 555-123-4567'
			}}];
		}}
		if (selector === '#test-form') {{
			return [{{
				querySelectorAll: function(innerSelector) {{
					if (innerSelector.includes('input')) {{
						return [
							{{ name: 'username', value: 'john_doe', type: 'text' }},
							{{ name: 'email', value: 'john@example.com', type: 'email' }},
							{{ name: 'phone', value: '123-456-7890', type: 'text' }},
							{{ name: 'backup', value: 'invalid-email', type: 'email' }}
						];
					}}
					return [];
				}}
			}}];
		}}
		return [];
	}},
	querySelector: function(selector) {{
		const results = this.querySelectorAll(selector);
		return results[0] || null;
	}},
	body: {{
		innerText: 'Climate Change Impact On Arctic Ice\\n\\nTech Giants Report Earnings Today\\n\\nContact us at news@example.com'
	}}
}};

// Mock Array.from for older environments
if (!Array.from) {{
	Array.from = function(arrayLike) {{
		return Array.prototype.slice.call(arrayLike);
	}};
}}

// Execute the test function
const testFunction = {js_code};
const result = testFunction();
console.log(JSON.stringify(result));
"""

		# Write to temporary file and execute with Node.js
		with tempfile.NamedTemporaryFile(mode='w', suffix='.js', delete=False) as f:
			f.write(full_js)
			temp_path = f.name

		try:
			# Execute with Node.js
			result = subprocess.run(['node', temp_path], capture_output=True, text=True, timeout=10)

			if result.returncode != 0:
				raise Exception(f'JavaScript execution failed: {result.stderr}')

			return result.stdout.strip()

		finally:
			# Clean up temp file
			Path(temp_path).unlink(missing_ok=True)

	def test_user_example_format_js_evaluation(self):
		"""Test the exact user example format with JavaScript evaluation"""

		# The exact user example JavaScript code (enhanced to also collapse multiple spaces)
		user_js_code = """() => {
	const nodes = Array.from(document.querySelectorAll('#content a'))
		.filter(a => a.closest('div') && a.innerText.trim().length>10);
	const texts = nodes.map(a=>a.innerText.replace(/\\n+/g,' ').replace(/\\s+/g,' ').trim()).slice(0,5);
	return JSON.stringify(texts);
}"""

		# Process through our JavaScript fixing pipeline
		processed_js = CodeProcessor.fix_js_code_for_evaluate(user_js_code)

		# Verify the regex pattern is preserved
		assert '/\\n+/g' in processed_js
		assert '/n+/g' not in processed_js

		# Execute the processed JavaScript
		result_json = self._execute_js(processed_js)
		headlines = json.loads(json.loads(result_json))

		# Verify the regex worked correctly
		assert len(headlines) == 5
		assert headlines[0] == 'Climate Change Impact On Arctic Ice'  # \\n should be replaced with space
		assert headlines[1] == 'Tech Giants Report Earnings Today'  # Multiple \\n and \\t should be handled
		assert '\\n' not in str(headlines)  # No literal newlines should remain

	def test_multiple_regex_patterns_js_evaluation(self):
		"""Test multiple regex patterns in JavaScript evaluation"""

		multi_regex_js = """() => {
	const content = document.body.innerText;
	const processed = content
		.replace(/\\n+/g, ' ')          // Replace newlines
		.replace(/\\s{2,}/g, ' ')       // Collapse multiple spaces
		.replace(/^\\s+|\\s+$/g, '')    // Trim start/end
		.replace(/[\\u0000-\\u001F]/g, ''); // Remove control chars
	return processed.substring(0, 200);
}"""

		# Process and execute
		processed_js = CodeProcessor.fix_js_code_for_evaluate(multi_regex_js)

		# Verify all regex patterns are preserved
		assert '/\\n+/g' in processed_js
		assert '/\\s{2,}/g' in processed_js
		assert '/^\\s+|\\s+$/g' in processed_js
		assert '/[\\u0000-\\u001F]/g' in processed_js

		result_json = self._execute_js(processed_js)
		processed_text = json.loads(result_json)

		# Verify regex operations worked
		assert '\\n' not in processed_text
		assert '  ' not in processed_text  # Multiple spaces should be collapsed
		assert not processed_text.startswith(' ')
		assert not processed_text.endswith(' ')

	def test_email_extraction_js_evaluation(self):
		"""Test email extraction regex pattern"""

		email_js = """() => {
	const text = document.querySelector('.contact-info').innerText;
	const emails = text.match(/[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\\.[a-zA-Z]{2,}/g) || [];
	return JSON.stringify(emails);
}"""

		processed_js = CodeProcessor.fix_js_code_for_evaluate(email_js)

		# Verify complex regex pattern is preserved
		assert '/[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\\.[a-zA-Z]{2,}/g' in processed_js

		result_json = self._execute_js(processed_js)
		emails = json.loads(json.loads(result_json))

		# Should extract emails correctly
		assert len(emails) == 2
		assert 'news@example.com' in emails
		assert 'editor@newssite.org' in emails

	def test_phone_number_extraction_js_evaluation(self):
		"""Test phone number extraction regex pattern"""

		phone_js = """() => {
	const text = document.querySelector('.contact-info').innerText;
	const phones = text.match(/\\d{3}-\\d{3}-\\d{4}/g) || [];
	return JSON.stringify(phones);
}"""

		processed_js = CodeProcessor.fix_js_code_for_evaluate(phone_js)

		# Verify regex pattern is preserved
		assert '/\\d{3}-\\d{3}-\\d{4}/g' in processed_js

		result_json = self._execute_js(processed_js)
		phones = json.loads(json.loads(result_json))

		# Should extract phone numbers correctly
		assert len(phones) == 2
		assert '123-456-7890' in phones
		assert '555-123-4567' in phones

	def test_form_validation_regex_js_evaluation(self):
		"""Test form validation with regex patterns"""

		form_js = """() => {
	const form = document.querySelector('#test-form');
	const inputs = Array.from(form.querySelectorAll('input[type="text"], input[type="email"]'));
	
	const validInputs = inputs.filter(input => {
		const value = input.value.replace(/^\\s+|\\s+$/g, '');
		if (input.type === 'email') {
			return /^[\\w._%+-]+@[\\w.-]+\\.[A-Za-z]{2,}$/.test(value);
		}
		return value.length > 0;
	});
	
	const results = validInputs.map(input => ({
		name: input.name,
		value: input.value.replace(/^\\s+|\\s+$/g, ''),
		type: input.type
	}));
	
	return JSON.stringify(results);
}"""

		processed_js = CodeProcessor.fix_js_code_for_evaluate(form_js)

		# Verify regex patterns are preserved
		assert '/^\\s+|\\s+$/g' in processed_js
		assert '/^[\\w._%+-]+@[\\w.-]+\\.[A-Za-z]{2,}$/' in processed_js

		result_json = self._execute_js(processed_js)
		valid_inputs = json.loads(json.loads(result_json))

		# Should validate correctly
		assert len(valid_inputs) == 3  # username, valid email, phone
		valid_names = [inp['name'] for inp in valid_inputs]
		assert 'username' in valid_names
		assert 'email' in valid_names
		assert 'phone' in valid_names
		assert 'backup' not in valid_names  # Invalid email filtered out

	def test_unicode_processing_js_evaluation(self):
		"""Test unicode character processing with regex"""

		unicode_js = """() => {
	const testStrings = [
		'Clean text\\u0000with\\u0001control\\u001Fchars',
		'Text with "smart quotes" and —dashes— and…ellipsis'
	];
	
	const results = testStrings.map((str, index) => {
		const cleaned = str
			.replace(/[\\u0000-\\u001F\\u007F-\\u009F]/g, '')  // Remove control chars
			.replace(/[""'']/g, '"')                          // Normalize quotes
			.replace(/[–—]/g, '-')                            // Normalize dashes
			.replace(/\\u2026/g, '...')                       // Ellipsis
			.replace(/\\u00A0/g, ' ');                        // Non-breaking space
		
		return {
			index: index,
			original: str,
			cleaned: cleaned,
			originalLength: str.length,
			cleanedLength: cleaned.length
		};
	});
	
	return JSON.stringify(results);
}"""

		processed_js = CodeProcessor.fix_js_code_for_evaluate(unicode_js)

		# Verify unicode regex patterns are preserved
		assert '/[\\u0000-\\u001F\\u007F-\\u009F]/g' in processed_js
		assert '/\\u2026/g' in processed_js
		assert '/\\u00A0/g' in processed_js

		result_json = self._execute_js(processed_js)
		results = json.loads(json.loads(result_json))

		assert len(results) == 2

		# Check first string (control chars removed)
		control_result = results[0]
		assert control_result['cleanedLength'] < control_result['originalLength']
		assert 'Clean textwithcontrolchars' in control_result['cleaned']

		# Check second string (quotes/dashes normalized)
		special_result = results[1]
		assert '"smart quotes"' in special_result['cleaned']
		assert '-dashes-' in special_result['cleaned']

	def test_edge_case_regex_js_evaluation(self):
		"""Test edge case regex patterns"""

		edge_case_js = """() => {
	const testString = 'path/to/file//double//slash and special chars: .*+?^${}()|[]\\\\';
	
	const results = {
		// Test forward slash normalization  
		normalizedPath: testString.replace(/\\/+/g, '/'),
		
		// Test special character escaping
		escapedSpecialChars: testString.replace(/[.*+?^${}()|\\[\\]\\\\]/g, '\\\\$&'),
		
		// Test word boundaries
		longWords: testString.match(/\\b\\w{4,}\\b/g) || [],
		
		// Test negative character class
		nonDigits: testString.match(/[^\\d]+/g) || []
	};
	
	return JSON.stringify(results);
}"""

		processed_js = CodeProcessor.fix_js_code_for_evaluate(edge_case_js)

		# Verify complex regex patterns are preserved
		assert '/\\/+/g' in processed_js
		assert '/[.*+?^${}()|\\[\\]\\\\]/g' in processed_js
		assert '/\\b\\w{4,}\\b/g' in processed_js
		assert '/[^\\d]+/g' in processed_js

		result_json = self._execute_js(processed_js)
		results = json.loads(json.loads(result_json))

		# Verify results
		assert results['normalizedPath'] == 'path/to/file/double/slash and special chars: .*+?^${}()|[]\\'
		assert '\\.' in results['escapedSpecialChars'] and '\\*' in results['escapedSpecialChars']
		assert len(results['longWords']) > 0
		assert len(results['nonDigits']) > 0

	def test_chained_regex_operations_js_evaluation(self):
		"""Test multiple chained regex operations"""

		chained_js = """() => {
	const text = 'Line 1\\nLine 2\\n\\nLine 3\\n\\n\\nLine 4\\t\\tExtra spaces   here';
	
	const processed = text
		.replace(/\\r\\n/g, '\\n')          // Normalize line endings
		.replace(/\\n{3,}/g, '\\n\\n')      // Limit consecutive newlines
		.replace(/\\t+/g, ' ')            // Replace tabs with spaces
		.replace(/ {2,}/g, ' ')          // Collapse multiple spaces
		.replace(/^\\s+/gm, '')          // Trim line starts
		.replace(/\\s+$/gm, '')          // Trim line ends
		.replace(/\\n\\s*\\n/g, '\\n\\n')   // Clean paragraph breaks
		.replace(/[\\u200B-\\u200D\\uFEFF]/g, ''); // Remove zero-width chars
	
	const analysis = {
		original: text,
		processed: processed,
		originalLines: text.split('\\n').length,
		processedLines: processed.split('\\n').length,
		steps: [
			text.replace(/\\n{3,}/g, '\\n\\n'),
			text.replace(/\\n{3,}/g, '\\n\\n').replace(/\\t+/g, ' '),
			text.replace(/\\n{3,}/g, '\\n\\n').replace(/\\t+/g, ' ').replace(/ {2,}/g, ' ')
		]
	};
	
	return JSON.stringify(analysis);
}"""

		processed_js = CodeProcessor.fix_js_code_for_evaluate(chained_js)

		# Verify all chained regex patterns are preserved
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
			assert pattern in processed_js, f'Pattern {pattern} not found in processed code'

		result_json = self._execute_js(processed_js)
		analysis = json.loads(json.loads(result_json))

		# Verify the chained operations worked
		assert analysis['processedLines'] <= analysis['originalLines']  # Lines should be reduced
		assert len(analysis['steps']) == 3  # All intermediate steps captured
		assert '\\t' not in analysis['processed']  # Tabs should be replaced
		assert '   ' not in analysis['processed']  # Multiple spaces should be collapsed

	@pytest.mark.skipif(
		subprocess.run(['which', 'node'], capture_output=True).returncode != 0,
		reason='Node.js not available for JavaScript execution testing',
	)
	def test_comprehensive_regex_preservation_js_evaluation(self):
		"""Comprehensive test of all regex patterns we support"""

		comprehensive_js = """() => {
	// Test data
	const testData = {
		emails: 'Contact: user@domain.com, admin@site.org, test123@example.co.uk',
		phones: 'Call 123-456-7890 or 555-123-4567 for support',  
		text: 'Line 1\\nLine 2\\n\\nLine 3\\t\\tTabbed\\n\\n\\nLine 4',
		mixed: 'Text123with456numbers and "quotes" —dashes— …ellipsis',
		special: 'Path/to//file///with\\\\backslashes and regex chars: .*+?^${}()|[]',
		unicode: 'Clean\\u0000text\\u0001with\\u001Fcontrol\\u00A0chars'
	};
	
	const results = {
		// Basic patterns
		emails: testData.emails.match(/[\\w._%+-]+@[\\w.-]+\\.[A-Za-z]{2,}/g) || [],
		phones: testData.phones.match(/\\d{3}-\\d{3}-\\d{4}/g) || [],
		numbers: testData.mixed.match(/\\d+/g) || [],
		
		// Text processing
		cleanText: testData.text
			.replace(/\\n+/g, ' ')
			.replace(/\\t+/g, ' ')
			.replace(/\\s{2,}/g, ' ')
			.replace(/^\\s+|\\s+$/g, ''),
		
		// Unicode processing  
		cleanUnicode: testData.unicode
			.replace(/[\\u0000-\\u001F]/g, '')
			.replace(/\\u00A0/g, ' '),
		
		// Special chars
		normalizedPath: testData.special.replace(/\\/+/g, '/'),
		escapedSpecial: testData.special.replace(/[.*+?^${}()|\\[\\]\\\\]/g, '\\\\$&'),
		
		// Advanced patterns
		longWords: testData.mixed.match(/\\b\\w{4,}\\b/g) || [],
		nonDigits: testData.mixed.match(/[^\\d]+/g) || [],
		
		// Quote normalization
		normalizedQuotes: testData.mixed
			.replace(/[""'']/g, '"')
			.replace(/[–—]/g, '-')
			.replace(/\\u2026/g, '...')
	};
	
	return JSON.stringify(results);
}"""

		processed_js = CodeProcessor.fix_js_code_for_evaluate(comprehensive_js)

		# Execute and verify all patterns work
		result_json = self._execute_js(processed_js)
		results = json.loads(json.loads(result_json))

		# Verify all operations succeeded
		assert len(results['emails']) == 3
		assert 'user@domain.com' in results['emails']
		assert 'admin@site.org' in results['emails']
		assert 'test123@example.co.uk' in results['emails']

		assert len(results['phones']) == 2
		assert '123-456-7890' in results['phones']
		assert '555-123-4567' in results['phones']

		assert len(results['numbers']) == 2
		assert '123' in results['numbers']
		assert '456' in results['numbers']

		assert 'Line 1 Line 2 Line 3 Tabbed Line 4' in results['cleanText']
		assert 'Cleantextwithcontrol chars' in results['cleanUnicode']
		assert 'Path/to/file/with\\backslashes' in results['normalizedPath']
		assert len(results['longWords']) > 0
		assert len(results['nonDigits']) > 0

		print(f'✅ Comprehensive regex test executed successfully with {len(results)} result categories')

	def test_python_code_string_issues_with_js_evaluation(self):
		"""Test the full Python code processing pipeline with JavaScript evaluation"""

		# The full Python code in LLM format
		python_code = """async def executor():
    js_code = \"\"\"() => {
        const nodes = Array.from(document.querySelectorAll('#content a'))
            .filter(a => a.closest('div') && a.innerText.trim().length>10);
        const processed = nodes.map(a => {
            return a.innerText
                .replace(/\\n+/g, ' ')
                .replace(/\\s{2,}/g, ' ')
                .replace(/^\\s+|\\s+$/g, '')
                .replace(/[\\u0000-\\u001F]/g, '');
        });
        const emails = processed.join(' ').match(/[\\w._%+-]+@[\\w.-]+\\.[A-Za-z]{2,}/g) || [];
        return JSON.stringify({
            headlines: processed.slice(0, 3),
            emails: emails,
            totalProcessed: processed.length
        });
    }\"\"\"
    result = await target.evaluate(js_code)
    return result
"""

		# Process the full Python code
		processed_python = CodeProcessor.fix_python_code_string_issues(python_code)

		# Extract the JavaScript from the processed Python code
		import re

		js_match = re.search(r'js_code = """(.*?)"""', processed_python, re.DOTALL)
		assert js_match, 'JavaScript code not found in processed Python'

		extracted_js = js_match.group(1)

		# Verify key regex patterns are preserved in the extracted JavaScript
		assert '/\\n+/g' in extracted_js
		assert '/\\s{2,}/g' in extracted_js
		assert '/^\\s+|\\s+$/g' in extracted_js
		assert '/[\\u0000-\\u001F]/g' in extracted_js
		assert '/[\\w._%+-]+@[\\w.-]+\\.[A-Za-z]{2,}/g' in extracted_js

		# Execute the JavaScript to verify it works
		result_json = self._execute_js(extracted_js)
		final_result = json.loads(json.loads(result_json))

		# Verify the full pipeline worked
		assert 'headlines' in final_result
		assert 'emails' in final_result
		assert 'totalProcessed' in final_result

		assert len(final_result['headlines']) == 3
		assert final_result['totalProcessed'] == 5

		# Headlines should be cleaned (no newlines, collapsed spaces, trimmed)
		for headline in final_result['headlines']:
			assert '\\n' not in headline
			assert '  ' not in headline  # No double spaces
			assert not headline.startswith(' ')
			assert not headline.endswith(' ')

		print('✅ Full Python-to-JavaScript processing pipeline executed successfully')
