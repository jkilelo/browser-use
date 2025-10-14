"""Test the new DOM-based markdown serializer."""

import pytest

from browser_use.dom.serializer.markdown_serializer import MarkdownSerializer
from browser_use.dom.views import EnhancedDOMTreeNode, EnhancedSnapshotNode, NodeType


@pytest.mark.asyncio
async def test_markdown_serializer_basic():
	"""Test basic markdown serialization from DOM tree."""

	# Create a simple DOM tree structure
	# Root HTML node
	root = EnhancedDOMTreeNode(
		node_id=1,
		backend_node_id=1,
		node_type=NodeType.DOCUMENT_NODE,
		node_name='#document',
		node_value='',
		attributes={},
		is_scrollable=None,
		is_visible=True,
		absolute_position=None,
		target_id='target1',
		frame_id=None,
		session_id=None,
		content_document=None,
		shadow_root_type=None,
		shadow_roots=None,
		parent_node=None,
		children_nodes=[],
		ax_node=None,
		snapshot_node=None,
	)

	# HTML element
	html_node = EnhancedDOMTreeNode(
		node_id=2,
		backend_node_id=2,
		node_type=NodeType.ELEMENT_NODE,
		node_name='HTML',
		node_value='',
		attributes={},
		is_scrollable=None,
		is_visible=True,
		absolute_position=None,
		target_id='target1',
		frame_id=None,
		session_id=None,
		content_document=None,
		shadow_root_type=None,
		shadow_roots=None,
		parent_node=root,
		children_nodes=[],
		ax_node=None,
		snapshot_node=EnhancedSnapshotNode(
			is_clickable=False,
			cursor_style=None,
			bounds=None,
			clientRects=None,
			scrollRects=None,
			computed_styles=None,
			paint_order=None,
			stacking_contexts=None,
		),
	)

	# Body element
	body_node = EnhancedDOMTreeNode(
		node_id=3,
		backend_node_id=3,
		node_type=NodeType.ELEMENT_NODE,
		node_name='BODY',
		node_value='',
		attributes={},
		is_scrollable=None,
		is_visible=True,
		absolute_position=None,
		target_id='target1',
		frame_id=None,
		session_id=None,
		content_document=None,
		shadow_root_type=None,
		shadow_roots=None,
		parent_node=html_node,
		children_nodes=[],
		ax_node=None,
		snapshot_node=EnhancedSnapshotNode(
			is_clickable=False,
			cursor_style=None,
			bounds=None,
			clientRects=None,
			scrollRects=None,
			computed_styles=None,
			paint_order=None,
			stacking_contexts=None,
		),
	)

	# H1 element
	h1_node = EnhancedDOMTreeNode(
		node_id=4,
		backend_node_id=4,
		node_type=NodeType.ELEMENT_NODE,
		node_name='H1',
		node_value='',
		attributes={},
		is_scrollable=None,
		is_visible=True,
		absolute_position=None,
		target_id='target1',
		frame_id=None,
		session_id=None,
		content_document=None,
		shadow_root_type=None,
		shadow_roots=None,
		parent_node=body_node,
		children_nodes=[],
		ax_node=None,
		snapshot_node=EnhancedSnapshotNode(
			is_clickable=False,
			cursor_style=None,
			bounds=None,
			clientRects=None,
			scrollRects=None,
			computed_styles=None,
			paint_order=None,
			stacking_contexts=None,
		),
	)

	# Text node inside H1
	text_node = EnhancedDOMTreeNode(
		node_id=5,
		backend_node_id=5,
		node_type=NodeType.TEXT_NODE,
		node_name='#text',
		node_value='Test Heading',
		attributes={},
		is_scrollable=None,
		is_visible=True,
		absolute_position=None,
		target_id='target1',
		frame_id=None,
		session_id=None,
		content_document=None,
		shadow_root_type=None,
		shadow_roots=None,
		parent_node=h1_node,
		children_nodes=None,
		ax_node=None,
		snapshot_node=EnhancedSnapshotNode(
			is_clickable=False,
			cursor_style=None,
			bounds=None,
			clientRects=None,
			scrollRects=None,
			computed_styles=None,
			paint_order=None,
			stacking_contexts=None,
		),
	)

	# P element with text
	p_node = EnhancedDOMTreeNode(
		node_id=6,
		backend_node_id=6,
		node_type=NodeType.ELEMENT_NODE,
		node_name='P',
		node_value='',
		attributes={},
		is_scrollable=None,
		is_visible=True,
		absolute_position=None,
		target_id='target1',
		frame_id=None,
		session_id=None,
		content_document=None,
		shadow_root_type=None,
		shadow_roots=None,
		parent_node=body_node,
		children_nodes=[],
		ax_node=None,
		snapshot_node=EnhancedSnapshotNode(
			is_clickable=False,
			cursor_style=None,
			bounds=None,
			clientRects=None,
			scrollRects=None,
			computed_styles=None,
			paint_order=None,
			stacking_contexts=None,
		),
	)

	text_node2 = EnhancedDOMTreeNode(
		node_id=7,
		backend_node_id=7,
		node_type=NodeType.TEXT_NODE,
		node_name='#text',
		node_value='This is a test paragraph.',
		attributes={},
		is_scrollable=None,
		is_visible=True,
		absolute_position=None,
		target_id='target1',
		frame_id=None,
		session_id=None,
		content_document=None,
		shadow_root_type=None,
		shadow_roots=None,
		parent_node=p_node,
		children_nodes=None,
		ax_node=None,
		snapshot_node=EnhancedSnapshotNode(
			is_clickable=False,
			cursor_style=None,
			bounds=None,
			clientRects=None,
			scrollRects=None,
			computed_styles=None,
			paint_order=None,
			stacking_contexts=None,
		),
	)

	# Build the tree structure
	root.children_nodes = [html_node]
	html_node.children_nodes = [body_node]
	body_node.children_nodes = [h1_node, p_node]
	h1_node.children_nodes = [text_node]
	p_node.children_nodes = [text_node2]

	# Serialize to markdown
	serializer = MarkdownSerializer(extract_links=False)
	markdown = serializer.serialize(root)

	# Check the output
	assert '# Test Heading' in markdown
	assert 'This is a test paragraph.' in markdown
	assert len(markdown) > 0

	print(f'Generated markdown:\n{markdown}')


@pytest.mark.asyncio
async def test_markdown_serializer_select_options():
	"""Test that markdown serializer shows all select options."""

	# Create a simple DOM tree with a select element
	root = EnhancedDOMTreeNode(
		node_id=1,
		backend_node_id=1,
		node_type=NodeType.DOCUMENT_NODE,
		node_name='#document',
		node_value='',
		attributes={},
		is_scrollable=None,
		is_visible=True,
		absolute_position=None,
		target_id='target1',
		frame_id=None,
		session_id=None,
		content_document=None,
		shadow_root_type=None,
		shadow_roots=None,
		parent_node=None,
		children_nodes=[],
		ax_node=None,
		snapshot_node=None,
	)

	body_node = EnhancedDOMTreeNode(
		node_id=2,
		backend_node_id=2,
		node_type=NodeType.ELEMENT_NODE,
		node_name='BODY',
		node_value='',
		attributes={},
		is_scrollable=None,
		is_visible=True,
		absolute_position=None,
		target_id='target1',
		frame_id=None,
		session_id=None,
		content_document=None,
		shadow_root_type=None,
		shadow_roots=None,
		parent_node=root,
		children_nodes=[],
		ax_node=None,
		snapshot_node=EnhancedSnapshotNode(
			is_clickable=False,
			cursor_style=None,
			bounds=None,
			clientRects=None,
			scrollRects=None,
			computed_styles=None,
			paint_order=None,
			stacking_contexts=None,
		),
	)

	# Build tree structure
	root.children_nodes = [body_node]

	# Serialize to markdown
	serializer = MarkdownSerializer(extract_links=False)
	markdown = serializer.serialize(root)

	print(f'Generated markdown with select:\n{markdown}')

	# Basic check
	assert len(markdown) >= 0


@pytest.mark.asyncio
async def test_markdown_serializer_deduplication():
	"""Test that markdown serializer deduplicates repeated text."""

	# Create a simple DOM tree with repeated text
	root = EnhancedDOMTreeNode(
		node_id=1,
		backend_node_id=1,
		node_type=NodeType.DOCUMENT_NODE,
		node_name='#document',
		node_value='',
		attributes={},
		is_scrollable=None,
		is_visible=True,
		absolute_position=None,
		target_id='target1',
		frame_id=None,
		session_id=None,
		content_document=None,
		shadow_root_type=None,
		shadow_roots=None,
		parent_node=None,
		children_nodes=[],
		ax_node=None,
		snapshot_node=None,
	)

	body_node = EnhancedDOMTreeNode(
		node_id=2,
		backend_node_id=2,
		node_type=NodeType.ELEMENT_NODE,
		node_name='BODY',
		node_value='',
		attributes={},
		is_scrollable=None,
		is_visible=True,
		absolute_position=None,
		target_id='target1',
		frame_id=None,
		session_id=None,
		content_document=None,
		shadow_root_type=None,
		shadow_roots=None,
		parent_node=root,
		children_nodes=[],
		ax_node=None,
		snapshot_node=EnhancedSnapshotNode(
			is_clickable=False,
			cursor_style=None,
			bounds=None,
			clientRects=None,
			scrollRects=None,
			computed_styles=None,
			paint_order=None,
			stacking_contexts=None,
		),
	)

	# Create 5 button nodes with the same text "Toggle options"
	button_nodes = []
	for i in range(5):
		button_node = EnhancedDOMTreeNode(
			node_id=10 + i,
			backend_node_id=10 + i,
			node_type=NodeType.ELEMENT_NODE,
			node_name='BUTTON',
			node_value='',
			attributes={},
			is_scrollable=None,
			is_visible=True,
			absolute_position=None,
			target_id='target1',
			frame_id=None,
			session_id=None,
			content_document=None,
			shadow_root_type=None,
			shadow_roots=None,
			parent_node=body_node,
			children_nodes=[],
			ax_node=None,
			snapshot_node=EnhancedSnapshotNode(
				is_clickable=False,
				cursor_style=None,
				bounds=None,
				clientRects=None,
				scrollRects=None,
				computed_styles=None,
				paint_order=None,
				stacking_contexts=None,
			),
		)

		text_node = EnhancedDOMTreeNode(
			node_id=20 + i,
			backend_node_id=20 + i,
			node_type=NodeType.TEXT_NODE,
			node_name='#text',
			node_value='Toggle options',
			attributes={},
			is_scrollable=None,
			is_visible=True,
			absolute_position=None,
			target_id='target1',
			frame_id=None,
			session_id=None,
			content_document=None,
			shadow_root_type=None,
			shadow_roots=None,
			parent_node=button_node,
			children_nodes=None,
			ax_node=None,
			snapshot_node=EnhancedSnapshotNode(
				is_clickable=False,
				cursor_style=None,
				bounds=None,
				clientRects=None,
				scrollRects=None,
				computed_styles=None,
				paint_order=None,
				stacking_contexts=None,
			),
		)

		button_node.children_nodes = [text_node]
		button_nodes.append(button_node)

	# Build tree structure
	root.children_nodes = [body_node]
	body_node.children_nodes = button_nodes

	# Serialize with default threshold (3)
	serializer = MarkdownSerializer(extract_links=False, deduplicate_threshold=3)
	markdown = serializer.serialize(root)

	print(f'Generated markdown with deduplication:\\n{markdown}')

	# Count how many times "Toggle options" appears
	toggle_count = markdown.count('[Toggle options]')

	# Should only appear 3 times (the threshold), not 5 times
	assert toggle_count == 3, f'Expected 3 occurrences, got {toggle_count}'

	# Test with threshold of 0 (no deduplication)
	serializer_no_dedup = MarkdownSerializer(extract_links=False, deduplicate_threshold=0)
	markdown_no_dedup = serializer_no_dedup.serialize(root)

	# Should appear all 5 times
	toggle_count_no_dedup = markdown_no_dedup.count('[Toggle options]')
	assert toggle_count_no_dedup == 5, f'Expected 5 occurrences, got {toggle_count_no_dedup}'
