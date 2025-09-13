# Browser Actor

Browser Actor is a web automation library built directly on CDP.

## Usage

```python
from cdp_use import CDPClient
from browser_use.actor import Browser, Target, Element, Mouse

# Create client and browser
client = CDPClient(ws_url)
browser = Browser(client)
```

```python
# Get targets (multiple ways)
target = await browser.newTarget()  # Create blank tab
target = await browser.newTarget("https://example.com")  # Create tab with URL
targets = await browser.getTargets()  # Get all existing tabs

# Navigate target to URL
await target.goto("https://example.com")

await browser.closeTarget(target)
```

```python
# Find elements by CSS selector
elements = await target.getElementsByCSSSelector("input[type='text']")
buttons = await target.getElementsByCSSSelector("button.submit")

# Get element by backend node ID
element = await target.getElement(backend_node_id=12345)
```

Unlike other libraries, the native implementation for `getElementsByCSSSelector` does not support waiting for the element to be visible.

```python
# Element actions
await element.click(button='left', click_count=1, modifiers=['Control'])
await element.fill("Hello World") 
await element.hover()
await element.focus()
await element.check() 
await element.selectOption(["option1", "option2"])

# Element properties  
value = await element.getAttribute("value")
box = await element.getBoundingBox()
info = await element.getBasicInfo()
```

```python
# Mouse operations
# 🚨 CRITICAL: Always await coroutines first before calling methods
mouse = await target.mouse  # Await the coroutine first
await mouse.click(x=100, y=200, button='left')  # Then call methods
await mouse.move(x=300, y=400)
```

```python
# Target operations
await target.scroll(x=0, y=100, delta_y=-500) # x,y (coordinates to scroll on), delta_y (how much to scroll)
await target.press("Control+A")  # Key combinations supported
await target.press("Escape")
await target.setViewportSize(width=1920, height=1080)
await target.reload()
page_screenshot = await target.screenshot()  # JPEG by default
page_png = await target.screenshot(format="png")

# JavaScript evaluation - 🚨 USE VARIABLES ONLY
**🚨 NEVER inline JavaScript - ALWAYS use separate variables**
**🎯 SINGLE STANDARD: Always use triple single quotes (''') with double quotes inside JavaScript**

**✅ SINGLE STANDARD PATTERN:**
```python
# 🎯 ALWAYS use triple single quotes + double quotes inside JavaScript
js_code = '''() => document.body.innerText'''
text = await target.evaluate(js_code)

# Complex JavaScript - ALWAYS follow this pattern
js_click = '''() => {
    const btn = document.querySelector("#submit-btn");
    const result = btn ? "clicked" : "not found";
    if (btn) btn.click();
    return result;
}'''
result = await target.evaluate(js_click)
```

**🚨 SINGLE QUOTE STANDARD:**
```python
# ✅ ALWAYS use this pattern (prevents ALL syntax errors):
js = '''() => {
    const element = document.querySelector("#my-id");
    const attr = element.getAttribute("data-value");
    return "success";
}'''

# For complex selectors, use template literals inside JS:
js = '''() => {
    const prog = document.querySelector(`[role="progressbar"]`);
    return "found";
}'''

# 🚨 REGEX PATTERNS - use single backslashes:
js = '''() => {
    const pattern = /\d+\s*[+\-*/]\s*\d+/;  // Single backslash for regex
    const text = "123 + 456";
    return pattern.test(text) ? "found" : "not found";
}'''
```

## Execute JavaScript
**🎯 STANDARD: ALL JavaScript must use triple single quotes (''') with double quotes inside**

Use execute_js to interact with the page when:
- other interactions fail
- you need special logic like scroll, zoom, extract data, click coordinates, drag and drop, wait, send keys, dispatch events sequences...

Think which website type you see and use the right approach. React/Vue/Angular ..., closed shadow DOM, iframes etc.
Start with selectors if you have them available. Else use coordinates as fallback.
Return always some information - but keep it limited to max 20000 characters.

**Core patterns:**
- Extract: `JSON.stringify(Array.from(document.querySelectorAll("a")).map(el => el.textContent))`
- Click: `document.querySelector("#button-id").click()`
- Input: `input.value = "text"; input.dispatchEvent(new Event("input", {bubbles: true}))`
- Coordinates: `document.elementFromPoint(150, 75).click()` (use x/y from browser_state)
- Send keys 

**Modern frameworks:**
- React click: `el.dispatchEvent(new MouseEvent("click", {bubbles: true}))`
- React input: `Object.getOwnPropertyDescriptor(HTMLInputElement.prototype, "value").set.call(input, "text")`
- For React: Use both value setting AND input events: `input.value="text"; input.dispatchEvent(new Event("input", {bubbles: true}))`
- For Angular/Material: Focus inputs first, then type character-by-character
- For Shadow DOM: Access via `.shadowRoot.querySelector("#element")`
- For modals: Always check for and dismiss overlays before main interactions
- Find in shadow: Use createTreeWalker to search shadowRoot elements


**Extract:**
- Explore structure: `document.body.innerHTML.substring(100, 500)`
- Find modals: `document.querySelector(".modal, [role='dialog']")`
- Check components: `document.querySelectorAll("*").filter(el => el.tagName.includes("-"))`
- Get links and filter them

**Constraints:**
- Return strings/numbers/booleans only (objects are useless)
- No DOM element injection.
- Use try/catch, keep concise

**🚨 CRITICAL SYNTAX RULES:**
```python
# ✅ CORRECT try/catch structure:
js = '''() => {
    try {
        const btn = document.querySelector("#submit");
        btn.click();
        return "clicked";
    } catch(e) {
        return "error: " + e.message;
    }
}'''

# ✅ CORRECT complex selectors (avoid double-escaping):
js = '''() => {
    const alert = document.querySelector(".alert");           // Simple
    const role = document.querySelector("[role='alert']");    // Mixed quotes  
    const complex = document.querySelector(`[data-id="123"]`); // Template literals
    return alert ? "found" : "not found";
}'''

# ❌ NEVER do this (common errors):
js = '''() => {
    const btn = document.querySelector("button[type=\"submit\"]");  // Double-escaped - BAD
    }catch(e){return "error"}  // Missing try block - BAD
    const x = text.toLowerCase();  // JavaScript method in Python context - BAD
}'''

# ✅ CORRECT versions:
js = '''() => {
    const btn = document.querySelector("button[type='submit']");  // Mixed quotes - GOOD
    try {
        btn.click();
        return "clicked";
    } catch(e) {
        return "error: " + e.message;  // Proper try/catch - GOOD
    }
}'''
# Python string methods: text.lower() not text.toLowerCase()
```


**❌ NEVER DO THIS:**
```python
# Inline JavaScript always fails
text = await target.evaluate('() => document.body.innerText')
await target.evaluate('() => document.querySelector("#button").click()')
```

**Why variables are mandatory:** Inline JavaScript breaks CDP parsing 99% of the time due to escaping issues.

JavaScript MUST use (...args) => format and returns strings (objects become JSON).




## Core Classes

- **Browser**, **Target**, **Element**, **Mouse**: Core classes for browser operations



## API Reference

### Browser Methods
- `newTarget(url=None)` → `Target` - Create blank tab or navigate to URL
- `getTargets()` → `list[Target]` - Get all page/iframe targets
- `closeTarget(target: Target | str)` - Close target by object or ID

### Target Methods
- `getElementsByCSSSelector(selector: str)` → `list[Element]` - Find elements by CSS selector
- `getElement(backend_node_id: int)` → `Element` - Get element by backend node ID
- `goto(url: str)` - Navigate this target to URL
- `goBack()`, `goForward()` - Navigate target history (with proper error handling)
- `evaluate(page_function: str, *args)` → `str` - Execute JavaScript (MUST use (...args) => format) and return string (objects/arrays are JSON-stringified)
- `press(key: str)` - Press key on page (supports "Control+A" format)
- `scroll(x=0, y=0, delta_x=None, delta_y=None)` - Scroll page (x,y (coordinates to scroll on), delta_y (how much to scroll))
- `setViewportSize(width: int, height: int)` - Set viewport dimensions
- `reload()` - Reload the current page
- `getUrl()` → `str`, `getTitle()` → `str` - Get page info

### Element Methods (Supported Only)
- `click(button='left', click_count=1, modifiers=None)` - Click element
- `fill(text: str)` - Fill input with text (clears first)
- `hover()` - Hover over element
- `focus()` - Focus the element
- `check()` - Toggle checkbox/radio button (clicks to change state)
- `selectOption(values: str | list[str])` - Select dropdown options (string or array)
- `dragTo(target: Element | Position, source_position=None, target_position=None)` - Drag to target
- `getAttribute(name: str)` → `str | None` - Get attribute value
- `getBoundingBox()` → `BoundingBox | None` - Get element position/size
- `getBasicInfo()` → `ElementInfo` - Get comprehensive element information


### Mouse Methods  
- `click(x: int, y: int, button='left', click_count=1)` - Click at coordinates
- `move(x: int, y: int, steps=1)` - Move to coordinates
- `down(button='left')`, `up(button='left')` - Press/release button

## Type Definitions

### Position
```python
class Position(TypedDict):
    x: float
    y: float
```

### BoundingBox
```python
class BoundingBox(TypedDict):
    x: float
    y: float
    width: float
    height: float
```

### ElementInfo
```python
class ElementInfo(TypedDict):
    backendNodeId: int
    nodeId: int | None
    nodeName: str
    nodeType: int
    nodeValue: str | None
    attributes: dict[str, str]
    boundingBox: BoundingBox | None
```

## Important LLM Usage Notes

**This is NOT Playwright.**. You can NOT use other methods than the ones described here. Key constraints for code generation:

**CRITICAL JAVASCRIPT EVALUATION RULES:**
- `target.evaluate()` MUST use (...args) => format and always returns string (objects become JSON strings)
- **SINGLE STANDARD**: Always use `'''()=>{}'''` (triple single quotes + double quotes inside JS)
- **CSS SELECTORS**: Use `"input[name="email"]"` or template literals `\`[role="button"]\`` 
- **NO ESCAPING NEEDED**: Double quotes inside triple single quotes work perfectly

**METHOD RESTRICTIONS:**
- `getElementsByCSSSelector()` returns immediately, no waiting
- For dropdowns: use `element.selectOption("value")` or `element.selectOption(["val1", "val2"])`, not `element.fill()`
- No methods: `element.submit()`, `element.dispatchEvent()`, `element.getProperty()`, `target.querySelectorAll()`
- Form submission: click submit button or use `target.press("Enter")`
- Get properties: use `target.evaluate("() => element.value")` not `element.getProperty()`

**ERROR PREVENTION:**
- Loop prevention: verify page state changes with `target.getUrl()`, `target.getTitle()`, `element.getAttribute()`
- Validate selectors before use: ensure no excessive escaping like `\\\\\\\\`
- Test complex selectors: if a selector fails, simplify it step by step
