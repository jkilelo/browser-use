"""Pydantic models for indexer service."""

from pydantic import BaseModel, ConfigDict, Field


class IndexerInput(BaseModel):
	"""Input for the indexer service."""

	task: str = Field(..., description='The task the agent is trying to accomplish')
	current_url: str = Field(..., description='The current URL the agent is on')

	model_config = ConfigDict(extra='forbid')


class IndexerResult(BaseModel):
	"""Result from the indexer service containing interaction hints."""

	hints: list[str] = Field(default_factory=list, description='List of hints on how to interact with the website')

	model_config = ConfigDict(extra='forbid')
