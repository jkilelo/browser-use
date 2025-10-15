"""Data models for code-use mode."""

from enum import Enum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field
from uuid_extensions import uuid7str


class CellType(str, Enum):
	"""Type of notebook cell."""

	CODE = 'code'
	MARKDOWN = 'markdown'


class ExecutionStatus(str, Enum):
	"""Execution status of a cell."""

	PENDING = 'pending'
	RUNNING = 'running'
	SUCCESS = 'success'
	ERROR = 'error'


class CodeCell(BaseModel):
	"""Represents a code cell in the notebook-like execution."""

	model_config = ConfigDict(extra='forbid')

	id: str = Field(default_factory=uuid7str)
	cell_type: CellType = CellType.CODE
	source: str = Field(description='The code to execute')
	output: str | None = Field(default=None, description='The output of the code execution')
	execution_count: int | None = Field(default=None, description='The execution count')
	status: ExecutionStatus = Field(default=ExecutionStatus.PENDING)
	error: str | None = Field(default=None, description='Error message if execution failed')
	browser_state: str | None = Field(default=None, description='Browser state after execution')


class NotebookSession(BaseModel):
	"""Represents a notebook-like session."""

	model_config = ConfigDict(extra='forbid')

	id: str = Field(default_factory=uuid7str)
	cells: list[CodeCell] = Field(default_factory=list)
	current_execution_count: int = Field(default=0)
	namespace: dict[str, Any] = Field(default_factory=dict, description='Current namespace state')

	def add_cell(self, source: str) -> CodeCell:
		"""Add a new code cell to the session."""
		cell = CodeCell(source=source)
		self.cells.append(cell)
		return cell

	def get_cell(self, cell_id: str) -> CodeCell | None:
		"""Get a cell by ID."""
		for cell in self.cells:
			if cell.id == cell_id:
				return cell
		return None

	def get_latest_cell(self) -> CodeCell | None:
		"""Get the most recently added cell."""
		if self.cells:
			return self.cells[-1]
		return None

	def increment_execution_count(self) -> int:
		"""Increment and return the execution count."""
		self.current_execution_count += 1
		return self.current_execution_count


class NotebookExport(BaseModel):
	"""Export format for Jupyter notebook."""

	model_config = ConfigDict(extra='forbid')

	nbformat: int = Field(default=4)
	nbformat_minor: int = Field(default=5)
	metadata: dict[str, Any] = Field(default_factory=dict)
	cells: list[dict[str, Any]] = Field(default_factory=list)
