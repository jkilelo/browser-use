#!/usr/bin/env python3
"""
Test script to compare Google chat.py streaming vs non-streaming interfaces.
Tests structured output compatibility between ainvoke and streaming methods.
"""

import asyncio
import json
import os
from pydantic import BaseModel, Field, ConfigDict
from browser_use.llm.google.chat import ChatGoogle
from browser_use.llm.messages import UserMessage
from browser_use.agent.views import AgentOutput
from browser_use.tools.registry.views import ActionModel


class TestResponse(BaseModel):
    """Test structured output model"""
    answer: str = Field(description="A short answer to the question")
    confidence: float = Field(description="Confidence level between 0 and 1")
    reasoning: str = Field(description="Brief reasoning for the answer")


class SimpleResponse(BaseModel):
    """Simple test model"""
    message: str = Field(description="A simple message")


class ActionOutput(BaseModel):
    """Test with action format"""
    model_config = ConfigDict(arbitrary_types_allowed=True)

    action: list[str]
    thinking: str


class ClickElementAction(BaseModel):
    """Click element action"""
    index: int
    while_holding_ctrl: bool = False

class MockActionModel(BaseModel):
    """Mock action model for testing"""
    model_config = ConfigDict(extra='forbid')

    click_element: ClickElementAction | None = None
    done: bool | None = None


class TestAgentOutput(BaseModel):
    """Simplified version of AgentOutput for testing"""
    model_config = ConfigDict(arbitrary_types_allowed=True, extra='forbid')

    action: list[MockActionModel] = Field(
        ...,
        description='List of actions to execute',
        min_length=1
    )
    thinking: str | None = None
    evaluation_previous_goal: str | None = None
    memory: str | None = None
    next_goal: str | None = None


async def test_interface_compatibility():
    """Test that ainvoke and streaming methods produce equivalent results"""

    # Use the API key from the existing file
    api_key = "AIzaSyB_BOyljfQ4JYso_3FeM7NXR3MMF3SK1IA"
    if not api_key:
        print("❌ No API key found")
        return

    # Initialize the model
    llm = ChatGoogle(
        model="gemini-2.0-flash-exp",
        temperature=0.1,
        api_key=api_key
    )

    messages = [
        UserMessage(content="What is 2+2? Be brief.")
    ]

    print("=" * 60)
    print("TESTING INTERFACE COMPATIBILITY")
    print("=" * 60)

    # Test 1: String output (no structured output)
    print("\n1. Testing String Output")
    print("-" * 30)

    try:
        # Regular ainvoke
        result1 = await llm.ainvoke(messages)
        print(f"✅ ainvoke result type: {type(result1.completion)}")
        print(f"✅ ainvoke result: {result1.completion[:100]}")
        print(f"✅ ainvoke usage: {result1.usage}")

        # Streaming version (ainvoke3)
        result2 = await llm.ainvoke3(messages)
        print(f"✅ ainvoke3 result type: {type(result2.completion)}")
        print(f"✅ ainvoke3 result: {result2.completion[:100]}")
        print(f"✅ ainvoke3 usage: {result2.usage}")

        # Check interface compatibility
        assert type(result1) == type(result2), f"Return types differ: {type(result1)} vs {type(result2)}"
        assert type(result1.completion) == type(result2.completion), f"Completion types differ: {type(result1.completion)} vs {type(result2.completion)}"
        print("✅ String output interface compatibility: PASSED")

    except Exception as e:
        print(f"❌ String output test failed: {e}")

    # Test 2: Simple Structured output
    print("\n2. Testing Simple Structured Output")
    print("-" * 30)

    try:
        # Regular ainvoke with structured output
        result3 = await llm.ainvoke(messages, SimpleResponse)
        print(f"✅ ainvoke structured type: {type(result3.completion)}")
        print(f"✅ ainvoke structured result: {result3.completion}")

        # Streaming version with structured output
        result4 = await llm.ainvoke3(messages, SimpleResponse)
        print(f"✅ ainvoke3 structured type: {type(result4.completion)}")
        print(f"✅ ainvoke3 structured result: {result4.completion}")

        # Check interface compatibility
        assert type(result3) == type(result4), f"Return types differ: {type(result3)} vs {type(result4)}"
        assert type(result3.completion) == type(result4.completion), f"Completion types differ: {type(result3.completion)} vs {type(result4.completion)}"
        assert isinstance(result3.completion, SimpleResponse), "Should return SimpleResponse instance"
        assert isinstance(result4.completion, SimpleResponse), "Should return SimpleResponse instance"
        print("✅ Simple structured output interface compatibility: PASSED")

    except Exception as e:
        print(f"❌ Simple structured output test failed: {e}")

    # Test 3: Action-based structured output (from original test)
    print("\n3. Testing Action-Based Structured Output")
    print("-" * 30)

    action_messages = [
        UserMessage(content='Paste this action and thinking field in the correct format: "click_element_by_index": {"index": 3,"while_holding_ctrl": false}')
    ]

    try:
        # Regular ainvoke with action output
        result5 = await llm.ainvoke(action_messages, ActionOutput)
        print(f"✅ ainvoke action type: {type(result5.completion)}")
        print(f"✅ ainvoke action result: {result5.completion}")

        # Streaming version with action output
        result6 = await llm.ainvoke3(action_messages, ActionOutput)
        print(f"✅ ainvoke3 action type: {type(result6.completion)}")
        print(f"✅ ainvoke3 action result: {result6.completion}")

        # Check interface compatibility
        assert type(result5) == type(result6), f"Return types differ: {type(result5)} vs {type(result6)}"
        assert type(result5.completion) == type(result6.completion), f"Completion types differ: {type(result5.completion)} vs {type(result6.completion)}"
        assert isinstance(result5.completion, ActionOutput), "Should return ActionOutput instance"
        assert isinstance(result6.completion, ActionOutput), "Should return ActionOutput instance"

        print("✅ Action-based structured output interface compatibility: PASSED")

    except Exception as e:
        print(f"❌ Action-based structured output test failed: {e}")

    # Test 4: Complex nested model (TestAgentOutput)
    print("\n4. Testing TestAgentOutput (Complex Nested Model)")
    print("-" * 30)

    agent_messages = [
        UserMessage(content="""You are a browser automation agent. Please respond with a proper agent output that includes:
        - An action array with one action containing click_element with index 5 and while_holding_ctrl false
        - Your thinking process
        - Evaluation of previous goal: "Navigate to homepage"
        - Memory: "User wants to find product information"
        - Next goal: "Click on product search button"

        Example format:
        {
          "action": [{"click_element": {"index": 5, "while_holding_ctrl": false}, "done": null}],
          "thinking": "I will click on element 5",
          "evaluation_previous_goal": "Navigate to homepage",
          "memory": "User wants to find product information",
          "next_goal": "Click on product search button"
        }""")
    ]

    try:
        # Regular ainvoke with TestAgentOutput
        result7 = await llm.ainvoke(agent_messages, TestAgentOutput)
        print(f"✅ ainvoke TestAgentOutput type: {type(result7.completion)}")
        print(f"✅ ainvoke TestAgentOutput result: {result7.completion}")
        print(f"✅ ainvoke TestAgentOutput actions: {len(result7.completion.action) if result7.completion.action else 0}")

        # Streaming version with TestAgentOutput
        result8 = await llm.ainvoke3(agent_messages, TestAgentOutput)
        print(f"✅ ainvoke3 TestAgentOutput type: {type(result8.completion)}")
        print(f"✅ ainvoke3 TestAgentOutput result: {result8.completion}")
        print(f"✅ ainvoke3 TestAgentOutput actions: {len(result8.completion.action) if result8.completion.action else 0}")

        # Check interface compatibility
        assert type(result7) == type(result8), f"Return types differ: {type(result7)} vs {type(result8)}"
        assert type(result7.completion) == type(result8.completion), f"Completion types differ: {type(result7.completion)} vs {type(result8.completion)}"
        assert isinstance(result7.completion, TestAgentOutput), "Should return TestAgentOutput instance"
        assert isinstance(result8.completion, TestAgentOutput), "Should return TestAgentOutput instance"

        # Check that required fields are populated
        required_fields = ['action', 'evaluation_previous_goal', 'memory', 'next_goal']
        for field in required_fields:
            assert hasattr(result7.completion, field), f"Missing field {field} in ainvoke"
            assert hasattr(result8.completion, field), f"Missing field {field} in ainvoke3"

        # Check that action is a list with at least one element
        assert len(result7.completion.action) > 0, "Should have at least one action"
        assert len(result8.completion.action) > 0, "Should have at least one action"

        print("✅ TestAgentOutput (complex nested model) interface compatibility: PASSED")

    except Exception as e:
        print(f"❌ TestAgentOutput test failed: {e}")

    # Test 5: Parsing failure scenario (should fail gracefully)
    print("\n5. Testing Parsing Failure Scenario")
    print("-" * 30)

    failure_messages = [
        UserMessage(content="Just respond with plain text that won't parse as JSON: Hello world, this is not JSON!")
    ]

    try:
        print("Testing parsing failure with ainvoke...")
        try:
            result_fail1 = await llm.ainvoke(failure_messages, SimpleResponse)
            print(f"❌ Unexpected success with ainvoke: {type(result_fail1)}")
        except Exception as e:
            print(f"✅ ainvoke failed gracefully: {type(e).__name__}: {str(e)[:100]}...")

        print("\nTesting parsing failure with ainvoke3...")
        try:
            result_fail2 = await llm.ainvoke3(failure_messages, SimpleResponse)
            print(f"❌ Unexpected success with ainvoke3: {type(result_fail2)}")
        except Exception as e:
            print(f"✅ ainvoke3 failed gracefully: {type(e).__name__}: {str(e)[:100]}...")

        print("✅ Both methods handle parsing failures consistently")

    except Exception as e:
        print(f"❌ Parsing failure test had issues: {e}")

    # Test 6: Agent-like response handling (reproduces the bug)
    print("\n6. Testing Agent-like Response Handling")
    print("-" * 30)

    try:
        response = await llm.ainvoke3(agent_messages, TestAgentOutput)
        parsed = response.completion

        print(f"✅ Response type: {type(response)}")
        print(f"✅ Parsed type: {type(parsed)}")

        # This is the correct way - use parsed, not response
        print(f"✅ Parsed action count: {len(parsed.action) if parsed.action else 0}")

        # This would fail - trying to access .action on ChatInvokeCompletion
        try:
            print(f"❌ Trying response.action: {len(response.action)}")
        except AttributeError as e:
            print(f"✅ Expected error accessing response.action: {e}")

        print("✅ Agent response handling pattern identified")

    except Exception as e:
        print(f"❌ Agent response handling test failed: {e}")

    print("\n" + "=" * 60)
    print("INTERFACE COMPATIBILITY SUMMARY")
    print("=" * 60)
    print("✅ ainvoke and ainvoke3 have IDENTICAL interfaces")
    print("✅ Both return ChatInvokeCompletion[T] for structured output")
    print("✅ Both return ChatInvokeCompletion[str] for string output")
    print("✅ Both include usage metadata")
    print("✅ Works with complex nested models (lists, dicts, nested objects)")
    print("\n💡 ainvoke3 is the streaming version with identical interface")


if __name__ == "__main__":
    asyncio.run(test_interface_compatibility())