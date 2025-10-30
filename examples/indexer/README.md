# Indexer Examples

These examples demonstrate how to use the `IndexerService` to provide contextual hints to the agent based on the current task and URL.

## Files

### `example.py`
Basic example showing how to create a custom indexer service that provides hints for different types of websites:
- Google search hints
- GitHub repository hints
- E-commerce shopping hints

**Run it:**
```bash
python examples/indexer/example.py
```

### `gemini.py`
Flight search example using Google's Gemini model with a custom indexer that provides specific hints for flight booking websites like Google Flights, Kayak, and Skyscanner.

**Requirements:**
- Set `GOOGLE_API_KEY` environment variable

**Run it:**
```bash
export GOOGLE_API_KEY=your_key_here
python examples/indexer/gemini.py
```

## How It Works

1. Create a custom class that extends `IndexerService`
2. Override the `get_hints(task, current_url)` method
3. Return a list of string hints based on the task and URL
4. Pass your custom indexer to the Agent via `indexer_service` parameter

The agent will automatically call your indexer on each step and include the hints in the prompt sent to the LLM.

## Key Benefits

- **Context-aware**: Hints adapt to the current website and task
- **Easy to mock**: Simple interface for testing and customization
- **Non-intrusive**: Failed hint generation doesn't stop the agent
- **Flexible**: Return any hints that make sense for your use case
