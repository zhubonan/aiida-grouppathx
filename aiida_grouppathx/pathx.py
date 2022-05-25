"""
Enhanced GroupPath tool
"""
import enum
from functools import wraps
from itertools import chain
from typing import Iterator, Optional, Union
import warnings

from treelib import Tree

from aiida.common.exceptions import NotExistent
import aiida.orm as orm
from aiida.orm import ProcessNode
from aiida.tools.groups.paths import (
    REGEX_ATTR,
    GroupAttr,
    GroupPath,
    InvalidPath,
    NoGroupsInPathError,
)

GROUP_ALIAS_KEY = "_group_alias"

__all__ = [
    "GroupPathX",
    "decorate_with_label",
    "decorate_group",
    "decorate_node",
    "decorate_with_exit_status",
    "decorate_with_group_names",
    "decorate_with_exit_status",
    "decorate_with_uuid_first_n",
    "decorate_with_uuid",
]


class GroupPathXType(enum.Enum):
    """Type of the path"""

    VIRTUAL = "virtual"
    GROUP = "group"
    NODE = "node"


class PathIsNodeError(Exception):
    """An exception raised when a path does not have an associated group."""

    def __init__(self, grouppath):
        msg = f"This path corresponds to a node: {grouppath.path}"
        super().__init__(msg)


class PathIsNotNodeError(Exception):
    """An exception raised when a path does not have an associated group."""

    def __init__(self, grouppath):
        msg = f"This path does correspond to a node: {grouppath.path}"
        super().__init__(msg)


class PathIsNotGroupError(Exception):
    """An exception raised when a path does not have an associated group."""

    def __init__(self, grouppath):
        msg = f"This path does correspond to a path: {grouppath.path}"
        super().__init__(msg)


class PathIsGroupError(Exception):
    """An exception raised when a path does not have an associated group."""

    def __init__(self, grouppath):
        msg = f"This path corresponds to a group: {grouppath.path}"
        super().__init__(msg)


class PathIsNotVirtualError(Exception):
    """An exception raised when a path does not have an associated group."""

    def __init__(self, grouppath):
        msg = f"This path corresponds a group or a node: {grouppath.path}"
        super().__init__(msg)


def requires_node(func):
    """Require the current path to be a Node"""

    @wraps(func)
    def _func(self, *args, **kwargs):
        if not self.is_node:
            raise PathIsNotNodeError(self)
        return func(self, *args, **kwargs)

    return _func


def requires_not_node(func):
    """Require the current path to be a Node"""

    @wraps(func)
    def _func(self, *args, **kwargs):
        if self.is_node:
            raise PathIsNodeError(self)
        return func(self, *args, **kwargs)

    return _func


def requires_group(func):
    """Require the current path to be a Node"""

    @wraps(func)
    def _func(self, *args, **kwargs):
        if not self.is_group:
            raise PathIsNotGroupError(self)
        return func(self, *args, **kwargs)

    return _func


class GroupPathX(GroupPath):
    """
    Enhanced version of the GroupPath
    """

    def __init__(
        self,
        path: str = "",
        cls: orm.groups.GroupMeta = orm.Group,
        warn_invalid_child: bool = True,
    ) -> None:
        """Instantiate the class.

        :param path: The initial path of the group.
        :param cls: The subclass of `Group` to operate on.
        :param warn_invalid_child: Issue a warning, when iterating children, if a child path is invalid.

        """
        super().__init__(path=path, cls=cls, warn_invalid_child=warn_invalid_child)
        self._extras_key = GROUP_ALIAS_KEY

    @property
    def not_ambigious(self):
        """
        Is the path ambiguous - e.g. it can be resolved into both a Group and a Node
        """
        if not self.is_virtual and self._get_node_query().count() > 0:
            return False
        return True

    def _get_node_query(self) -> Optional[orm.QueryBuilder]:
        """Get a query to find the node associated with this path if exists"""
        parent = self.parent
        if parent is None:
            return None
        if not parent.is_group:
            return None
        query = orm.QueryBuilder()
        query.append(parent.cls, subclassing=False, filters={"label": parent.path})
        query.append(
            orm.Node,
            with_group=parent.cls,
            filters={
                "extras." + self._extras_key + "." + parent.get_group().uuid: self.key
            },
        )
        return query

    def get_node(self) -> Optional[orm.Node]:
        """Get an associated node for this group Path if exists"""

        query = self._get_node_query()
        if query is None:
            return None
        try:
            node = query.one()[0]
        except NotExistent:
            return None
        return node

    @property
    def path_type(self):
        """Return a `GroupPathXType enum"""
        if self.is_virtual:
            return GroupPathXType.VIRTUAL
        if self.is_group:
            return GroupPathXType.GROUP
        if self.is_node:
            return GroupPathXType.NODE
        raise ValueError("Cannot determine the type of the path")

    @property
    def is_group(self) -> bool:
        """Return whether there is one or more concrete groups associated with this path."""
        return len(self.group_ids) > 0

    @property
    def is_virtual(self) -> bool:
        """Return whether there is one or more concrete groups associated with this path or a Node."""
        return len(self.group_ids) == 0 and not self.is_node

    @property
    def is_node(self) -> bool:
        """Check this there is an unique associated node for this path"""
        query = self._get_node_query()
        if query is None:
            return False
        if query.count() == 1:
            return True
        if query.count() > 1:
            raise ValueError(
                f"There are multiple nodes having the same alias: {[entry[0] for entry in query.all()]}"
            )
        return False

    @property
    def children(self) -> Iterator["GroupPath"]:
        """
        Iterate through all (direct) children of this path, including any nodes with alias inside the group.
        """

        # No children if the Path corresponds to a Node
        if self.is_node:
            return

        query = orm.QueryBuilder()
        filters = {}
        if self.path:
            filters["label"] = {"like": f"{self.path + self.delimiter}%"}
        query.append(self.cls, subclassing=False, filters=filters, project="label")

        # Query sub nodes with group_alias in the extras
        node_query = orm.QueryBuilder()
        node_query.append(self.cls, subclassing=False, filters={"label": self.path})
        node_query.append(
            orm.Node,
            with_group=self.cls,
            filters={"extras": {"has_key": self._extras_key}},
            project=["extras." + self._extras_key],
        )

        if query.count() == 0 and self.is_virtual:
            raise NoGroupsInPathError(self)

        def node_wrapper(items):
            for item in items:
                yield ("node", item)

        def group_wrapper(items):
            for item in items:
                yield ("group", item)

        yielded = []
        for (item_type, label) in chain(
            group_wrapper(query.iterall()), node_wrapper(node_query.iterall())
        ):
            label = label[0]
            # Group specific label
            if isinstance(label, dict):
                label = label.get(self.get_group().uuid)
                if label is None:
                    continue

            if item_type == "node":
                # This means that the path is associated with a node
                # Hence we composethe full path
                label = self.path + self.delimiter + label

            # Sanity check....
            path = label.split(self._delimiter)
            if len(path) <= len(self._path_list):
                continue

            # Get the fully qualified path to the next level
            path_string = self._delimiter.join(path[: len(self._path_list) + 1])
            if (
                path_string not in yielded
                and path[: len(self._path_list)] == self._path_list
            ):
                yielded.append(path_string)
                try:
                    yield GroupPathX(
                        path=path_string,
                        cls=self.cls,
                        warn_invalid_child=self._warn_invalid_child,
                    )
                except InvalidPath:
                    if self._warn_invalid_child:
                        warnings.warn(
                            f"invalid path encountered: {path_string}"
                        )  # pylint: disable=no-member

    def walk(self, return_virtual: bool = True) -> Iterator["GroupPathX"]:
        """Recursively iterate through all children of this path."""
        for child in self:
            if return_virtual or not child.is_virtual:
                yield child
            for sub_child in child.walk(return_virtual=return_virtual):
                if return_virtual or not sub_child.is_virtual:
                    yield sub_child

    def _build_tree(self, tree=None, parent=None, decorate=None):
        """Build a tree diagram of all children"""

        name = self.key
        if decorate is not None:
            suffix = []
            for dfunc in decorate:
                val = dfunc(self)
                if val is not None:
                    suffix.append(val)
            if suffix:
                name = name + " " + " | ".join(suffix)

        if tree is None:
            tree = Tree()
            tree.create_node(name, self.path)
        else:
            tree.create_node(name, self.path, parent=parent)
        for child in self:
            child._build_tree(  # pylint: disable=protected-access
                tree,
                parent=self.path,
                decorate=decorate,
            )
        return tree

    def show_tree(self, *decorate):
        """
        Show the tree of all children

        Path that are nodes are decorated with ``*``.
        """
        if not decorate:
            decorate = [decorate_node]

        tree = self._build_tree(decorate=decorate)
        tree.show()

    def __truediv__(self, path: str) -> "GroupPathX":
        """Return a child ``GroupPathX``, with a new path formed by appending ``path`` to the current path."""
        if not isinstance(path, str):
            raise TypeError(f"path is not a string: {path}")
        path = self._validate_path(path)
        child = GroupPathX(
            path=self.path + self.delimiter + path if self.path else path,
            cls=self.cls,
            warn_invalid_child=self._warn_invalid_child,
        )
        return child

    @property
    def parent(self) -> Optional["GroupPathX"]:
        """Return the parent path."""
        if self.path_list:
            return GroupPathX(
                self.delimiter.join(self.path_list[:-1]),
                cls=self.cls,
                warn_invalid_child=self._warn_invalid_child,
            )
        return None

    @requires_not_node
    def add_node(self, node: Union[orm.Node, "GroupAttr"], alias: str, force=False):
        """
        Add an node to the group with an alias.

        A group will be created if the path is virtual.
        """
        if not REGEX_ATTR.match(alias):
            warnings.warn(
                f"Alias {alias} is not valid Python identifier - you may consider using one for easier access."
            )
        if self.is_virtual:
            self.get_or_create_group()
        if isinstance(node, GroupAttr):
            node = node().get_node()

        # Check if the node to be added has an existing name for this group
        group = self.get_group()
        existing_name = get_alias(node, group)

        if existing_name is not None and alias != existing_name:
            if force is False:
                raise ValueError(
                    f"Cannot add {node} with alias: {alias}, because it already has one: {existing_name}."
                )

        # Check if this path is in use already
        target_path = self[alias]
        if not target_path.is_virtual:
            if target_path.is_group:
                raise PathIsGroupError(target_path)
            if not force:
                raise PathIsNotVirtualError(self[alias])
            # Unlink existing node
            warnings.warn(f"Unsetting exsiting node: {target_path.get_node()}'s alias")
            target_path.unlink()

        set_alias(node, group, alias)
        self.get_group().add_nodes(node)

    @requires_node
    def rename(self, alias: str):
        """Update the alias of this Node"""
        if not REGEX_ATTR.match(alias):
            warnings.warn(
                f"Alias {alias} is not valid Python identifier - you may consider using one for easier access."
            )

        if not self.is_node:
            raise PathIsGroupError(self)
        node = self.get_node()
        if not self.parent[alias].is_virtual:
            raise ValueError(f"Alias {alias} has been used already.")
        set_alias(node, self.parent.get_group(), alias)

    @requires_node
    def unlink(self, save_previous=True):
        """Update the alias of this Node"""
        node = self.get_node()
        delete_alias(node, self.parent.get_group(), save_previous=save_previous)

    def list_nodes(self):
        """List all nodes with alias in this group"""
        if not self.is_group:
            return []
        return [path.key for path in self.children if path.is_node]

    def list_nodes_without_alias(self):
        """List all nodes that do not have any alias in this group"""
        if not self.is_group:
            return []
        existing = [path.get_node().id for path in self.children if path.is_node]
        missing = []
        for node in self.get_group().nodes:
            if node.id not in existing:
                missing.append(node)
        return missing

    @property
    def browse_nodes(self):
        """Return a ``NodeAttr`` instance, for attribute access to child nodes."""
        return NodeAttr(self)


def set_alias(node, group, alias: str, suffix=""):
    """Set the alias field of a Node for a specific group"""
    extras = node.extras
    alias_dict = extras.get(GROUP_ALIAS_KEY + suffix, {})
    if not isinstance(alias_dict, dict):
        alias_dict = {}
    alias_dict[group.uuid] = alias
    node.set_extra(GROUP_ALIAS_KEY + suffix, alias_dict)
    return node


def delete_alias(node, group, save_previous=True):
    """Delete the alias field of a Node for a specific group"""
    extras = dict(node.extras)
    alias_dict = extras.get(GROUP_ALIAS_KEY, {})
    if not isinstance(alias_dict, dict):
        alias_dict = {}

    previous_alias = alias_dict.pop(group.uuid, None)
    node.set_extra(GROUP_ALIAS_KEY, alias_dict)
    # Save previously used alias
    if save_previous:
        set_alias(node, group, previous_alias, "_deleted")
    return node


def get_alias(node, group, suffix=""):
    """Get the alias field of a Node for a specific group"""
    extras = node.extras
    alias_dict = extras.get(GROUP_ALIAS_KEY + suffix, {})
    if not isinstance(alias_dict, dict):
        alias_dict = {}
    return alias_dict.get(group.uuid)


class NodeAttr(GroupAttr):
    """Like ``GroupAttr`` but only include nodes"""

    def __dir__(self):
        """Return a list of available attributes."""
        return [
            c.path_list[-1]
            for c in self._group_path.children
            if REGEX_ATTR.match(c.path_list[-1]) and c.is_node
        ]


def decorate_node(path) -> Optional[str]:
    """Decrate paths tha are nodes with ``*``"""
    if path.is_node:
        return "*"
    return None


def decorate_group(path) -> Optional[str]:
    """Decrate paths that are groups with ``*``"""
    if path.is_group:
        return "*"
    return None


def decorate_with_exit_status(path) -> Optional[str]:
    """Decrate paths that are nodes with process states"""

    if path.is_node:
        node = path.get_node()
        if isinstance(node, ProcessNode):
            if node.is_finished:
                return f"[{node.exit_status}]"
            return f"[{node.process_state.value}]"
    return None


def decorate_with_uuid_first_n(n_char=12):
    """
    Generator for UUID decoration

    Usage:

        >>> path.show_tree(decorate_with_uuid(12))  # To show the first 12 characters of the UUID
    """

    def func(path) -> Optional[str]:
        """Decrate paths that are nodes with process states"""
        if path.is_node:
            node = path.get_node()
            return f"{node.uuid[:n_char]}"
        return None

    return func


def decorate_with_uuid(path) -> Optional[str]:
    """Decrate the nodes with their UUIDs"""
    if path.is_node:
        node = path.get_node()
        return f"{node.uuid[:12]}"
    return None


def decorate_with_label(path) -> Optional[str]:
    """Decrate nodes with their labels"""
    if path.is_node:
        node = path.get_node()
        return f"{node.label}"
    return None


def decorate_with_group_names(path) -> Optional[str]:
    """Decrate nodes with the name of the group they belong to"""
    if path.is_node:
        node = path.get_node()
        query = orm.QueryBuilder().append(orm.Node, filters={"id": node.id})
        query.append(orm.Group, with_node=orm.Node, project=["label"])
        groups = [entry[0] for entry in query.all()]
        return ", ".join(groups)
    return None
