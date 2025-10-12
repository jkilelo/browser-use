import asyncio
import os
import sys

sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from dotenv import load_dotenv

load_dotenv()

from browser_use import Agent, Browser
from private_example.chat import ChatBrowserUse

# Connect to your existing Chrome browser
browser = Browser(
	executable_path='/Applications/Google Chrome.app/Contents/MacOS/Google Chrome',
	user_data_dir='~/Library/Application Support/Google/Chrome',
	profile_directory='Default',
)


task = """Go to https://www.linkedin.com/mynetwork/invitation-manager/received/PEOPLE_WITH_MUTUAL_CONNECTION/ and accept / ignore invitations.
only decide based on the short text you see in the list. 

Accept:
- if we have >10 mutual connections

Else reject.

I have 1500. - finish all.



If you dont see any - wait / refresh / scroll until you finished all


Keep the responses as short as possible.

dont not accept marketing people who try to offer me something like recuritng etc.
use multiaction with click action


"""

from lmnr import Laminar

Laminar.initialize()


async def main():
	agent = Agent(
		task=task,
		llm=ChatBrowserUse(),
		browser=browser,
		use_vision=True,
	)
	await agent.run(max_steps=1000)


if __name__ == '__main__':
	asyncio.run(main())
