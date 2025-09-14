### THIS PART IS AI WRITTEN
import asyncio

from cdp_use import CDPClient

from browser_use.actor import Browser


async def executor(client: CDPClient):
	browser = Browser(client)
	target = await browser.newTarget('https://www.google.com/travel/flights')
	await asyncio.sleep(3)  # let the page load

	# Try to accept consent if it appears (EU/UK regions)
	try:
		clicked = await target.evaluate("""
        () => {
            const tryClick = (root) => {
                const labels = ['I agree', 'Accept all', 'Accept', 'Agree', 'Got it'];
                const nodes = root.querySelectorAll('button, div[role="button"], input[type="button"], input[type="submit"]');
                for (const el of nodes) {
                    const t = (el.innerText || el.value || '').trim().toLowerCase();
                    if (labels.some(l => t.includes(l.toLowerCase()))) { el.click(); return true; }
                }
                return false;
            };
            if (tryClick(document)) return true;
            const iframes = document.querySelectorAll('iframe');
            for (const f of iframes) {
                try {
                    if (f.contentDocument && tryClick(f.contentDocument)) return true;
                } catch (e) {}
            }
            return false;
        }
        """)
		if clicked:
			await asyncio.sleep(2)
	except Exception:
		pass

	# Helper to get first element by trying multiple CSS selectors
	async def first_by_selectors(selectors):
		for sel in selectors:
			els = await target.getElementsByCSSSelector(sel)
			if els:
				return els[0]
		return None

	# Open/Focus the "From" field if needed
	from_input = await first_by_selectors(
		[
			"input[aria-label*='where from' i]",
			"input[aria-label*='from' i]",
			"input[aria-label*='departure' i]",
			"input[placeholder*='where from' i]",
			"input[placeholder*='from' i]",
		]
	)
	if not from_input:
		# Try clicking the container/combobox to reveal the input
		from_container = await first_by_selectors(
			[
				"div[role='combobox'][aria-label*='where from' i]",
				"div[role='combobox'][aria-label*='from' i]",
				"button[aria-label*='where from' i]",
				"button[aria-label*='from' i]",
			]
		)
		if from_container:
			await from_container.click()
			await asyncio.sleep(0.8)
			from_input = await first_by_selectors(
				[
					"input[aria-label*='where from' i]",
					"input[aria-label*='from' i]",
					"input[aria-label*='departure' i]",
					"input[placeholder*='where from' i]",
					"input[placeholder*='from' i]",
				]
			)

	if from_input:
		await from_input.click()
		await asyncio.sleep(0.3)
		await from_input.fill('London')
		await asyncio.sleep(1.2)
		# Confirm the first suggestion (usually selects "London, United Kingdom (LON)")
		await target.press('Enter')
		await asyncio.sleep(1.2)

	# Now set the "To" field
	to_input = await first_by_selectors(
		[
			"input[aria-label*='where to' i]",
			"input[aria-label*='to' i]",
			"input[aria-label*='destination' i]",
			"input[placeholder*='where to' i]",
			"input[placeholder*='to' i]",
		]
	)
	if not to_input:
		to_container = await first_by_selectors(
			[
				"div[role='combobox'][aria-label*='where to' i]",
				"div[role='combobox'][aria-label*='to' i]",
				"button[aria-label*='where to' i]",
				"button[aria-label*='to' i]",
			]
		)
		if to_container:
			await to_container.click()
			await asyncio.sleep(0.8)
			to_input = await first_by_selectors(
				[
					"input[aria-label*='where to' i]",
					"input[aria-label*='to' i]",
					"input[aria-label*='destination' i]",
					"input[placeholder*='where to' i]",
					"input[placeholder*='to' i]",
				]
			)

	if to_input:
		await to_input.click()
		await asyncio.sleep(0.3)
		await to_input.fill('New York')
		await asyncio.sleep(1.2)
		await target.press('Enter')
		await asyncio.sleep(2.0)

	# Optional: take a screenshot after selection
	# img_b64 = await target.screenshot(format="png")
	# print(img_b64[:100])  # preview

	# At this point, the page should be set to flights from London to New York.


### END OF AI WRITTEN PART


async def main():
	from browser_use.browser.session import BrowserSession

	browser_session = BrowserSession()
	await browser_session.start()
	client = browser_session.cdp_client

	await executor(client)


if __name__ == '__main__':
	asyncio.run(main())
