"""
Example: Using code-use mode to extract products from multiple pages.

This example demonstrates the new code-use mode, which works like a Jupiter notebook
where the LLM writes Python code that gets executed in a persistent namespace.

The agent can:
- Navigate to pages
- Extract data using JavaScript
- Combine results from multiple pages
- Save data to files
- Export the session as a Jupyter notebook

This solves the problem from the brainstorm where extraction of multiple items
was difficult with the extract tool alone.
"""

import asyncio

# Set up LLM (use a fast model for code generation)
from lmnr import Laminar

from browser_use import ChatGoogle
from browser_use.browser.profile import BrowserProfile
from browser_use.code_use import CodeUseAgent, export_to_ipynb, session_to_python_script

Laminar.initialize()
llm = ChatGoogle(model='gemini-flash-latest')


async def main():
	"""
	Task: Extract product listings from an e-commerce site.

	The agent will:
	1. Navigate to the products page
	2. Extract products using JavaScript
	3. Scroll to load more products
	4. Combine all results
	5. Save to a JSON file
	"""

	# Create code-use agent
	agent = CodeUseAgent(
		task="""
		Go to https://webscraper.io/test-sites/e-commerce/allinone/computers/laptops
		and extract all laptop products. For each product, extract:
		- Name
		- Price
		- Description
		- Rating

		Use JavaScript to extract the data efficiently. Scroll down to load all products
		if needed. Save the results to a file called 'laptops.json'.

		IMPORTANT: Before calling done(), verify that:
		1. The JSON file was created successfully
		2. It contains the expected number of products
		3. Each product has all required fields
		""",
		llm=llm,
		browser_profile=BrowserProfile(
			headless=False,  # Show browser to see what's happening
		),
		max_steps=10,
	)

	try:
		# Run the agent
		print('Running code-use agent...')
		session = await agent.run()

		# Print summary
		print(f'\n{"=" * 60}')
		print('Session Summary')
		print(f'{"=" * 60}')
		print(f'Total cells executed: {len(session.cells)}')
		print(f'Total execution count: {session.current_execution_count}')

		# Print each cell
		for i, cell in enumerate(session.cells):
			print(f'\n{"-" * 60}')
			print(f'Cell {i + 1} (Status: {cell.status.value})')
			print(f'{"-" * 60}')
			print('Code:')
			print(cell.source)
			if cell.output:
				print('\nOutput:')
				print(cell.output)
			if cell.error:
				print('\nError:')
				print(cell.error)

		# Export to Jupyter notebook
		notebook_path = export_to_ipynb(session, 'product_extraction.ipynb')
		print(f'\n✓ Exported session to Jupyter notebook: {notebook_path}')

		# Export to Python script
		script = session_to_python_script(session)
		with open('product_extraction.py', 'w') as f:
			f.write(script)
		print('✓ Exported session to Python script: product_extraction.py')

	finally:
		await agent.close()


if __name__ == '__main__':
	asyncio.run(main())
