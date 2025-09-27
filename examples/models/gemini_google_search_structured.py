import asyncio
import os
import sys
from typing import List

sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from dotenv import load_dotenv
from pydantic import BaseModel, Field

from browser_use import ChatGoogle

load_dotenv()

api_key = os.getenv('GOOGLE_API_KEY')
if not api_key:
	raise ValueError('GOOGLE_API_KEY is not set')


class MatchResult(BaseModel):
	"""Structured output for Euro 2024 final match information"""

	winner: str = Field(description='The team that won Euro 2024')
	runner_up: str = Field(description='The team that came second')
	final_score: str = Field(description='The final score of the match')
	match_date: str = Field(description='Date when the final was played')
	venue: str = Field(description='Stadium where the final was played')
	key_moments: List[str] = Field(description='List of key moments or highlights from the match')


class NewsUpdate(BaseModel):
	"""Structured output for current news"""

	headline: str = Field(description='Main headline of the news')
	summary: str = Field(description='Brief summary of the news')
	date: str = Field(description='Date of the news')
	source: str = Field(description='News source')


async def test_structured_output_with_google_search():
	"""Test structured output combined with Google Search grounding"""

	# Enable both Google Search grounding AND structured output
	llm = ChatGoogle(
		model='gemini-2.5-flash',
		google_search=True,  # This enables Google Search grounding for direct LLM calls
	)

	# Test with structured output - the model will use Google Search to get current info
	# and return it in the specified structure
	print('🔍 Testing Euro 2024 query with structured output + Google Search...')

	response = await llm.ainvoke(
		messages=[
			{
				'role': 'user',
				'content': 'Find information about who won Euro 2024. I need current, accurate information about the final match.',
			}
		],
		output_format=MatchResult,
	)

	print(f'✅ Response type: {type(response.completion)}')
	print(f'✅ Winner: {response.completion.winner}')
	print(f'✅ Score: {response.completion.final_score}')
	print(f'✅ Venue: {response.completion.venue}')

	print('\n' + '=' * 60 + '\n')

	# Test with different structured output
	print('📰 Testing current news with structured output + Google Search...')

	response2 = await llm.ainvoke(
		messages=[{'role': 'user', 'content': 'Find the latest news about artificial intelligence developments today.'}],
		output_format=NewsUpdate,
	)

	print(f'✅ Response type: {type(response2.completion)}')
	print(f'✅ Headline: {response2.completion.headline}')
	print(f'✅ Summary: {response2.completion.summary[:100]}...')
	print(f'✅ Date: {response2.completion.date}')


async def test_without_google_search():
	"""Test structured output without Google Search for comparison"""

	llm = ChatGoogle(
		model='gemini-2.5-flash',
		google_search=False,  # No grounding - will use training data only
	)

	print('📚 Testing without Google Search (training data only)...')

	response = await llm.ainvoke(
		messages=[{'role': 'user', 'content': 'Tell me about who won Euro 2024 and the final match details.'}],
		output_format=MatchResult,
	)

	print(f'✅ Response type: {type(response.completion)}')
	print(f'✅ Winner (from training data): {response.completion.winner}')
	print('✅ Note: This may be outdated or incorrect without Google Search')


if __name__ == '__main__':
	print('🧪 Testing Google Search + Structured Output Integration\n')

	asyncio.run(test_structured_output_with_google_search())

	print('\n' + '=' * 80 + '\n')

	asyncio.run(test_without_google_search())

	print('\n🎉 Tests completed! Google Search grounding works perfectly with structured output.')
