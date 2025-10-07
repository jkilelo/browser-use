# pyright: reportMissingImports=false
import asyncio
import os
import sys
from dataclasses import dataclass

sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from dotenv import load_dotenv

load_dotenv()

# Third-party imports
import gradio as gr  # type: ignore
from rich.console import Console
from rich.panel import Panel
from rich.text import Text

# Local module imports
from browser_use import Agent, ChatOpenAI, ChatGoogle


@dataclass
class ActionResult:
	is_done: bool
	extracted_content: str | None
	error: str | None
	include_in_memory: bool


@dataclass
class AgentHistoryList:
	all_results: list[ActionResult]
	all_model_outputs: list[dict]


def parse_agent_history(history_str: str) -> None:
	console = Console()

	# Split the content into sections based on ActionResult entries
	sections = history_str.split('ActionResult(')

	for i, section in enumerate(sections[1:], 1):  # Skip first empty section
		# Extract relevant information
		content = ''
		if 'extracted_content=' in section:
			content = section.split('extracted_content=')[1].split(',')[0].strip("'")

		if content:
			header = Text(f'Step {i}', style='bold blue')
			panel = Panel(content, title=header, border_style='blue')
			console.print(panel)
			console.print()

	return None


async def run_browser_task(
	task: str,
	api_key: str,
	model: str = 'o3',
	headless: bool = True,
) -> str:
	if not api_key.strip():
		return 'Please provide an API key'

	try:
		# Create appropriate LLM based on model selection
		if model.startswith('gemini'):
			os.environ['GOOGLE_API_KEY'] = api_key
			llm = ChatGoogle(model=model)
		else:
			os.environ['OPENAI_API_KEY'] = api_key
			llm = ChatOpenAI(model=model)
		
		agent = Agent(
			task=task,
			llm=llm,
		)
		result = await agent.run()
		#  TODO: The result could be parsed better
		return str(result)
	except Exception as e:
		return f'Error: {str(e)}'


def create_ui():
	with gr.Blocks(title='Browser Use GUI') as interface:
		gr.Markdown('# Browser Use Task Automation')

		with gr.Row():
			with gr.Column():
				api_key = gr.Textbox(label='API Key (OpenAI or Google)', placeholder='sk-... or AIza...', type='password')
				task = gr.Textbox(
					label='Task Description',
					placeholder='E.g., Find flights from New York to London for next week',
					lines=3,
				)
				model = gr.Dropdown(choices=['o3', 'gemini-2.5-flash', 'gemini-2.5-flash-lite'], label='Model', value='o3')
				headless = gr.Checkbox(label='Run Headless', value=False)
				submit_btn = gr.Button('Run Task')

			with gr.Column():
				output = gr.Textbox(label='Output', lines=10, interactive=False)

		submit_btn.click(
			fn=lambda *args: asyncio.run(run_browser_task(*args)),
			inputs=[task, api_key, model, headless],
			outputs=output,
		)

	return interface


if __name__ == '__main__':
	demo = create_ui()
	demo.launch()
