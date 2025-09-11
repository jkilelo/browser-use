# Browser Actor

Python Playwright-like library built on CDP (Chrome DevTools Protocol).

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
target = await browser.goto("https://example.com")  # Navigate to URL
target = await browser.newTarget()  # Create blank tab
targets = await browser.getTargets()  # Get all existing tabs

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
mouse = await target.mouse
await mouse.click(x=100, y=200, button='left')
await mouse.move(x=300, y=400)
```

```python
# Target operations
await target.scroll(x=0, y=100, delta_y=-500) 
await target.press("Control+A")  # Key combinations supported
await target.press("Escape")
await target.setViewportSize(width=1920, height=1080)
await target.reload()
page_screenshot = await target.screenshot()  # JPEG by default
page_png = await target.screenshot(format="png")

# JavaScript evaluation - always returns string
text = await target.evaluate("() => document.body.innerText")
result = await target.evaluate("() => ({title: document.title, url: location.href})")  # Returns JSON string
# Can use directly with regex since it's always a string
matches = re.findall(r"pattern", text)
data = json.loads(result)  # Parse JSON if needed
```

JavaScript execution always returns strings (objects/arrays are JSON-stringified).

## Core Classes

- **Browser**, **Target**, **Element**, **Mouse**: Core classes for browser operations

## API Reference

### Browser Methods
- `goto(url: str)` → `Target` - Navigate to URL, returns new target
- `newTarget()` → `Target` - Create blank tab
- `getTargets()` → `list[Target]` - Get all page/iframe targets
- `closeTarget(target: Target | str)` - Close target by object or ID
- `goBack()`, `goForward()` - Navigate browser history (with proper error handling)

### Target Methods
- `getElementsByCSSSelector(selector: str)` → `list[Element]` - Find elements by CSS selector
- `getElement(backend_node_id: int)` → `Element` - Get element by backend node ID
- `evaluate(page_function: str, arg=None)` → `str` - Execute JavaScript and return string (objects/arrays are JSON-stringified)
- `press(key: str)` - Press key on page (supports "Control+A" format)
- `scroll(x=0, y=0, delta_x=None, delta_y=None)` - Scroll page (robust with fallbacks)
- `setViewportSize(width: int, height: int)` - Set viewport dimensions
- `reload()` - Reload the current page
- `getUrl()` → `str`, `getTitle()` → `str` - Get page info

### Element Methods
- `click(button='left', click_count=1, modifiers=None)` - Click element
- `fill(text: str)` - Fill input with text (clears first)
- `hover()` - Hover over element
- `focus()` - Focus the element
- `check()` - Toggle checkbox/radio button (clicks to change state)
- `selectOption(values: str | list[str])` - Select dropdown options
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
