# Conversation History Summarization Feature

## Overview

Implemented a conversation history summarization feature that condenses the agent's message history every N steps to prevent context overflow during long-running tasks.

## Changes Made

### 1. Agent Parameter (browser_use/agent/service.py:182)

```python
summarize_every_n_steps: int | None = None
```

- **Default**: `None` (no summarization)
- **When set**: The agent will summarize its conversation history every N steps
- **Example**: `summarize_every_n_steps=10` will trigger summarization after steps 10, 20, 30, etc.

### 2. Initialization (lines 249-251)

```python
self.summarize_every_n_steps = summarize_every_n_steps
self._steps_since_last_summary = 0
self._summary_count = 0
```

### 3. Step Counter Logic (lines 886-892)

After each step completes:
1. Increment `_steps_since_last_summary`
2. If threshold reached, call `_summarize_history()`
3. Reset counter and increment `_summary_count`

### 4. Summarization Method (lines 894-965)

The `_summarize_history()` method:
- Separates already-summarized blocks from new items
- Only summarizes new items since the last summary
- Sends history to LLM with a focused prompt
- Creates a new summary block tagged as `<summary_N>`
- Maintains accumulated structure: `[init, summary_0, summary_1, ..., new_items]`

## How It Works

### Example: `summarize_every_n_steps=10`

**Steps 1-10**:
- History: `[init, step_1, step_2, ..., step_10]`

**After Step 10** (first summarization):
- History: `[init, summary_0]`
- `summary_0` contains condensed version of steps 1-10

**Steps 11-20**:
- History: `[init, summary_0, step_11, step_12, ..., step_20]`

**After Step 20** (second summarization):
- History: `[init, summary_0, summary_1]`
- `summary_1` contains condensed version of steps 11-20

**Steps 21-30**:
- History: `[init, summary_0, summary_1, step_21, step_22, ..., step_30]`

**After Step 30** (third summarization):
- History: `[init, summary_0, summary_1, summary_2]`
- And so on...

This creates the "condensed blocks" structure where multiple summaries accumulate rather than having one giant history.

## Usage Example

```python
from browser_use import Agent
from browser_use.llm.models import get_llm_by_name

agent = Agent(
    task='Research the top 10 AI companies and their products',
    llm=get_llm_by_name('gpt-4o-mini'),
    summarize_every_n_steps=10,  # Summarize every 10 steps
)

history = await agent.run(max_steps=50)
```

See full example at: `examples/features/conversation_summarization.py`

## Benefits

1. **Prevents Context Overflow**: Long-running tasks won't hit token limits
2. **Maintains Key Information**: Summaries preserve important discoveries and progress
3. **Accumulative Structure**: Multiple summary blocks provide historical context
4. **Graceful Failure**: If summarization fails, agent continues without crashing
5. **Configurable**: Set to `None` to disable, or any integer to control frequency

## Technical Details

### Summarization Prompt

The LLM receives:
- The original task
- Recent conversation history (only new items since last summary)
- Instructions to summarize:
  1. What has been accomplished
  2. Key information discovered
  3. Current progress and remaining work

### Summary Format

Summaries are stored as `HistoryItem` objects with:
```python
system_message=f'<summary_{count}>\n{summary_text}\n</summary_{count}>'
```

### Error Handling

- If summarization fails, the error is logged but the agent continues
- Original history is preserved if summarization encounters an error
- No impact on main agent execution flow

## Files Modified

1. `browser_use/agent/service.py`
   - Added parameter `summarize_every_n_steps`
   - Added tracking variables
   - Added `_summarize_history()` method
   - Added logic in `_finalize()` to trigger summarization
   - Added import for `HistoryItem`

## Files Created

1. `examples/features/conversation_summarization.py`
   - Demonstrates usage of the feature

## Testing

To test the feature:

```python
import asyncio
from browser_use import Agent
from browser_use.llm.models import get_llm_by_name

async def test():
    agent = Agent(
        task="Count from 1 to 25, one number per step",
        llm=get_llm_by_name('gpt-4o-mini'),
        summarize_every_n_steps=10,
    )
    
    # Should create 2 summaries (at step 10 and 20)
    history = await agent.run(max_steps=25)
    
    print(f"Completed {len(history)} steps")
    print(f"Total summaries created: {agent._summary_count}")
    
asyncio.run(test())
```

Expected output:
- Summary created after step 10
- Summary created after step 20
- Final history contains 2 condensed summary blocks + steps 21-25
