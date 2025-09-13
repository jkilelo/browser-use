"""Website insights service for capturing and retrieving site-specific feedback."""

import logging
from typing import Any

import aiohttp
from pydantic import BaseModel

from browser_use.config import CONFIG
from browser_use.llm.base import BaseChatModel
from browser_use.llm.messages import BaseMessage, UserMessage

logger = logging.getLogger(__name__)


class WebsiteInsight(BaseModel):
	"""Model for storing website insights."""

	domain: str
	strategy_notes: str
	success_factors: str
	improvement_areas: str
	timestamp: str


def extract_core_domain(url: str) -> str:
	"""
	Extract the core domain from a URL, removing http/https, www, and subdomains.

	Args:
	    url: The URL to extract domain from

	Returns:
	    Core domain (e.g., "example.com")
	"""
	if not url:
		return ''

	# Remove protocol if present
	if '://' in url:
		url = url.split('://', 1)[1]

	# Remove www prefix
	if url.startswith('www.'):
		url = url[4:]

	# Extract domain part (before first slash or query)
	domain = url.split('/')[0].split('?')[0]

	# For subdomains like "subdomain.example.com", try to get the root domain
	# This is a simple heuristic - for production use, consider using a proper library
	parts = domain.split('.')
	if len(parts) >= 2:
		# Take the last two parts for simple cases (example.com)
		# This works for most common cases but might not work for complex TLDs
		return '.'.join(parts[-2:])

	return domain


class WebsiteInsightsService:
	"""Service for storing and retrieving website-specific insights."""

	def __init__(self):
		"""Initialize the insights service."""
		self.api_key = getattr(CONFIG, 'WEBSITE_INSIGHTS_API_KEY', None)
		self.base_url = 'https://api.jsonbin.io/v3/b'
		self.enabled = bool(self.api_key)

		if not self.enabled:
			logger.warning('Website insights service disabled - no WEBSITE_INSIGHTS_API_KEY environment variable found')
		else:
			api_key_preview = self.api_key[:10] + '...' if self.api_key and len(self.api_key) > 10 else 'short key'
			logger.debug(f'Website insights service enabled with API key: {api_key_preview}')

	async def analyze_run_results(
		self, llm: BaseChatModel, domain: str, last_input_messages: list[Any] | None, task: str
	) -> WebsiteInsight | None:
		"""
		Analyze the agent run results and generate insights.

		Args:
		    llm: The language model to use for analysis
		    domain: The website domain
		    last_input_messages: The final messages sent to the LLM (most recent context)
		    task: The original task

		Returns:
		    WebsiteInsight object or None if analysis fails
		"""
		if not self.enabled:
			return None

		try:
			# Format the last input for analysis
			formatted_context = self._format_messages_for_analysis(last_input_messages or [])

			# Create analysis prompt
			analysis_prompt = f"""
Analyze this browser automation run for domain: {domain}

Original Task: {task}

Final context and reasoning from the agent:
{formatted_context}

Please provide a brief analysis covering:
1. Strategy Notes: What approach was taken 
2. Success Factors: What worked well in the strategy
3. Improvement Areas: What could be done better next time for this website

Keep it concise and focused on actionable insights for future runs on this domain.
Focus on strategy patterns, not specific data values.
"""

			# Call LLM for analysis
			messages: list[BaseMessage] = [UserMessage(content=analysis_prompt)]
			response = await llm.ainvoke(messages)

			if not response or not response.completion:
				logger.warning('No response from LLM for website analysis')
				return None

			analysis_text = response.completion

			# Parse the response (simple parsing - could be made more robust)
			strategy_notes = self._extract_section(analysis_text, 'Strategy Notes:')
			success_factors = self._extract_section(analysis_text, 'Success Factors:')
			improvement_areas = self._extract_section(analysis_text, 'Improvement Areas:')

			from datetime import datetime

			return WebsiteInsight(
				domain=domain,
				strategy_notes=strategy_notes,
				success_factors=success_factors,
				improvement_areas=improvement_areas,
				timestamp=datetime.utcnow().isoformat(),
			)

		except Exception as e:
			logger.error(f'Error analyzing run results: {e}')
			return None

	def _extract_section(self, text: str, section_header: str) -> str:
		"""Extract a section from the analysis text."""
		lines = text.split('\n')
		section_lines = []
		in_section = False

		for line in lines:
			if section_header.lower() in line.lower():
				in_section = True
				# Include the content after the header on the same line
				content_after_header = line.split(':', 1)[-1].strip()
				if content_after_header:
					section_lines.append(content_after_header)
				continue

			if in_section:
				# Stop when we hit another section header
				if any(header in line.lower() for header in ['strategy notes:', 'success factors:', 'improvement areas:']):
					break
				if line.strip():
					section_lines.append(line.strip())

		return ' '.join(section_lines).strip() if section_lines else 'No information provided'

	def _format_messages_for_analysis(self, messages: list[Any]) -> str:
		"""Format the last input messages for analysis."""
		if not messages:
			return 'No context available'

		formatted_parts = []

		for msg in messages[-3:]:  # Last 3 messages to keep it focused
			if hasattr(msg, '__class__'):
				msg_type = msg.__class__.__name__
			else:
				msg_type = 'Message'

			if hasattr(msg, 'content'):
				content = str(msg.content)
				# Truncate very long content to keep analysis focused
				if len(content) > 1000:
					content = content[:1000] + '...'
				formatted_parts.append(f'{msg_type}: {content}')
			elif hasattr(msg, 'text'):
				content = str(msg.text)
				if len(content) > 1000:
					content = content[:1000] + '...'
				formatted_parts.append(f'{msg_type}: {content}')

		return '\n\n'.join(formatted_parts) if formatted_parts else 'No message content available'

	async def store_insight(self, insight: WebsiteInsight) -> bool:
		"""
		Store an insight in the remote database.

		Args:
		    insight: The insight to store

		Returns:
		    True if stored successfully, False otherwise
		"""
		if not self.enabled:
			logger.warning('Cannot store insight - WEBSITE_INSIGHTS_API_KEY environment variable not set')
			return False

		try:
			# Get existing insights for this domain
			existing_insights = await self.get_insights(insight.domain)

			# Add new insight to the list
			existing_insights.append(insight.model_dump())

			# Keep only the last 10 insights per domain
			if len(existing_insights) > 10:
				existing_insights = existing_insights[-10:]

			# Initialize bin cache if not exists
			if not hasattr(self, '_bin_cache'):
				self._bin_cache = {}

			# Store back to JSONBin
			bin_name = f'website_insights_{insight.domain.replace(".", "_")}'
			headers = {'Content-Type': 'application/json', 'X-Master-Key': self.api_key, 'X-Bin-Name': bin_name}
			data = {'insights': existing_insights}

			async with aiohttp.ClientSession() as session:
				async with session.post(self.base_url, json=data, headers=headers) as response:
					if response.status in [200, 201]:
						result = await response.json()
						bin_id = result.get('metadata', {}).get('id')
						if bin_id:
							# Cache the bin ID for future use
							self._bin_cache[insight.domain] = bin_id
							logger.debug(f'Stored insight for domain: {insight.domain} (bin: {bin_id})')
						else:
							logger.debug(f'Stored insight for domain: {insight.domain}')
						return True
					elif response.status == 401:
						logger.error('Failed to store insight: 401 Unauthorized. Check your WEBSITE_INSIGHTS_API_KEY is valid.')
						return False
					else:
						logger.warning(f'Failed to store insight: {response.status}')
						return False

		except Exception as e:
			logger.error(f'Error storing insight: {e}')
			return False

	async def get_insights(self, domain: str, limit: int = 3) -> list[dict]:
		"""
		Get recent insights for a domain.

		Args:
		    domain: The domain to get insights for
		    limit: Maximum number of insights to return

		Returns:
		    List of insight dictionaries
		"""
		if not self.enabled:
			return []

		try:
			headers = {'X-Master-Key': self.api_key or ''}
			bin_id = f'website_insights_{domain.replace(".", "_")}'
			async with aiohttp.ClientSession() as session:
				async with session.get(f'{self.base_url}/{bin_id}', headers=headers) as response:
					if response.status == 200:
						data = await response.json()
						insights = data.get('record', {}).get('insights', [])
						return insights[-limit:] if insights else []
					elif response.status == 404:
						return []
			# If no cached bin ID or bin was not found, return empty (will be created when storing)
			return []

		except Exception as e:
			logger.debug(f'Could not retrieve insights for {domain}: {e}')

		return []

	def format_insights_for_task(self, insights: list[dict], domain: str) -> str:
		"""
		Format insights for injection into a task prompt.

		Args:
		    insights: List of insight dictionaries
		    domain: The domain these insights are for

		Returns:
		    Formatted string to add to task prompt
		"""
		if not insights:
			return ''

		formatted_insights = []
		for insight in insights[-3:]:  # Last 3 insights
			formatted_insights.append(
				f'- Strategy: {insight.get("strategy_notes", "N/A")}\n'
				f'- Success: {insight.get("success_factors", "N/A")}\n'
				f'- Improve: {insight.get("improvement_areas", "N/A")}'
			)

		return f"""

--- Previous Experience with {domain} ---
Note: This information is from previous automation runs on this website. 
Use it as guidance if relevant, but it may not apply to your current task.

{chr(10).join(formatted_insights)}
--- End Previous Experience ---

"""
