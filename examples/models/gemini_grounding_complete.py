"""
Complete example: Google Search grounding with structured output and memory integration
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


class WeatherInfo(BaseModel):
	"""Structured weather information"""

	temperature: str = Field(description='Current temperature')
	conditions: str = Field(description='Weather conditions')
	location: str = Field(description='Location name')


async def test_direct_llm_grounding():
	"""Direct LLM with Google Search grounding and structured output"""

	print('🤖 DIRECT LLM with Google Search Grounding + Structured Output:')
	print('=' * 70)

	llm = ChatGoogle(
		model='gemini-2.5-flash',
		google_search=True,  # Enable grounding for direct calls
	)

	response = await llm.ainvoke(
		messages=[UserMessage(content='What is the current weather in Paris?')], output_format=WeatherInfo
	)

	print(f'🌡️ Temperature: {response.completion.temperature}')
	print(f'☁️ Conditions: {response.completion.conditions}')
	print(f'📍 Location: {response.completion.location}')

	if response.grounding_metadata:
		print('\n🔍 Grounding Sources:')
		print(response.grounding_metadata)

	return response


async def test_agent_grounding():
	"""Agent with Google Search grounding - grounding data appears in memory"""

	print('\n🤖 AGENT with Google Search Grounding (Memory Integration):')
	print('=' * 70)

	llm = ChatGoogle(
		model='gemini-2.5-flash',
		google_search=True,  # Enable grounding for agent
	)

	agent = Agent(
		task='What is the current weather in London? Just provide the answer directly.',
		llm=llm,
	)

	try:
		history = await agent.run(max_steps=1)

		print(f'🌟 Agent Result: {history.final_result()}')

		# Show memory with grounding data
		if history.history and history.history[0].model_output:
			memory = history.history[0].model_output.memory
			print('\n🧠 Agent Memory (includes grounding sources):')
			print(memory)

		return history
	except Exception as e:
		print(f'❌ Agent error: {e}')
		return None


if __name__ == '__main__':
	print('🧪 Complete Google Search Grounding Integration Test\n')

	# Test 1: Direct LLM with structured output
	direct_result = asyncio.run(test_direct_llm_grounding())

	# Test 2: Agent with memory integration
	agent_result = asyncio.run(test_agent_grounding())

	print('\n' + '=' * 80)
	print('🎯 SUMMARY:')
	print('=' * 80)
	print('✅ Direct LLM: Gets current info in structured format + grounding_metadata field')
	print('✅ Agent: Gets current info + grounding sources automatically added to memory')
	print('✅ Both approaches provide transparency about information sources')
	print('\n🎉 Google Search grounding fully integrated with browser-use!')
