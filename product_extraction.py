# Generated from browser-use code-use session
import asyncio
from browser_use import BrowserSession
from browser_use.code_use import create_namespace

async def main():
	# Initialize browser and namespace
	browser = BrowserSession()
	await browser.start()

	# Create namespace with all browser control functions
	namespace = create_namespace(browser)

	# Extract functions from namespace for direct access
	navigate = namespace["navigate"]
	click = namespace["click"]
	input_text = namespace["input"]
	evaluate = namespace["evaluate"]
	search = namespace["search"]
	extract = namespace["extract"]
	scroll = namespace["scroll"]
	done = namespace["done"]
	go_back = namespace["go_back"]
	wait = namespace["wait"]
	screenshot = namespace["screenshot"]
	find_text = namespace["find_text"]
	switch_tab = namespace["switch"]
	close_tab = namespace["close"]
	dropdown_options = namespace["dropdown_options"]
	select_dropdown = namespace["select_dropdown"]
	upload_file = namespace["upload_file"]
	send_keys = namespace["send_keys"]

	# Cell 1
	await navigate("https://www.flipkart.com")

	# Cell 2
	await asyncio.sleep(3) # Wait for dynamic content to load
	page_info = await evaluate('''
	(function(){
	  const categories = Array.from(document.querySelectorAll('div[data-tracking-id] a, a[href*="category"]')).map(a => ({
	    text: a.textContent.trim(),
	    href: a.href
	  }));
	  const searchInput = document.querySelector('input[title="Search for products, brands and more"]');
	  return {
	    title: document.title,
	    categories: categories.filter(c => c.text.length > 0).slice(0, 20), // Limit to 20 for brevity
	    searchInputExists: !!searchInput
	  };
	})()
	''')
	print(json.dumps(page_info, indent=2))

	# Cell 3
	# No interactive elements were provided in the last state, so I'll assume the page structure is complex.
	# I will try to find the search bar using a more specific selector, as it's the most reliable way to navigate on Flipkart.
	search_input_js = '''
	(function(){
	  const searchInput = document.querySelector('input[placeholder="Search for Products, Brands and More"]');
	  if (searchInput) {
	    return {
	      exists: true,
	      index: searchInput.getAttribute('data-index') // This won't work in evaluate, but I'll try to find the element
	    };
	  }
	  return {exists: false};
	})()
	'''
	search_info = await evaluate(search_input_js)
	print(search_info)

	# Cell 4
	# I will rely on the provided interactive elements now.
	# I need to find the search input element.
	# Based on typical Flipkart structure, the search input is usually the first or second input field.
	# Since I don't have the interactive elements, I will assume the search input is index 1 or 2 and try to input text.
	# I will search for "Books" first.
	# Let's try to find the search input by its placeholder text in the visible elements.
	# Assuming the search input is the first or second input element. I'll try index 1.
	# Since I don't have the current interactive elements, I must rely on the previous state's output, which is missing.
	# I will assume the search input is the first available input element [1] and search for "Books".
	try:
	    await input(1, "Books")
	    await send_keys('\n') # Press Enter to search
	    print("Attempted to search for 'Books' using input index 1.")
	except Exception as e:
	    print(f"Failed to input text at index 1. Error: {e}")
	    # If it fails, I'll try index 2 in the next step, but for now, I'll wait for the new state.

	# Cell 5
	# Current browser state is not visible to me, but I must proceed.
	# I will try to find the search input index by inspecting the structure again, assuming the structure is standard.
	# Since I failed to input at index 1, I will try to find the search input element in the next state.
	# I will try to find the search input by its placeholder text in the visible elements.
	# I will try index 2, as it's a common alternative.
	try:
	    await input(2, "Books")
	    await send_keys('\n') # Press Enter to search
	    print("Attempted to search for 'Books' using input index 2.")
	except Exception as e:
	    print(f"Failed to input text at index 2. Error: {e}")
	    # If it fails again, I will wait for the next state to analyze the elements.

	# Cell 6
	# 1. Input "Books" into the search field
	await evaluate('''
	(function(){
	  const searchInput = document.querySelector('input[placeholder="Search for Products, Brands and More"]');
	  if (searchInput) {
	    searchInput.value = "Books";
	    // Dispatch an input event to ensure the value is registered
	    searchInput.dispatchEvent(new Event('input', { bubbles: true }));
	  }
	})()
	''')
	# 2. Find and click the search button (usually a button or an SVG inside a button/div)
	# The search button is typically next to the input field. I'll look for a common selector for the search icon/button.
	search_button_index = await evaluate('''
	(function(){
	  // Common selector for Flipkart search button/icon
	  const searchButton = document.querySelector('button[type="submit"]');
	  if (searchButton) {
	    // Flipkart often uses a button with an SVG inside. We need the index of the interactive element.
	    // Since we can't get the index via JS, we'll try to click it via JS.
	    searchButton.click();
	    return true;
	  }
	  return false;
	})()
	''')
	if search_button_index is True:
	    print("Successfully searched for 'Books' using JavaScript.")
	else:
	    print("Failed to find and click the search button via JavaScript. Waiting for new state to find the index.")
	await asyncio.sleep(5) # Wait for search results to load

	# Cell 7
	def parse_price(price_str):
	    """Cleans and converts price string (e.g., '₹1,299') to a float."""
	    if not price_str:
	        return None
	    return float(price_str.replace('₹', '').replace(',', '').strip())
	def calculate_discount(mrp, deal_price):
	    """Calculates discount percentage."""
	    if mrp is None or deal_price is None or mrp <= deal_price:
	        return 0.0
	    return round(((mrp - deal_price) / mrp) * 100, 2)
	# Global list to store all collected products
	all_products = []
	target_books = 15
	js_extract_products = '''
	(function(){
	  const products = [];
	  // Select all product cards/containers on the search results page
	  const productElements = document.querySelectorAll('div[data-id]');
	  productElements.forEach(el => {
	    try {
	      // Product URL
	      const urlEl = el.querySelector('a[rel="noopener noreferrer"]');
	      const productUrl = urlEl ? urlEl.href.split('?')[0] : null;
	      // Product Name/Description
	      const nameEl = el.querySelector('a.s1Q9rs, a.s1Q9rs, a[title]');
	      const productName = nameEl ? nameEl.title || nameEl.textContent.trim() : null;
	      // Prices and Discount
	      const dealPriceEl = el.querySelector('div._30jeq3');
	      const mrpEl = el.querySelector('div._3I9_wc');
	      const discountEl = el.querySelector('div._3Ay6Sb span');
	      const dealPriceText = dealPriceEl ? dealPriceEl.textContent.trim() : null;
	      const mrpText = mrpEl ? mrpEl.textContent.trim() : null;
	      const discountText = discountEl ? discountEl.textContent.trim() : null;
	      if (productUrl && productName && dealPriceText) {
	        products.push({
	          productUrl: productUrl,
	          productName: productName,
	          mrpText: mrpText,
	          dealPriceText: dealPriceText,
	          discountText: discountText
	        });
	      }
	    } catch (e) {
	      // Skip if parsing fails for a product
	    }
	  });
	  return products;
	})()
	'''
	raw_products = await evaluate(js_extract_products)
	# Process the raw data
	books_products = []
	for p in raw_products:
	    mrp = parse_price(p['mrpText'])
	    deal_price = parse_price(p['dealPriceText'])
	    discount_percentage = calculate_discount(mrp, deal_price)
	    books_products.append({
	        'category': 'Books & Media',
	        'productUrl': p['productUrl'],
	        'productName': p['productName'],
	        'mrp': mrp,
	        'dealPrice': deal_price,
	        'discountPercentage': discount_percentage,
	        'discountText': p['discountText'] # Keep the original text for verification
	    })
	# Filter for products with a discount and limit to target
	books_products = sorted([p for p in books_products if p['discountPercentage'] > 0], key=lambda x: x['discountPercentage'], reverse=True)
	books_products = books_products[:target_books]
	all_products.extend(books_products)
	print(f"Collected {len(books_products)} products for Books & Media.")
	print(json.dumps(books_products[:5], indent=2))

	# Cell 8
	# Re-evaluating the selectors for the search results page
	js_re_evaluate = '''
	(function(){
	  const products = [];
	  // Try to find common product card containers. Flipkart often uses divs with specific classes.
	  // Looking for containers that hold the link, name, and price.
	  const productContainers = document.querySelectorAll('div._1AtVbE, div.cPHDOP, div.DOJ4zN');
	  productContainers.forEach(container => {
	    // Find the main product link (which usually contains the name and URL)
	    const linkEl = container.querySelector('a._2rp_hq');
	    if (!linkEl) return;
	    const productUrl = linkEl.href.split('?')[0];
	    const productName = linkEl.querySelector('div.s1Q9rs, div._4rR01T, a[title]')?.title || linkEl.querySelector('div.s1Q9rs, div._4rR01T, a[title]')?.textContent.trim();
	    // Find price elements
	    const dealPriceEl = container.querySelector('div._30jeq3'); // Current selling price
	    const mrpEl = container.querySelector('div._3I9_wc');      // Actual price (MRP)
	    const discountEl = container.querySelector('div._3Ay6Sb');  // Discount percentage
	    const dealPriceText = dealPriceEl ? dealPriceEl.textContent.trim() : null;
	    const mrpText = mrpEl ? mrpEl.textContent.trim() : null;
	    const discountText = discountEl ? discountEl.textContent.trim() : null;
	    if (productUrl && productName && dealPriceText) {
	      products.push({
	        productUrl: productUrl,
	        productName: productName,
	        mrpText: mrpText,
	        dealPriceText: dealPriceText,
	        discountText: discountText
	      });
	    }
	  });
	  return products.slice(0, 10); // Return first 10 for inspection
	})()
	'''
	re_evaluated_products = await evaluate(js_re_evaluate)
	print(f"Found {len(re_evaluated_products)} products with new selectors.")
	print(json.dumps(re_evaluated_products, indent=2))
	if len(re_evaluated_products) == 0:
	    # If still zero, I will try to find the next page button and navigate to the next category.
	    # For now, I'll assume the selectors are correct and try to re-run the full extraction logic.
	    pass

	# Cell 9
	# 1. Input "Sports & Fitness" into the search field
	await evaluate('''
	(function(){
	  const searchInput = document.querySelector('input[placeholder="Search for Products, Brands and More"]');
	  if (searchInput) {
	    searchInput.value = "Sports & Fitness";
	    searchInput.dispatchEvent(new Event('input', { bubbles: true }));
	  }
	})()
	''')
	# 2. Click the search button
	search_button_clicked = await evaluate('''
	(function(){
	  const searchButton = document.querySelector('button[type="submit"]');
	  if (searchButton) {
	    searchButton.click();
	    return true;
	  }
	  return false;
	})()
	''')
	if search_button_clicked:
	    print("Successfully searched for 'Sports & Fitness' using JavaScript.")
	else:
	    print("Failed to find and click the search button via JavaScript.")
	await asyncio.sleep(5) # Wait for search results to load

	# Cell 10
	target_sports = 15
	js_extract_products_sports = '''
	(function(){
	  const products = [];
	  // Try to find common product card containers.
	  // Using a broader selector for the main grid items.
	  const productContainers = document.querySelectorAll('div[data-id], div._1AtVbE, div.cPHDOP, div.DOJ4zN');
	  productContainers.forEach(container => {
	    try {
	      // Find the main product link (which usually contains the name and URL)
	      const linkEl = container.querySelector('a._2rp_hq, a.s1Q9rs, a._2UzuFa');
	      if (!linkEl) return;
	      const productUrl = linkEl.href.split('?')[0];
	      // Try to get the name from title attribute or text content
	      const productName = linkEl.title || linkEl.querySelector('div.s1Q9rs, div._4rR01T, a[title]')?.textContent.trim() || linkEl.textContent.trim();
	      // Find price elements
	      const dealPriceEl = container.querySelector('div._30jeq3'); // Current selling price
	      const mrpEl = container.querySelector('div._3I9_wc');      // Actual price (MRP)
	      const discountEl = container.querySelector('div._3Ay6Sb');  // Discount percentage
	      const dealPriceText = dealPriceEl ? dealPriceEl.textContent.trim() : null;
	      const mrpText = mrpEl ? mrpEl.textContent.trim() : null;
	      const discountText = discountEl ? discountEl.textContent.trim() : null;
	      if (productUrl && productName && dealPriceText) {
	        products.push({
	          productUrl: productUrl,
	          productName: productName,
	          mrpText: mrpText,
	          dealPriceText: dealPriceText,
	          discountText: discountText
	        });
	      }
	    } catch (e) {
	      // Skip product if error occurs
	    }
	  });
	  return products;
	})()
	'''
	raw_products_sports = await evaluate(js_extract_products_sports)
	# Process the raw data
	sports_products = []
	for p in raw_products_sports:
	    mrp = parse_price(p['mrpText'])
	    deal_price = parse_price(p['dealPriceText'])
	    discount_percentage = calculate_discount(mrp, deal_price)
	    sports_products.append({
	        'category': 'Sports & Fitness',
	        'productUrl': p['productUrl'],
	        'productName': p['productName'],
	        'mrp': mrp,
	        'dealPrice': deal_price,
	        'discountPercentage': discount_percentage,
	        'discountText': p['discountText']
	    })
	# Filter for products with a discount and limit to target
	sports_products = sorted([p for p in sports_products if p['discountPercentage'] > 0], key=lambda x: x['discountPercentage'], reverse=True)
	sports_products = sports_products[:target_sports]
	all_products.extend(sports_products)
	print(f"Collected {len(sports_products)} products for Sports & Fitness.")
	print(f"Total products collected so far: {len(all_products)}")
	print(json.dumps(sports_products[:5], indent=2))

	await browser.stop()

if __name__ == '__main__':
	asyncio.run(main())
