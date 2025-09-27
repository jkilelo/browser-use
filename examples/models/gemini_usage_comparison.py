"""
Comparison: Agent vs Direct LLM usage with Google Search grounding
"""

import asyncio
import os
import sys

sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from dotenv import load_dotenv
from pydantic import BaseModel, Field

from browser_use import Agent, ChatGoogle
from browser_use.llm.messages import UserMessage

load_dotenv()

api_key = os.getenv('GOOGLE_API_KEY')
if not api_key:
	raise ValueError('GOOGLE_API_KEY is not set')


class SearchResult(BaseModel):
	"""Structured output for search results"""

	answer: str = Field(description='The answer to the question')
	confidence: str = Field(description='How confident the answer is (high/medium/low)')
	source_type: str = Field(description='Type of source used (search/training_data)')


async def test_direct_llm_with_google_search():
	"""Direct LLM usage with Google Search grounding - gets current info instantly"""

	print('🤖 DIRECT LLM with Google Search Grounding:')
	print('=' * 60)

	# Enable Google Search grounding for direct LLM calls
	llm = ChatGoogle(
		model='gemini-2.5-flash',
		google_search=True,  # Real-time search data
	)

	response = await llm.ainvoke(
		messages=[UserMessage(content='How many stars does the browser-use repository have on GitHub?')],
		output_format=SearchResult,
	)

	print(f'📊 Answer: {response.completion.answer}')
	print(f'🎯 Confidence: {response.completion.confidence}')
	print(f'📄 Source: {response.completion.source_type}')

	if response.grounding_metadata:
		print('\n🔍 Grounding Sources:')
		print(response.grounding_metadata)

	return response


async def test_agent_with_browser_tools():
	"""Agent usage with browser tools - uses browser to search"""

	print('\n🤖 AGENT with Browser Tools:')
	print('=' * 60)

	# For agents, google_search is disabled by default (they have browser tools)
	llm = ChatGoogle(
		model='gemini-2.5-flash',
		google_search=False,  # Use browser tools instead
	)

	agent = Agent(
		task='Find how many stars the browser-use repository has on GitHub',
		llm=llm,
	)

	try:
		history = await agent.run(max_steps=5)  # Limit steps for demo
		print(f'📊 Agent result: {history.final_result()}')
		return history
	except Exception as e:
		print(f'❌ Agent failed: {e}')
		return None


async def test_direct_llm_without_google_search():
	"""Direct LLM usage without Google Search - uses training data only"""

	print('\n🤖 DIRECT LLM without Google Search (training data only):')
	print('=' * 60)

	llm = ChatGoogle(
		model='gemini-2.5-flash',
		google_search=False,  # No real-time data
	)

	response = await llm.ainvoke(
		messages=[UserMessage(content='How many stars does the browser-use repository have on GitHub?')],
		output_format=SearchResult,
	)

	print(f'📊 Answer: {response.completion.answer}')
	print(f'🎯 Confidence: {response.completion.confidence}')
	print(f'📄 Source: {response.completion.source_type}')
	print('⚠️ Note: This may be outdated since it uses training data only')

	return response


if __name__ == '__main__':
	print('🧪 Testing different usage patterns for Google Search grounding\n')

	# Test 1: Direct LLM with Google Search grounding (instant, current results)
	direct_with_search = asyncio.run(test_direct_llm_with_google_search())

	# Test 2: Agent with browser tools (uses browser to search)
	agent_result = asyncio.run(test_agent_with_browser_tools())

	# Test 3: Direct LLM without Google Search (training data only)
	direct_without_search = asyncio.run(test_direct_llm_without_google_search())

	print('\n' + '=' * 80)
	print('📋 SUMMARY:')
	print('=' * 80)
	print('✅ Direct LLM + Google Search: Fast, current, structured data with sources')
	print('✅ Agent + Browser Tools: Comprehensive web automation (may hit CAPTCHAs)')
	print('✅ Direct LLM only: Fast but potentially outdated information')
	print('\n🎯 Use Google Search grounding for direct LLM calls when you need current info!')
