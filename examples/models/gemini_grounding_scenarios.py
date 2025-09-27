"""
Test different scenarios for Google Search grounding
"""

import asyncio
import os
import sys

sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from dotenv import load_dotenv
from pydantic import BaseModel, Field

from browser_use import ChatGoogle
from browser_use.llm.messages import UserMessage

load_dotenv()

api_key = os.getenv('GOOGLE_API_KEY')
if not api_key:
	raise ValueError('GOOGLE_API_KEY is not set')


class TestResult(BaseModel):
	answer: str = Field(description='The answer to the question')
	confidence: str = Field(description='Confidence level')


async def test_grounding_scenarios():
	"""Test different scenarios to understand when grounding is triggered"""

	llm = ChatGoogle(model='gemini-2.5-flash', google_search=True)

	scenarios = [
		('Math question', 'What is 15 * 23?'),
		('Current events', 'Who won Euro 2024?'),
		('Current weather', 'What is the weather in Tokyo right now?'),
		('General knowledge', 'What is the capital of France?'),
		('Current stock price', 'What is Tesla stock price today?'),
		('Programming concept', 'What is Python?'),
		('Recent news', 'What happened in AI news this week?'),
	]

	results = []

	for scenario_name, query in scenarios:
		print(f'\n{"=" * 60}')
		print(f'🧪 Testing: {scenario_name}')
		print(f'❓ Query: {query}')
		print('=' * 60)

		try:
			response = await llm.ainvoke(messages=[UserMessage(content=query)], output_format=TestResult)

			has_grounding = bool(response.grounding_metadata)
			grounding_summary = 'None'

			if response.grounding_metadata:
				lines = response.grounding_metadata.split('\n')
				grounding_summary = f'{len(lines)} lines of metadata'
				if 'sources' in response.grounding_metadata.lower():
					source_count = response.grounding_metadata.count('sources):')
					if source_count > 0:
						grounding_summary += f', {source_count} source groups'

			print(f'📊 Answer: {response.completion.answer[:100]}...')
			print(f'🎯 Confidence: {response.completion.confidence}')
			print(f'🔍 Grounding: {grounding_summary}')
			print(f'✅ Has grounding: {has_grounding}')

			results.append((scenario_name, has_grounding, grounding_summary))

		except Exception as e:
			print(f'❌ Error: {e}')
			results.append((scenario_name, False, f'Error: {str(e)[:50]}'))

	# Summary
	print(f'\n{"=" * 80}')
	print('📋 GROUNDING SUMMARY:')
	print('=' * 80)

	for scenario, has_grounding, summary in results:
		status = '✅' if has_grounding else '❌'
		print(f'{status} {scenario:20} | Grounding: {summary}')

	print(f'\n🎯 Total scenarios with grounding: {sum(1 for _, has_grounding, _ in results if has_grounding)}/{len(results)}')
	print('💡 Grounding is intelligently triggered based on whether current information would improve the answer')


if __name__ == '__main__':
	asyncio.run(test_grounding_scenarios())
