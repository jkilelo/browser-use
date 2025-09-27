import asyncio
import os

from dotenv import load_dotenv
from pydantic import BaseModel, Field

from browser_use import Agent, Browser, ChatOpenAI
from browser_use.remote_execute.service import RemoteExecutor

load_dotenv()


class HackernewsPost(BaseModel):
	title: str = Field(..., description='The post title')
	url: str = Field(..., description='The post URL')


class HackernewsPosts(BaseModel):
	posts: list[HackernewsPost] = Field(..., description='The list of posts')


remote = RemoteExecutor(
	OPENAI_API_KEY=os.getenv('OPENAI_API_KEY'),
)


@remote.execute()
async def pydantic_example(browser: Browser) -> HackernewsPosts | None:
	await browser.navigate_to('https://news.ycombinator.com/')

	await asyncio.sleep(2)

	agent = Agent(
		"""Get the latest 4 posts from Hacker News""",
		browser=browser,
		output_model_schema=HackernewsPosts,
		llm=ChatOpenAI(model='gpt-5-mini'),
	)
	res = await agent.run()

	return res.structured_output


async def main():
	# Basic usage
	# result = await simple_example()
	# print(f"Dict result: {result}")
	# print(f"Type: {type(result)}")

	# Pydantic model usage
	pydantic_result = await pydantic_example()
	print(f'Pydantic result: {pydantic_result}')
	print(f'Type: {type(pydantic_result)}')
	if pydantic_result:
		print(f'Is HackernewsPosts: {isinstance(pydantic_result, HackernewsPosts)}')
		print(f'Posts count: {len(pydantic_result.posts)}')
		print(f'JSON: {pydantic_result.model_dump_json()}')


if __name__ == '__main__':
	asyncio.run(main())
