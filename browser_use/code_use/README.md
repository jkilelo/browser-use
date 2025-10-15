# Code-Use Mode

Code-Use Mode is a Jupiter notebook-like code execution system for browser automation. Instead of the agent choosing from a predefined set of actions, the LLM writes Python code that gets executed in a persistent namespace with all browser control functions available.

## Problem Solved

The original brainstorm (Brainstorm.md:3-8) identified that data extraction was difficult:
- Single items could be extracted with the `extract` tool
- But extracting multiple items (e.g., "extract 40 products") was problematic
- The agent would call `extract` repeatedly on the same page after scrolling
- This resulted in large overlaps in data with no good way to combine results

**Code-Use Mode solves this** by giving the agent a Python execution environment where it can:
- Store extracted data in variables
- Loop through pages programmatically
- Combine results from multiple extractions
- Process and filter data before saving

## Architecture

### Components

1. **CodeUseAgent** (`service.py`) - Main agent that orchestrates the execution loop
2. **Namespace** (`namespace.py`) - Creates a Python namespace with all browser tools available as functions
3. **NotebookSession** (`views.py`) - Tracks execution state and history
4. **Notebook Export** (`notebook_export.py`) - Exports sessions to Jupyter notebooks or Python scripts

### How It Works

```
┌─────────────────────────────────────────────────────────────┐
│                      CodeUseAgent                           │
│                                                             │
│  ┌────────────┐      ┌──────────────┐      ┌────────────┐ │
│  │   LLM      │─────▶│   Execute    │─────▶│  Browser   │ │
│  │  Writes    │      │   Python     │      │   State    │ │
│  │   Code     │◀─────│    Code      │◀─────│            │ │
│  └────────────┘      └──────────────┘      └────────────┘ │
│        │                    │                      │       │
│        └────────────────────┴──────────────────────┘       │
│                    Feedback Loop                           │
└─────────────────────────────────────────────────────────────┘
```

1. **LLM generates Python code** based on the task and current browser state
2. **Code is executed** in a persistent namespace with browser tools
3. **Output and browser state** are captured and fed back to the LLM
4. **Process repeats** until the task is complete

### Namespace

The namespace is initialized with:

**Browser Control Functions:**
- `navigate(url)` - Navigate to a URL
- `click(index)` - Click an element
- `input(index, text)` - Type text
- `scroll(down, pages)` - Scroll the page
- `evaluate(code)` - Execute JavaScript
- `extract(query)` - Use LLM to extract data
- `done(text, success)` - Mark task complete
- And all other browser actions...

**Custom evaluate() Function:**
```python
# Returns values directly, not wrapped in ActionResult
result = await evaluate('''
(function(){
  return Array.from(document.querySelectorAll('.product')).map(p => ({
    name: p.querySelector('.name').textContent,
    price: p.querySelector('.price').textContent
  }))
})()
''')
# result is now a list of dicts, ready to use!
```

**Utilities:**
- `json` - JSON module
- `asyncio` - Async operations
- `Path` - File paths
- `browser` - Direct BrowserSession access
- `file_system` - File operations

## Usage

### Basic Example

```python
from browser_use.code_use import CodeUseAgent
from langchain_openai import ChatOpenAI

llm = ChatOpenAI(model='gpt-4o')

agent = CodeUseAgent(
    task='Extract all products from the page',
    llm=llm,
)

session = await agent.run()
await agent.close()
```

### Multi-Page Data Extraction

```python
agent = CodeUseAgent(
    task='''
    Go to the products page and extract all products from pages 1-5.
    For each product extract the name, price, and rating.
    Save results to products.json
    ''',
    llm=llm,
)

session = await agent.run()
```

The agent will write code like:

```python
# Navigate to first page
await navigate(url='https://example.com/products?page=1')

# Extract products using JavaScript
all_products = []
for page in range(1, 6):
    if page > 1:
        await navigate(url=f'https://example.com/products?page={page}')

    products = await evaluate('''
    (function(){
        return Array.from(document.querySelectorAll('.product')).map(p => ({
            name: p.querySelector('.name')?.textContent || '',
            price: p.querySelector('.price')?.textContent || '',
            rating: p.querySelector('.rating')?.textContent || ''
        }))
    })()
    ''')

    all_products.extend(products)
    print(f'Page {page}: Found {len(products)} products')

# Save to file
import json
with open('products.json', 'w') as f:
    json.dump(all_products, f, indent=2)

print(f'Total: {len(all_products)} products saved to products.json')

await done(text='Extracted all products', success=True)
```

### Export to Jupyter Notebook

```python
from browser_use.code_use import export_to_ipynb

# After running the agent
session = await agent.run()

# Export to .ipynb file
notebook_path = export_to_ipynb(session, 'my_automation.ipynb')
print(f'Saved to {notebook_path}')

# Now open in Jupyter Lab/Notebook to see the full execution history!
```

The exported notebook contains:
- All code cells with execution counts
- All outputs (print statements, return values)
- Any errors that occurred
- Browser state after each execution

## Advantages Over Action-Based Mode

### 1. Data Accumulation

**Action Mode:**
```
extract(query='products') -> ActionResult with text
extract(query='products') -> ActionResult with text
# How to combine these? They're just strings in the context window
```

**Code-Use Mode:**
```python
products_page_1 = await evaluate('/* js code */')
products_page_2 = await evaluate('/* js code */')
all_products = products_page_1 + products_page_2
# Real data structures, easy to manipulate!
```

### 2. Iteration and Loops

**Action Mode:**
- Can't easily loop through pages
- Each action is independent
- No programmatic control flow

**Code-Use Mode:**
```python
for page_num in range(1, 10):
    await navigate(url=f'https://example.com/page/{page_num}')
    products = await evaluate('/* extract */')
    all_products.extend(products)
```

### 3. Data Processing

**Action Mode:**
- Limited to what actions provide
- Can't filter or transform data
- Everything goes to files or LLM context

**Code-Use Mode:**
```python
products = await evaluate('/* extract */')
# Filter out products without prices
valid_products = [p for p in products if p['price']]
# Calculate average price
avg_price = sum(float(p['price'].strip('$')) for p in valid_products) / len(valid_products)
print(f'Average price: ${avg_price:.2f}')
```

### 4. Debugging

**Action Mode:**
- Hard to see what went wrong
- Limited introspection

**Code-Use Mode:**
- Full Python execution environment
- Print statements work
- Can inspect variables
- Export to Jupyter notebook for analysis

## System Prompt

The system prompt (system_prompt.md) explains to the LLM:
- What functions are available
- How to use `evaluate()` for JavaScript
- How to combine results from multiple pages
- Examples of common patterns
- Browser state format

## Implementation Notes

### Namespace Wrapper Functions

Each browser action is wrapped in a function that:
1. Validates parameters using the action's Pydantic model
2. Calls the action with proper special context
3. Unwraps `ActionResult` to return just the content
4. Raises errors instead of returning them

This makes the functions feel like native Python functions rather than browser automation tools.

### Code Execution

The agent uses Python's `exec()` to run code in the namespace:
- Stdout is captured for print statements
- Exceptions are caught and added to the cell
- Browser state is captured after each execution
- Everything is tracked in the NotebookSession

### Jupyter Notebook Format

The export uses standard `.ipynb` format (nbformat 4):
- Code cells with execution counts
- Stream outputs for print statements
- Error outputs for exceptions
- Can be opened in Jupyter Lab/Notebook/VSCode

## Limitations

1. **No Interactive Input** - Can't use `input()` for user prompts
2. **Async Required** - Must use `await` for all browser operations
3. **Limited Standard Library** - Only pre-imported modules available
4. **Token Limits** - Output is truncated at 20k characters

## Future Improvements

1. **Better Browser State** - Currently simplified, could show full DOM structure
2. **Streaming Output** - Show output as code executes
3. **Breakpoints** - Pause execution for inspection
4. **Auto-Save** - Save notebook after each step
5. **Imports** - Allow importing additional Python modules
6. **Variables Panel** - Show current namespace state

## Example: Job Application Demo

See `examples/code_use_extract_products.py` for a complete example that:
1. Navigates to a products page
2. Extracts product data using JavaScript
3. Scrolls to load more products
4. Combines all results
5. Saves to JSON file
6. Exports session to Jupyter notebook

## Comparison Table

| Feature | Action Mode | Code-Use Mode |
|---------|-------------|---------------|
| Data accumulation | ❌ Difficult | ✅ Easy (variables) |
| Looping | ❌ No | ✅ Python loops |
| Data processing | ❌ Limited | ✅ Full Python |
| Debugging | ⚠️ Basic | ✅ Jupyter notebook |
| Learning curve | ✅ Simple | ⚠️ Requires Python |
| Token efficiency | ✅ Better | ⚠️ More context |

## When to Use

**Use Code-Use Mode when:**
- Extracting data from multiple pages
- Need to combine/filter/process results
- Complex iteration logic
- Want to debug execution history

**Use Action Mode when:**
- Simple linear tasks
- Don't need data accumulation
- Want maximum token efficiency
- Simpler for non-programmers
