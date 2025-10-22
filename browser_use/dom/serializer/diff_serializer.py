"""DOM tree diff serializer for showing state changes."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
	from browser_use.dom.views import SimplifiedNode

from browser_use.dom.views import DEFAULT_INCLUDE_ATTRIBUTES


def compute_tree_diff(previous_tree: SimplifiedNode, current_tree: SimplifiedNode) -> str:
	"""Compute diff between two SimplifiedNode trees.

	Finds where subtrees diverge and serializes them using the original eval_representation format.

	Args:
		previous_tree: Previous SimplifiedNode tree
		current_tree: Current SimplifiedNode tree

	Returns:
		Diff showing removed/added subtrees in original serialization format
	"""
	from browser_use.dom.serializer.serializer import DOMTreeSerializer

	diff_sections: list[str] = []

	# Find divergence points
	removed_subtrees, added_subtrees = _find_divergent_subtrees(previous_tree, current_tree)

	# Format removed subtrees
	if removed_subtrees:
		diff_sections.append('## Removed Subtrees\n')
		for path, node in removed_subtrees:
			# Serialize the removed subtree using original serializer
			subtree_html = DOMTreeSerializer.serialize_tree(node, DEFAULT_INCLUDE_ATTRIBUTES)
			diff_sections.append(f'-- Location: {path}')
			diff_sections.append(subtree_html)
			diff_sections.append('')  # Blank line

	# Format added subtrees
	if added_subtrees:
		diff_sections.append('## Added Subtrees\n')
		for path, node in added_subtrees:
			# Serialize the added subtree using original serializer
			subtree_html = DOMTreeSerializer.serialize_tree(node, DEFAULT_INCLUDE_ATTRIBUTES)
			diff_sections.append(f'++ Location: {path}')
			diff_sections.append(subtree_html)
			diff_sections.append('')  # Blank line

	if not diff_sections:
		return 'No DOM changes detected'

	summary = f'# DOM Diff: {len(removed_subtrees)} removed, {len(added_subtrees)} added subtrees\n'
	return summary + '\n'.join(diff_sections)


def _find_divergent_subtrees(
	previous_tree: SimplifiedNode, current_tree: SimplifiedNode, path: str = 'root'
) -> tuple[list[tuple[str, SimplifiedNode]], list[tuple[str, SimplifiedNode]]]:
	"""Find where two trees diverge and return the divergent subtrees.

	Args:
		previous_tree: Previous SimplifiedNode tree
		current_tree: Current SimplifiedNode tree
		path: Current path in the tree (for location tracking)

	Returns:
		Tuple of (removed_subtrees, added_subtrees) where each is a list of (path, node) tuples
	"""
	removed: list[tuple[str, SimplifiedNode]] = []
	added: list[tuple[str, SimplifiedNode]] = []

	# Check if nodes are structurally identical
	if _nodes_are_equivalent(previous_tree, current_tree):
		# Nodes match - recurse into children
		# Match children by position and tag
		prev_children = previous_tree.children
		curr_children = current_tree.children

		max_children = max(len(prev_children), len(curr_children))
		for i in range(max_children):
			prev_child = prev_children[i] if i < len(prev_children) else None
			curr_child = curr_children[i] if i < len(curr_children) else None

			if prev_child and curr_child:
				# Both exist - recurse
				child_path = _build_path(path, curr_child)
				child_removed, child_added = _find_divergent_subtrees(prev_child, curr_child, child_path)
				removed.extend(child_removed)
				added.extend(child_added)
			elif prev_child and not curr_child:
				# Child was removed
				child_path = _build_path(path, prev_child)
				removed.append((child_path, prev_child))
			elif curr_child and not prev_child:
				# Child was added
				child_path = _build_path(path, curr_child)
				added.append((child_path, curr_child))
	else:
		# Nodes differ - entire subtree changed
		# Mark current node as removed/added
		removed.append((path, previous_tree))
		added.append((path, current_tree))

	return removed, added


def _nodes_are_equivalent(node1: SimplifiedNode, node2: SimplifiedNode) -> bool:
	"""Check if two nodes are equivalent (same tag, attributes, text).

	Args:
		node1: First SimplifiedNode
		node2: Second SimplifiedNode

	Returns:
		True if nodes are equivalent
	"""
	# Check tag name
	if node1.original_node.tag_name != node2.original_node.tag_name:
		return False

	# Check node value (text content)
	if node1.original_node.node_value != node2.original_node.node_value:
		return False

	# Check important attributes
	attrs1 = node1.original_node.attributes or {}
	attrs2 = node2.original_node.attributes or {}

	# Compare important attributes that affect rendering/behavior
	important_attrs = {'id', 'class', 'value', 'checked', 'selected', 'disabled', 'href', 'src', 'type'}
	for attr in important_attrs:
		if attrs1.get(attr) != attrs2.get(attr):
			return False

	return True


def _build_path(parent_path: str, node: SimplifiedNode) -> str:
	"""Build path string for a node.

	Args:
		parent_path: Parent path
		node: SimplifiedNode

	Returns:
		Path string like "root > body > div#id"
	"""
	tag = node.original_node.tag_name or 'node'
	attrs = node.original_node.attributes or {}

	# Add ID or class to make path more specific
	if 'id' in attrs:
		tag = f'{tag}#{attrs["id"]}'
	elif 'class' in attrs:
		classes = attrs['class'].split()[:1]  # First class only
		if classes:
			tag = f'{tag}.{classes[0]}'

	return f'{parent_path} > {tag}'
