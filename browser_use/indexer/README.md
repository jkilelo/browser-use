# Indexer Service

The Indexer Service provides contextual hints on how to interact with websites based on the current task and URL. These hints are automatically included in the agent's prompt to help guide the LLM's decision-making.

## Overview

The indexer service is called during each agent step to provide relevant interaction hints. By default, it returns an empty list, allowing you to implement your own custom logic.

## Basic Usage

```python
from browser_use import Agent
from browser_use.indexer import IndexerService

# Use default indexer (returns empty hints)
agent = Agent(task="Your task", indexer_service=IndexerService())

# Or let Agent create one automatically
agent = Agent(task="Your task")  # Uses default IndexerService
```

## Custom Implementation

Create your own indexer by extending `IndexerService`:

```python
from browser_use.indexer import IndexerService

class MyCustomIndexer(IndexerService):
    async def get_hints(self, task: str, current_url: str) -> list[str]:
        hints = []

        # Add custom logic based on URL and task
        if 'google.com' in current_url and 'search' in task.lower():
            hints = [
                'Use the search input field',
                'Click the search button',
                'Review search results'
            ]

        return hints

# Use your custom indexer
agent = Agent(task="Search for something", indexer_service=MyCustomIndexer())
```

## How It Works

1. During each agent step, the indexer's `get_hints()` method is called with:
   - `task`: The agent's current task
   - `current_url`: The current page URL

2. The hints are added to the agent's prompt in an `<indexer_hints>` section

3. The LLM can use these hints to make better decisions about which actions to take

## API Reference

### IndexerService

**Methods:**

- `async get_hints(task: str, current_url: str) -> list[str]`
  - Returns a list of string hints
  - Override this method to implement custom logic

- `async get_hints_structured(input_data: IndexerInput) -> IndexerResult`
  - Structured version using Pydantic models
  - Useful for more complex integrations

### Pydantic Models

**IndexerInput:**
```python
IndexerInput(
    task="Your task description",
    current_url="https://example.com"
)
```

**IndexerResult:**
```python
IndexerResult(
    hints=["hint1", "hint2", "hint3"]
)
```

## Example

See `examples/indexer_example.py` for a complete working example.

## Notes

- Hints should be concise and actionable
- The indexer service runs on every step, so keep logic lightweight
- Failed hint generation is logged but doesn't stop agent execution
- You can mock the indexer service in tests by subclassing `IndexerService`
