"""DOM tree diff serializer for showing state changes."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
	from browser_use.dom.views import SimplifiedNode

from browser_use.dom.views import DEFAULT_INCLUDE_ATTRIBUTES


def compute_tree_diff(previous_tree: SimplifiedNode, current_tree: SimplifiedNode) -> str:
	"""Compute diff between two SimplifiedNode trees.

	Shows removed nodes by backend_node_id, added nodes with position + content, and changed nodes with delta.

	Args:
		previous_tree: Previous SimplifiedNode tree
		current_tree: Current SimplifiedNode tree

	Returns:
		Diff showing removed (by ID), added (position + content), and changed (delta) nodes
	"""
	from browser_use.dom.serializer.serializer import DOMTreeSerializer

	diff_sections: list[str] = []

	# Find divergence points
	removed_nodes, added_nodes, changed_nodes = _find_tree_changes(previous_tree, current_tree)

	# Format removed nodes - only show backend_node_id
	if removed_nodes:
		diff_sections.append('## Removed')
		for backend_node_id in removed_nodes:
			diff_sections.append(f'-- {backend_node_id}')
		diff_sections.append('')

	# Format changed nodes - show only what changed
	if changed_nodes:
		diff_sections.append('## Changed')
		for backend_node_id, changes in changed_nodes:
			diff_sections.append(f'!! {backend_node_id}')
			for key, (old_val, new_val) in changes.items():
				diff_sections.append(f'  {key}: {old_val!r} → {new_val!r}')
		diff_sections.append('')

	# Format added nodes - show position (after backend_node_id) and content
	if added_nodes:
		diff_sections.append('## Added')
		for after_id, node in added_nodes:
			subtree_html = DOMTreeSerializer.serialize_tree(node, DEFAULT_INCLUDE_ATTRIBUTES)
			diff_sections.append(f'++ after {after_id}')
			diff_sections.append(subtree_html)
			diff_sections.append('')

	if not diff_sections:
		return 'No DOM changes detected'

	summary = f'# DOM Diff: {len(removed_nodes)} removed, {len(changed_nodes)} changed, {len(added_nodes)} added\n'
	return summary + '\n'.join(diff_sections)


def _find_tree_changes(
	previous_tree: SimplifiedNode,
	current_tree: SimplifiedNode,
	prev_sibling_id: int | None = None,
) -> tuple[list[int], list[tuple[int, SimplifiedNode]], list[tuple[int, dict[str, tuple]]]]:
	"""Find changes between two trees.

	Args:
		previous_tree: Previous SimplifiedNode tree
		current_tree: Current SimplifiedNode tree
		prev_sibling_id: Backend node ID of previous sibling (for positioning added nodes)

	Returns:
		Tuple of (removed_ids, added_nodes_with_position, changed_nodes_with_delta)
		- removed_ids: List of backend_node_id for removed nodes
		- added_nodes_with_position: List of (after_backend_node_id, new_node)
		- changed_nodes_with_delta: List of (backend_node_id, {attr: (old, new)})
	"""
	removed_ids: list[int] = []
	added_nodes: list[tuple[int, SimplifiedNode]] = []
	changed_nodes: list[tuple[int, dict[str, tuple]]] = []

	# Build maps by backend_node_id for quick lookup
	prev_map = _build_node_map(previous_tree)
	curr_map = _build_node_map(current_tree)

	# Find removed nodes (in prev but not in curr) - only track top-level removed nodes
	all_removed_ids = {backend_id for backend_id in prev_map if backend_id not in curr_map}

	# Filter to only top-level removed nodes (whose parents still exist or are also removed)
	for backend_id in all_removed_ids:
		node = prev_map[backend_id]
		# Check if any ancestor is also removed - if so, skip this node
		is_descendant_of_removed = False
		parent = _find_parent(previous_tree, node)
		while parent:
			if parent.original_node.backend_node_id in all_removed_ids:
				is_descendant_of_removed = True
				break
			parent = _find_parent(previous_tree, parent)

		if not is_descendant_of_removed:
			removed_ids.append(backend_id)

	# Find added and changed nodes
	prev_children_ids = [child.original_node.backend_node_id for child in previous_tree.children]

	for i, curr_child in enumerate(current_tree.children):
		curr_id = curr_child.original_node.backend_node_id

		if curr_id not in prev_map:
			# Node was added - find what it comes after
			after_id = prev_children_ids[i - 1] if i > 0 and i - 1 < len(prev_children_ids) else 0
			# Only add the top-level node (serializer will include all descendants)
			added_nodes.append((after_id, curr_child))
		else:
			# Node exists - check if it changed
			prev_node = prev_map[curr_id]
			changes = _detect_node_changes(prev_node, curr_child)
			if changes:
				changed_nodes.append((curr_id, changes))

			# Recurse into children
			child_removed, child_added, child_changed = _find_tree_changes(prev_node, curr_child, curr_id)
			removed_ids.extend(child_removed)
			added_nodes.extend(child_added)
			changed_nodes.extend(child_changed)

	return removed_ids, added_nodes, changed_nodes


def _build_node_map(tree: SimplifiedNode) -> dict[int, SimplifiedNode]:
	"""Build a map of backend_node_id -> SimplifiedNode for quick lookup."""
	node_map = {tree.original_node.backend_node_id: tree}
	for child in tree.children:
		node_map.update(_build_node_map(child))
	return node_map


def _find_parent(tree: SimplifiedNode, target: SimplifiedNode) -> SimplifiedNode | None:
	"""Find the parent of a target node in the tree."""
	for child in tree.children:
		if child == target:
			return tree
		parent = _find_parent(child, target)
		if parent:
			return parent
	return None


def _detect_node_changes(prev_node: SimplifiedNode, curr_node: SimplifiedNode) -> dict[str, tuple]:
	"""Detect what changed on a node.

	Returns dict of {attribute_name: (old_value, new_value)} for changed attributes.
	"""
	changes = {}

	# Check node value (text content)
	prev_val = prev_node.original_node.node_value
	curr_val = curr_node.original_node.node_value
	if prev_val != curr_val:
		changes['text'] = (prev_val, curr_val)

	# Check important attributes (exclude verbose ones like class, href, src)
	prev_attrs = prev_node.original_node.attributes or {}
	curr_attrs = curr_node.original_node.attributes or {}

	# Only track concise, meaningful attributes (exclude class, href, src which can be very long)
	important_attrs = {'value', 'checked', 'selected', 'disabled', 'id', 'aria-checked', 'aria-selected', 'aria-expanded'}
	for attr in important_attrs:
		prev_attr_val = prev_attrs.get(attr)
		curr_attr_val = curr_attrs.get(attr)
		if prev_attr_val != curr_attr_val:
			changes[attr] = (prev_attr_val, curr_attr_val)

	return changes
