import asyncio
import os
from dotenv import load_dotenv
from browser_use.llm.google import ChatGoogle
from browser_use.llm.messages import SystemMessage, UserMessage
from pydantic import BaseModel, Field

load_dotenv()

class SimpleAction(BaseModel):
	text: str = Field(description="The action")

class SimpleOutput(BaseModel):
	action: list[SimpleAction] = Field(description="Actions")
	thinking: str | None = None

async def test():
	print("Creating LLM...")
	llm = ChatGoogle(model='gemini-2.5-flash', api_key=os.getenv('GOOGLE_API_KEY'), temperature=0.0)
	print(f"LLM created: {llm}")

	messages = [
		UserMessage(content="What's 2+2? Give me one action with the answer.")
	]
	print(f"Messages created: {len(messages)}")

	print("About to call astream...")
	try:
		actions_task, complete_task = await llm.astream(messages, output_format=SimpleOutput)
		print(f"astream returned: {actions_task}, {complete_task}")
	except Exception as e:
		print(f"ERROR in astream: {e}")
		import traceback
		traceback.print_exc()
		return

	print("Got tasks, waiting for actions...")
	actions = await actions_task
	print(f"Actions: {actions}")

	print("Waiting for complete...")
	complete = await complete_task
	print(f"Complete: {complete}")

if __name__ == '__main__':
	asyncio.run(test())
