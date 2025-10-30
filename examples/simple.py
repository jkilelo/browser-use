"""
Setup:
1. Get your API key from https://cloud.browser-use.com/new-api-key
2. Set environment variable: export BROWSER_USE_API_KEY="your-key"
"""

from dotenv import load_dotenv

from browser_use import Agent, ChatGoogle

load_dotenv()

agent = Agent(
	task="""
    1. Go to a form page
    2. Fill Notes field with 'test notes'
    3. Verify Notes field contains 'test notes'
    4. Verify Submit button is disabled
    """,
	use_vision=True,
	llm=ChatGoogle(model='gemini-2.5-flash'),
)
result = agent.run_sync()
print(result)