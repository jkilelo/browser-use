Execute Browser Actor code using the browser-use actor library.

CRITICAL RULES - READ BEFORE WRITING CODE:

2. ONLY USE METHODS FROM THE "API Reference" SECTION BELOW
   - If a method is NOT listed in the API Reference, it DOES NOT EXIST
   - This is NOT Playwright, NOT Puppeteer, NOT Selenium
   - Do not assume methods exist just because they exist in other libraries

3. ALL METHODS ARE ASYNC - ALWAYS USE await
   - Every method call must be awaited: `await page.goto()`, `await element.click()`
   - Forgetting await causes "coroutine has no attribute" errors

4. CHECK THE API REFERENCE BEFORE EVERY METHOD CALL
   - Before writing `element.some_method()`, verify it exists in API Reference
   - If unsure, DON'T use it - only use documented methods

5. COMMON MISTAKES TO AVOID:
   - ❌ Writing long multi-step procedures (use other tools for workflows)
   - ❌ Using Playwright methods (e.g., `page.locator()`, `page.waitForSelector()`)
   - ❌ Using Puppeteer methods (e.g., `page.$()`, `page.$$()`)
   - ❌ Calling methods not in API Reference (e.g., `element.scroll()`, `page.bring_to_front()`)
   - ❌ Forgetting to await async methods
   - ❌ Treating response objects as they have properties like `.text` - check API Reference for correct access

<DOCS>
Browser Actor is a web automation library built on CDP (Chrome DevTools Protocol) that provides low-level browser automation capabilities within the browser-use ecosystem.

```
page = await browser.new_page("https://example.com")
pages = await browser.get_pages()
current_page = await browser.get_current_page()
```

```
page = await browser.new_page("https://example.com")
pages = await browser.get_pages()
await browser.switch_page(page)
await browser.close_page(page)

await page.goto("https://example.com")
await page.go_back()
await page.go_forward()
await page.reload()
```

```
elements = await page.get_elements_by_css_selector("input[type='text']")
buttons = await page.get_elements_by_css_selector("button.submit")

element = await page.get_element(backend_node_id=12345)

element = await page.get_element_by_prompt("search button", llm=your_llm)
element = await page.must_get_element_by_prompt("login form", llm=your_llm)
```

> Note: `get_elements_by_css_selector` returns immediately without waiting for visibility.

## Element Interactions

```
await element.click(button='left', click_count=1, modifiers=['Control'])
await element.fill("Hello World")  # Clears first, then types
await element.hover()
await element.focus()
await element.check()  # Toggle checkbox/radio
await element.select_option(["option1", "option2"])  # For dropdown/select
await element.drag_to(target_element)  # Drag and drop

value = await element.get_attribute("value")
box = await element.get_bounding_box()  # Returns BoundingBox or None
info = await element.get_basic_info()  # Comprehensive element info
```

## Mouse Operations

```
mouse = await page.mouse # IMPORTANT: THIS PROPERTY IS ASYNC (do not forget to use await)
await mouse.click(x=100, y=200, button='left', click_count=1)
await mouse.move(x=300, y=400, steps=1)
await mouse.down(button='left')  # Press button
await mouse.up(button='left')    # Release button
await mouse.scroll(x=0, y=100, delta_x=0, delta_y=-500)  # Scroll at coordinates
```

## Page Operations

```
result = await page.evaluate('() => document.title')  # Must use arrow function format
result = await page.evaluate('(x, y) => x + y', 10, 20)  # With arguments

await page.press("Control+A")  # Key combinations supported
await page.press("Escape")     # Single keys

url = await page.get_url()
title = await page.get_title()
```

```
# Content extraction using LLM
from pydantic import BaseModel

class ProductInfo(BaseModel):
    name: str
    price: float
    description: str

# Extract structured data from current page
products = await page.extract_content(
    "Find all products with their names, prices and descriptions",
    ProductInfo,
    llm=your_llm
)
```

## Core Classes

- Browser (aliased as BrowserSession
BrowserSession): Main browser session manager with tab operations
- Page: Represents a single browser tab or iframe for page-level operations
- Element: Individual DOM element for interactions and property access
- Mouse: Mouse operations within a page (click, move, scroll)

## API Reference

⚠️ THIS IS THE COMPLETE LIST OF AVAILABLE METHODS. NOTHING ELSE EXISTS.

### Browser Methods (Tab Management) - ALL ASYNC

Tab Operations:
async new_page(url: str | None = None) → Page - Create new tab (blank if url=None, or navigate to url)
async get_pages() → list[Page] - Get all available pages/tabs
async get_current_page() → Page | None - Get the currently focused page
async switch_page(page: Page | str) - Switch to page by object or ID
async close_page(page: Page | str) - Close page by object or ID

Important: Use `browser.new_page()`, `browser.get_pages()`, `browser.switch_page()`, etc. The browser object is available as `browser` in your code context.

---

### Page Methods (Page Operations) - ALL ASYNC

Element Finding:
async get_elements_by_css_selector(selector: str) → list[Element] - Find elements by CSS selector (returns immediately, doesn't wait)
async get_element(backend_node_id: int) → Element - Get element by backend node ID
async get_element_by_prompt(prompt: str, llm) → Element | None - AI-powered element finding (requires llm parameter)
async must_get_element_by_prompt(prompt: str, llm) → Element - AI element finding (raises if not found)

Navigation:
async goto(url: str) - Navigate this page to URL
async go_back() - Navigate back in history
async go_forward() - Navigate forward in history
async reload() - Reload the current page

JavaScript & Interaction:
async evaluate(page_function: str, *args) → str - Execute JavaScript (MUST use (...args) => {...} arrow function format)
async press(key: str) - Press key on page (supports "Control+A" format)

Page Info:
async get_url() → str - Get current page URL
async get_title() → str - Get current page title
async set_viewport_size(width: int, height: int) - Set viewport dimensions

Async Property:
await page.mouse → Mouse - Get mouse interface (MUST await this property)

⚠️ Playwright/Puppeteer methods like `page.locator()`, `page.$()`, `page.waitForSelector()`, `page.bring_to_front()` DO NOT EXIST

---

### Element Methods (DOM Interactions) - ALL ASYNC

Actions:
async click(button='left', click_count=1, modifiers=None) - Click element with options
async fill(text: str, clear_existing=True) - Fill input with text (clears first by default)
async hover() - Hover over element
async focus() - Focus the element
async check() - Toggle checkbox/radio button (clicks to change state)
async select_option(values: str | list[str]) - Select dropdown options
async drag_to(target: Element | Position, ...) - Drag to target element

Properties:
async get_attribute(name: str) → str | None - Get attribute value
async get_bounding_box() → BoundingBox | None - Get element position/size (returns dict with x, y, width, height)
async get_basic_info() → ElementInfo - Get comprehensive element information (returns dict with nodeId, nodeName, attributes, etc.)

⚠️ Element does NOT have: `.scroll()`, `.text`, `.text_content`, `.innerText` as properties
⚠️ To get text content: `await element.get_attribute('textContent')` or use `page.evaluate()`

---

### Mouse Methods (Coordinate-Based Operations) - ALL ASYNC

Mouse Operations:
async click(x: int, y: int, button='left', click_count=1) - Click at coordinates
async move(x: int, y: int, steps=1) - Move to coordinates
async down(button='left', click_count=1) - Press mouse button
async up(button='left', click_count=1) - Release mouse button
async scroll(x=0, y=0, delta_x=None, delta_y=None) - Scroll page at coordinates

⚠️ Elements do NOT have scroll() - use mouse.scroll() instead

---

### How to Access These Objects

In your code context, these are available:
```
browser  # BrowserSession - use for tab management
page     # Page - current page (or get via browser.get_current_page())
Element  # Class - instantiate via page.get_element() or page.get_elements_by_css_selector()
Mouse    # Class - get via: mouse = await page.mouse
llm      # LLM - use for AI-powered features like page.get_element_by_prompt("search button", llm=llm)
```

## Important Usage Notes

### This is Browser-Use Actor - NOT Other Libraries

browser-use/actor is its own library with its own API.

❌ Do NOT use:
- Playwright methods (`page.locator()`, `page.waitForSelector()`, `page.click()` without element, etc.)
- Puppeteer methods (`page.$()`, `page.$$()`, `page.evaluate()` with different signature, etc.)
- Selenium methods (`driver.find_element()`, etc.)

✅ Only use methods documented in the API Reference section above.

### Critical Method Restrictions

If a method is not in the API Reference, it does not exist:
- Element has NO `.scroll()` method - use `mouse.scroll()` or `page.evaluate()`
- Element has NO `.text` or `.text_content` properties - use `await element.get_attribute('textContent')`
- Page has NO `.locator()`, `.waitForSelector()`, `.bring_to_front()`, etc.

### Async Property Access

```
# ✅ CORRECT:
mouse = await page.mouse
await mouse.click(100, 200)

# ❌ WRONG:
mouse = page.mouse  # This is a coroutine, not a Mouse object
await mouse.click(100, 200)  # Will error: 'coroutine' object has no attribute 'click'
```

### Response Object Access

Methods like `get_bounding_box()` return dictionaries, not objects:

```
# ✅ CORRECT:
box = await element.get_bounding_box()
if box:
    x = box['x']  # Dictionary access
    width = box['width']

# ❌ WRONG:
box = await element.get_bounding_box()
x = box.x  # Will error if box is dict
```

### Element Finding

```
# get_elements_by_css_selector returns immediately (no waiting):
elements = await page.get_elements_by_css_selector("button")

# For dropdowns, use element.select_option(), NOT element.fill():
await element.select_option(["option1"])

# Form submission - click submit button or press Enter:
await page.press("Enter")
```

### JavaScript Code Guidelines

Critical: Use Triple-Quoted Strings to Avoid Escaping Issues

When writing JavaScript code, use Python triple-quoted strings to avoid escape character problems:

```
# ✅ CORRECT - Use triple quotes, allows you to use both ' and " freely:
js_code = '''() => {
    const button = document.querySelector("button[data-id='submit']");
    return button ? button.textContent : null;
}'''
result = await page.evaluate(js_code)

# ❌ WRONG - Double quotes with escaping gets messy:
result = await page.evaluate("() => document.querySelector(\"button\").click()")
```

JavaScript Format Requirements:
- MUST start with `(...args) =>` arrow function format
- Returns are automatic - last expression is returned
- Objects/arrays are JSON-stringified automatically
- Always returns string type

Examples:
```
# Simple expression:
js_code = '''() => document.title'''

# With arguments:
js_code = '''(selector) => document.querySelector(selector).textContent'''
result = await page.evaluate(js_code, "h1")

# Complex multi-line:
js_code = '''() => {
    const items = document.querySelectorAll('.item');
    return Array.from(items).map(i => i.textContent);
}'''
```

Why Triple Quotes?
- Allows natural use of both `'` and `"` in JavaScript without escaping
- Cleaner, more readable code
- Avoids JSON string escaping issues
- JavaScript can always use template literals `` ` `` if needed
</output_format>
</DOCS>

<RULES>
1. WRITE MINIMAL, SINGLE-ACTION CODE
   - Keep code SHORT: typically 3-8 lines, maximum 500 characters
   - Do ONE PRIMARY ACTION: click element, fill field, extract specific data
   - Use other tools for multi-step workflows - this is for focused operations only
   - If you need to do multiple things, call this tool multiple times with simple code each time

2. ONLY USE METHODS FROM API REFERENCE SECTION
   - Before writing ANY method call, verify it exists in API Reference above
   - Do not use methods from Playwright, Puppeteer, Selenium, or any other library
   - If method not in API Reference = method does not exist

3. Function Format:
   - Functions must start with `async def executor():` (no parameters)
   - All variables (browser, page, Element, Mouse, llm, asyncio, json, os) are available in context

4. JavaScript Code:
   - Use triple-quoted strings: `js_code = '''...'''`
   - Must use `(...args) => {...}` arrow function format
   - Use raw strings for regex: `r"pattern"`

5. Async Rules:
   - ALL API methods are async - must use `await`
   - `page.mouse` is async property: `mouse = await page.mouse`

6. Timing:
   - Add `await asyncio.sleep(0.5-1)` between actions for page loads
   - Keep it simple - if you need complex timing, use other tools

7. Before Submitting Code - Verify:
   ✓ Code does ONE thing (not a multi-step workflow)
   ✓ Every method used exists in API Reference
   ✓ All async methods are awaited
   ✓ No Playwright/Puppeteer methods used
   ✓ JavaScript uses triple quotes and arrow function format
   ✓ Using correct method names (snake_case: get_element, not getElement)
   ✓ Code is under 500 characters and focused on single action
</RULES>

<EXPECTED_OUTPUT>
Use `async def executor():` - all variables available in context:

Context: browser (BrowserSession), page (current open page), Element/Mouse classes, llm (for AI-powered features), asyncio/json/os available (no import needed).

Remember: Write MINIMAL, SINGLE-ACTION code. Do ONE thing, not multi-step workflows.
</EXPECTED_OUTPUT>
