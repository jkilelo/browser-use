"""
Test JavaScript regex patterns with actual browser execution.

These tests validate that regex patterns work correctly when executed in a real browser
through the browser-use action execution pipeline.
"""

import json

import pytest
from pytest_httpserver import HTTPServer
from werkzeug.wrappers import Response

from browser_use.browser.session import BrowserSession
from browser_use.tools.service import Tools
from browser_use.tools.views import BrowserUseCodeAction


class TestRegexBrowserExecution:
	"""Test regex patterns with actual browser execution"""

	@pytest.fixture
	async def browser_session(self):
		"""Create a browser session for testing"""
		session = BrowserSession()
		await session.start()
		yield session
		await session.stop()

	@pytest.fixture
	def httpserver(self):
		"""Create HTTP server with test HTML content for regex testing"""
		server = HTTPServer(host='127.0.0.1', port=0)
		server.start()

		# Test HTML with various content patterns for regex testing
		test_html = """
		<!DOCTYPE html>
		<html>
		<head><title>Regex Test Page - News Headlines</title></head>
		<body>
			<div id="content">
				<div class="article">
					<a href="/story1">Climate Change    Impact\nOn Arctic Ice</a>
				</div>
				<div class="article">
					<a href="/story2">Tech Giants\n\nReport Earnings\t\tToday</a>
				</div>
				<div class="article">
					<a href="/story3">Sports: Team Wins   Championship</a>
				</div>
				<div class="article">
					<a href="/story4">Breaking:   Major\nEconomic\tNews</a>
				</div>
				<div class="article">
					<a href="/story5">Health Study Shows   Promising Results</a>
				</div>
			</div>
			
			<div class="contact-info">
				<p>Contact us at news@example.com or call 123-456-7890</p>
				<p>Also reach out via editor@newssite.org or 555-123-4567</p>
			</div>
			
			<div class="content-processing">
				<p id="multiline-text">Line 1\nLine 2\n\nLine 3\n\n\nLine 4</p>
				<p id="special-chars">Text with "smart quotes" and —dashes— and…ellipsis</p>
				<p id="unicode-test">Clean text\u0000with\u0001control\u001fchars</p>
				<p id="mixed-content">Numbers 123, 456, 789 mixed with text</p>
				<input id="email-input" type="email" value="  test@domain.com  " />
				<input id="text-input" type="text" value="   spaces around text   " />
			</div>
			
			<form id="test-form">
				<input type="text" name="username" value="john_doe" />
				<input type="email" name="email" value="john@example.com" />
				<input type="text" name="phone" value="123-456-7890" />
				<input type="email" name="backup" value="invalid-email" />
			</form>
		</body>
		</html>
		"""

		server.expect_request('/test').respond_with_response(Response(test_html, content_type='text/html'))

		yield server
		server.stop()

	async def test_user_example_format_browser_execution(self, browser_session, httpserver):
		"""Test the exact user example format with browser execution"""

		tools = Tools()

		# Navigate to test page
		target = await browser_session.get_or_create_cdp_session()
		await target.send.Page.navigate(url=f'http://127.0.0.1:{httpserver.port}/test')
		await target.send.Page.loadEventFired()

		# The exact user example format
		user_example_code = """async def executor():
    js_code = \"\"\"() => {
        const nodes = Array.from(document.querySelectorAll('#content a'))
            .filter(a => a.closest('div') && a.innerText.trim().length>10);
        const texts = nodes.map(a=>a.innerText.replace(/\\n+/g,' ').trim()).slice(0,5);
        return JSON.stringify(texts);
    }\"\"\"
    result = await target.evaluate(js_code)
    return result
"""

		action = BrowserUseCodeAction(code=user_example_code)
		result = await tools.registry.execute_action(
			action_name='execute_browser_use_code', params=action.model_dump(), browser_session=browser_session
		)

		assert result.error is None, f'User example execution failed: {result.error}'

		# Parse the result
		data = json.loads(result.extracted_content)
		headlines = json.loads(data)

		# Verify the regex /\\n+/g worked correctly (newlines replaced with spaces)
		assert len(headlines) == 5
		assert 'Climate Change Impact On Arctic Ice' in headlines[0]
		assert 'Tech Giants Report Earnings Today' in headlines[1]  # \\n+ and \\t+ should be replaced
		assert '\\n' not in str(headlines)  # No literal newlines should remain

	async def test_multiple_regex_patterns_browser_execution(self, browser_session, httpserver):
		"""Test multiple regex patterns in one execution"""

		tools = Tools()

		target = await browser_session.get_or_create_cdp_session()
		await target.send.Page.navigate(url=f'http://127.0.0.1:{httpserver.port}/test')
		await target.send.Page.loadEventFired()

		# Test chained regex operations
		multi_regex_code = """async def executor():
    js_code = \"\"\"() => {
        const content = document.body.innerText;
        const processed = content
            .replace(/\\n+/g, ' ')          // Replace newlines
            .replace(/\\s{2,}/g, ' ')       // Collapse multiple spaces  
            .replace(/^\\s+|\\s+$/g, '')    // Trim start/end
            .replace(/[\\u0000-\\u001F]/g, ''); // Remove control chars
        return processed.substring(0, 200);
    }\"\"\"
    result = await target.evaluate(js_code)
    return result
"""

		action = BrowserUseCodeAction(code=multi_regex_code)
		result = await tools.registry.execute_action(
			action_name='execute_browser_use_code', params=action.model_dump(), browser_session=browser_session
		)

		assert result.error is None, f'Multi-regex execution failed: {result.error}'

		processed_text = json.loads(result.extracted_content)

		# Verify all regex patterns worked
		assert '\\n' not in processed_text  # Newlines removed
		assert '  ' not in processed_text  # Multiple spaces collapsed
		assert not processed_text.startswith(' ')  # Leading spaces trimmed
		assert not processed_text.endswith(' ')  # Trailing spaces trimmed

	async def test_email_extraction_browser_execution(self, browser_session, httpserver):
		"""Test email extraction regex pattern"""

		tools = Tools()

		target = await browser_session.get_or_create_cdp_session()
		await target.send.Page.navigate(url=f'http://127.0.0.1:{httpserver.port}/test')
		await target.send.Page.loadEventFired()

		email_extraction_code = """async def executor():
    js_code = \"\"\"() => {
        const text = document.querySelector('.contact-info').innerText;
        const emails = text.match(/[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\\.[a-zA-Z]{2,}/g) || [];
        return JSON.stringify(emails);
    }\"\"\"
    result = await target.evaluate(js_code)
    return result
"""

		action = BrowserUseCodeAction(code=email_extraction_code)
		result = await tools.registry.execute_action(
			action_name='execute_browser_use_code', params=action.model_dump(), browser_session=browser_session
		)

		assert result.error is None, f'Email extraction failed: {result.error}'

		data = json.loads(result.extracted_content)
		emails = json.loads(data)

		# Should find both emails
		assert len(emails) == 2
		assert 'news@example.com' in emails
		assert 'editor@newssite.org' in emails

	async def test_phone_number_extraction_browser_execution(self, browser_session, httpserver):
		"""Test phone number extraction regex pattern"""

		tools = Tools()

		target = await browser_session.get_or_create_cdp_session()
		await target.send.Page.navigate(url=f'http://127.0.0.1:{httpserver.port}/test')
		await target.send.Page.loadEventFired()

		phone_extraction_code = """async def executor():
    js_code = \"\"\"() => {
        const text = document.querySelector('.contact-info').innerText;
        const phones = text.match(/\\d{3}-\\d{3}-\\d{4}/g) || [];
        return JSON.stringify(phones);
    }\"\"\"
    result = await target.evaluate(js_code)
    return result
"""

		action = BrowserUseCodeAction(code=phone_extraction_code)
		result = await tools.registry.execute_action(
			action_name='execute_browser_use_code', params=action.model_dump(), browser_session=browser_session
		)

		assert result.error is None, f'Phone extraction failed: {result.error}'

		data = json.loads(result.extracted_content)
		phones = json.loads(data)

		# Should find both phone numbers
		assert len(phones) == 2
		assert '123-456-7890' in phones
		assert '555-123-4567' in phones

	async def test_form_validation_regex_browser_execution(self, browser_session, httpserver):
		"""Test form validation with regex patterns"""

		tools = Tools()

		target = await browser_session.get_or_create_cdp_session()
		await target.send.Page.navigate(url=f'http://127.0.0.1:{httpserver.port}/test')
		await target.send.Page.loadEventFired()

		form_validation_code = """async def executor():
    js_code = \"\"\"() => {
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
    }\"\"\"
    result = await target.evaluate(js_code)
    return result
"""

		action = BrowserUseCodeAction(code=form_validation_code)
		result = await tools.registry.execute_action(
			action_name='execute_browser_use_code', params=action.model_dump(), browser_session=browser_session
		)

		assert result.error is None, f'Form validation failed: {result.error}'

		data = json.loads(result.extracted_content)
		valid_inputs = json.loads(data)

		# Should find 3 valid inputs (username, valid email, phone)
		assert len(valid_inputs) == 3
		valid_names = [inp['name'] for inp in valid_inputs]
		assert 'username' in valid_names
		assert 'email' in valid_names
		assert 'phone' in valid_names
		assert 'backup' not in valid_names  # Invalid email should be filtered out

	async def test_unicode_processing_browser_execution(self, browser_session, httpserver):
		"""Test unicode character processing with regex"""

		tools = Tools()

		target = await browser_session.get_or_create_cdp_session()
		await target.send.Page.navigate(url=f'http://127.0.0.1:{httpserver.port}/test')
		await target.send.Page.loadEventFired()

		unicode_processing_code = """async def executor():
    js_code = \"\"\"() => {
        const elements = document.querySelectorAll('#unicode-test, #special-chars');
        const results = Array.from(elements).map(el => {
            const original = el.innerText;
            const cleaned = original
                .replace(/[\\u0000-\\u001F\\u007F-\\u009F]/g, '')  // Remove control chars
                .replace(/[""'']/g, '"')                          // Normalize quotes
                .replace(/[–—]/g, '-')                            // Normalize dashes
                .replace(/\\u2026/g, '...')                       // Ellipsis
                .replace(/\\u00A0/g, ' ');                        // Non-breaking space
            
            return {
                id: el.id,
                original: original,
                cleaned: cleaned,
                originalLength: original.length,
                cleanedLength: cleaned.length
            };
        });
        
        return JSON.stringify(results);
    }\"\"\"
    result = await target.evaluate(js_code)
    return result
"""

		action = BrowserUseCodeAction(code=unicode_processing_code)
		result = await tools.registry.execute_action(
			action_name='execute_browser_use_code', params=action.model_dump(), browser_session=browser_session
		)

		assert result.error is None, f'Unicode processing failed: {result.error}'

		data = json.loads(result.extracted_content)
		results = json.loads(data)

		assert len(results) == 2

		# Check unicode-test element (should have control chars removed)
		unicode_result = next(r for r in results if r['id'] == 'unicode-test')
		assert unicode_result['cleanedLength'] < unicode_result['originalLength']
		assert 'Clean textwithcontrolchars' in unicode_result['cleaned']

		# Check special-chars element (should have quotes/dashes normalized)
		special_result = next(r for r in results if r['id'] == 'special-chars')
		assert '"smart quotes"' in special_result['cleaned']
		assert '-dashes-' in special_result['cleaned']
		assert '...' in special_result['cleaned']

	async def test_complex_news_extraction_browser_execution(self, browser_session, httpserver):
		"""Test complex news headline extraction like real-world usage"""

		tools = Tools()

		target = await browser_session.get_or_create_cdp_session()
		await target.send.Page.navigate(url=f'http://127.0.0.1:{httpserver.port}/test')
		await target.send.Page.loadEventFired()

		news_extraction_code = """async def executor():
    js_code = \"\"\"() => {
        const articles = Array.from(document.querySelectorAll('.article a'));
        const headlines = articles
            .map(a => a.innerText
                .replace(/\\n+/g, ' ')                    // Replace newlines
                .replace(/\\t+/g, ' ')                    // Replace tabs
                .replace(/\\s{2,}/g, ' ')                 // Collapse spaces
                .replace(/^\\s+|\\s+$/g, '')              // Trim
                .replace(/[\\u0000-\\u001F]/g, '')        // Remove control chars
            )
            .filter(text => text.length > 10 && /[a-zA-Z]/.test(text))
            .slice(0, 5);
        
        // Also extract numbers for analysis
        const numberAnalysis = headlines.map(headline => {
            const numbers = headline.match(/\\d+/g) || [];
            return {
                headline: headline,
                numbers: numbers,
                wordCount: headline.split(/\\s+/).length
            };
        });
        
        return JSON.stringify({
            headlines: headlines,
            analysis: numberAnalysis,
            totalCount: headlines.length
        });
    }\"\"\"
    result = await target.evaluate(js_code)
    return result
"""

		action = BrowserUseCodeAction(code=news_extraction_code)
		result = await tools.registry.execute_action(
			action_name='execute_browser_use_code', params=action.model_dump(), browser_session=browser_session
		)

		assert result.error is None, f'News extraction failed: {result.error}'

		data = json.loads(result.extracted_content)
		news_data = json.loads(data)

		headlines = news_data['headlines']
		analysis = news_data['analysis']

		# Should extract all 5 headlines
		assert len(headlines) == 5
		assert news_data['totalCount'] == 5

		# Verify specific headlines are cleaned properly
		climate_headline = next(h for h in headlines if 'Climate Change' in h)
		assert 'Climate Change Impact On Arctic Ice' == climate_headline

		tech_headline = next(h for h in headlines if 'Tech Giants' in h)
		assert 'Tech Giants Report Earnings Today' == tech_headline

		# Verify analysis structure
		assert len(analysis) == 5
		for item in analysis:
			assert 'headline' in item
			assert 'numbers' in item
			assert 'wordCount' in item
			assert item['wordCount'] > 0

	async def test_input_processing_browser_execution(self, browser_session, httpserver):
		"""Test input field processing with regex patterns"""

		tools = Tools()

		target = await browser_session.get_or_create_cdp_session()
		await target.send.Page.navigate(url=f'http://127.0.0.1:{httpserver.port}/test')
		await target.send.Page.loadEventFired()

		input_processing_code = """async def executor():
    js_code = \"\"\"() => {
        const inputs = document.querySelectorAll('#email-input, #text-input');
        const results = Array.from(inputs).map(input => {
            const originalValue = input.value;
            const trimmedValue = originalValue.replace(/^\\s+|\\s+$/g, '');
            
            // For email inputs, also validate
            let isValid = true;
            if (input.type === 'email') {
                isValid = /^[\\w._%+-]+@[\\w.-]+\\.[A-Za-z]{2,}$/.test(trimmedValue);
            }
            
            return {
                id: input.id,
                type: input.type,
                original: originalValue,
                trimmed: trimmedValue,
                originalLength: originalValue.length,
                trimmedLength: trimmedValue.length,
                isValid: isValid
            };
        });
        
        return JSON.stringify(results);
    }\"\"\"
    result = await target.evaluate(js_code)
    return result
"""

		action = BrowserUseCodeAction(code=input_processing_code)
		result = await tools.registry.execute_action(
			action_name='execute_browser_use_code', params=action.model_dump(), browser_session=browser_session
		)

		assert result.error is None, f'Input processing failed: {result.error}'

		data = json.loads(result.extracted_content)
		results = json.loads(data)

		assert len(results) == 2

		# Check email input
		email_result = next(r for r in results if r['id'] == 'email-input')
		assert email_result['trimmed'] == 'test@domain.com'
		assert email_result['trimmedLength'] < email_result['originalLength']
		assert email_result['isValid'] is True

		# Check text input
		text_result = next(r for r in results if r['id'] == 'text-input')
		assert email_result['trimmed'] == 'test@domain.com'
		assert text_result['trimmedLength'] < text_result['originalLength']

	async def test_edge_case_regex_browser_execution(self, browser_session, httpserver):
		"""Test edge case regex patterns that could break"""

		tools = Tools()

		target = await browser_session.get_or_create_cdp_session()
		await target.send.Page.navigate(url=f'http://127.0.0.1:{httpserver.port}/test')
		await target.send.Page.loadEventFired()

		edge_case_code = """async def executor():
    js_code = \"\"\"() => {
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
    }\"\"\"
    result = await target.evaluate(js_code)
    return result
"""

		action = BrowserUseCodeAction(code=edge_case_code)
		result = await tools.registry.execute_action(
			action_name='execute_browser_use_code', params=action.model_dump(), browser_session=browser_session
		)

		assert result.error is None, f'Edge case execution failed: {result.error}'

		data = json.loads(result.extracted_content)
		results = json.loads(data)

		# Verify forward slash normalization
		assert results['normalizedPath'] == 'path/to/file/double/slash and special chars: .*+?^${}()|[]\\\\'

		# Verify special char escaping
		assert '\\\\.*' in results['escapedSpecialChars']
		assert '\\\\+' in results['escapedSpecialChars']

		# Verify word boundaries found long words
		assert len(results['longWords']) > 0
		assert any(len(word) >= 4 for word in results['longWords'])

		# Verify non-digits extraction
		assert len(results['nonDigits']) > 0
