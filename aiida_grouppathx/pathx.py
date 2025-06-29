"""
Enhanced GroupPath tool
"""

import enum
import warnings
from contextlib import contextmanager
from functools import wraps
from itertools import chain
from typing import Iterator, Optional, Union

from aiida import orm
from aiida.common.exceptions import NotExistent
from aiida.orm import ProcessNode
from aiida.tools.groups.paths import (
    REGEX_ATTR,
    GroupAttr,
    GroupPath,
    InvalidPath,
    NoGroupsInPathError,
)
from treelib import Tree

GROUP_ALIAS_KEY = '_group_alias'

__all__ = [
    'GroupPathX',
    'decorate_with_label',
    'decorate_group',
    'decorate_node',
    'decorate_with_exit_status',
    'decorate_with_group_names',
    'decorate_with_exit_status',
    'decorate_with_uuid_first_n',
    'decorate_with_uuid',
    'decorate_with_pk',
]


class GroupPathXType(enum.Enum):
    """Type of the path"""

    VIRTUAL = 'virtual'
    GROUP = 'group'
    NODE = 'node'


class PathIsNodeError(Exception):
    """An exception raised when a path does not have an associated group."""

    def __init__(self, grouppath):
        msg = f'This path corresponds to a node: {grouppath.path}'
        super().__init__(msg)


class PathIsNotNodeError(Exception):
    """An exception raised when a path does not have an associated group."""

    def __init__(self, grouppath):
        msg = f'This path does correspond to a node: {grouppath.path}'
        super().__init__(msg)


class PathIsNotGroupError(Exception):
    """An exception raised when a path does not have an associated group."""

    def __init__(self, grouppath):
        msg = f'This path does correspond to a path: {grouppath.path}'
        super().__init__(msg)


class PathIsGroupError(Exception):
    """An exception raised when a path does not have an associated group."""

    def __init__(self, grouppath):
        msg = f'This path corresponds to a group: {grouppath.path}'
        super().__init__(msg)


class PathIsNotVirtualError(Exception):
    """An exception raised when a path does not have an associated group."""

    def __init__(self, grouppath):
        msg = f'This path corresponds a group or a node: {grouppath.path}'
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
        path: str = '',
        cls=orm.Group,
        warn_invalid_child: bool = True,
        node_cache=None,
        group_cache=None,
        verbose=False,
    ) -> None:
        """
        Instantiate a GroupPathX object.
        A GroupPathX object may represent group as well as a node, which resembles a file system path.

        The underlying group/node can be passed in `node_cache` or `group_cache` to avoid querying the database.
        This is useful when the underlying group/node are not expected to change during the lifetime of this object.
        To enable caching, use the`use_cache` context manager when iterating a `GroupPathX` object.

        :param path: The initial path of the group.
        :param cls: The subclass of `Group` to operate on.
        :param warn_invalid_child: Issue a warning, when iterating children, if a child path is invalid.
        :param node_cache: A cache of the node associated with this path.
        :param group_cache: A cache of the group associated with this path.
        :param verbose: Print debug messages.
        """

        super().__init__(path=path, cls=cls, warn_invalid_child=warn_invalid_child)
        self._extras_key = GROUP_ALIAS_KEY
        self._uuid = None
        self.node_cache = node_cache
        self.group_cache = group_cache
        self.only_nodes_in_iter = False
        self.add_cache_in_iter = False
        self._verbose = verbose

    def _clear_cache(self):
        self.node_cache = None
        self.group_cache = None

    def get_group(self):
        if self.group_cache is not None:
            return self.group_cache
        return super().get_group()

    @property
    def group(self):
        """Return the group associated with this path if exists"""
        return self.get_group()

    @property
    def uuid(self) -> Union[str, None]:
        """Return the uuid of the group or node associated with this path if exists"""
        gp = self.get_group()
        if gp:
            return gp.uuid
        node = self.node
        if node:
            return node.uuid
        return None

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
        query.append(parent.cls, subclassing=False, filters={'label': parent.path})
        query.append(
            orm.Node,
            with_group=parent.cls,
            filters={'extras.' + self._extras_key + '.' + parent.get_group().uuid: self.key},
        )
        return query

    def get_node(self) -> Optional[orm.Node]:
        """Get an associated node for this group Path if exists"""
        warnings.warn('GroupPathX.get_node is deprecated use .node property instead', DeprecationWarning)
        return self.node

    @property
    def node(self) -> Optional[orm.Node]:
        if self.node_cache is not None:
            return self.node_cache
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
        raise ValueError('Cannot determine the type of the path')

    @property
    def is_group(self) -> bool:
        """Return whether there is one or more concrete groups associated with this path."""
        if self.group_cache is not None:
            return True
        return len(self.group_ids) > 0

    @property
    def is_virtual(self) -> bool:
        """Return whether there is one or more concrete groups associated with this path or a Node."""
        return len(self.group_ids) == 0 and not self.is_node

    @property
    def is_node(self) -> bool:
        """Check this there is an unique associated node for this path"""
        if self.node_cache is not None:
            return True
        query = self._get_node_query()
        if query is None:
            return False
        if query.count() == 1:
            return True
        if query.count() > 1:
            raise ValueError(f'There are multiple nodes having the same alias: {[entry[0] for entry in query.all()]}')
        return False

    @property
    def children(self) -> Iterator['GroupPathX']:
        """
        Iterate through all (direct) children of this path, including any nodes with alias inside the group.
        """
        # No children if the Path corresponds to a Node
        return self._get_children()

    @property
    def fast_iter(self) -> Iterator['GroupPathX']:
        """
        Iterate through all (direct) children of this path, including any nodes with alias inside the group.
        """
        # No children if the Path corresponds to a Node
        with use_cache(self):
            return list(self._get_children())

    def _get_children(self, add_cache=None, only_nodes=None) -> Iterator['GroupPathX']:
        """
        Iterate through all (direct) children of this path, including any nodes with alias inside the group.
        """
        add_cache = self.add_cache_in_iter if add_cache is None else add_cache
        only_nodes = self.only_nodes_in_iter if only_nodes is None else only_nodes

        # No children if the Path corresponds to a Node
        if self.is_node:
            return

        query = orm.QueryBuilder()
        filters = {}
        if self.path:
            filters['label'] = {'like': f'{self.path + self.delimiter}%'}
        query.append(self.cls, subclassing=False, filters=filters, project='label' if not add_cache else ['label', '*'])

        # Query sub nodes with group_alias in the extras
        node_query = orm.QueryBuilder()
        node_query.append(self.cls, subclassing=False, filters={'label': self.path})
        node_query.append(
            orm.Node,
            with_group=self.cls,
            # Do not use filter in order to support SQLite backend which does support has_key as of aiida-core 2.6.3
            # filters={'extras': {'has_key': self._extras_key}},
            project=['extras.' + self._extras_key] if not add_cache else ['extras.' + self._extras_key, '*'],
        )

        if query.count() == 0 and self.is_virtual:
            raise NoGroupsInPathError(self)

        def node_wrapper(items):
            for item in items:
                if item[0] is not None:
                    # Only yield is self._extras_key is set
                    yield ('node', item)

        def group_wrapper(items):
            for item in items:
                if item[0] is not None:
                    # Only yield is self._extras_key is set
                    yield ('group', item)

        yielded = []
        group_uuid = self.uuid

        # Are we in node-only mode?
        if only_nodes:
            iter_obj = node_wrapper(node_query.iterall())
        else:
            iter_obj = chain(group_wrapper(query.iterall()), node_wrapper(node_query.iterall()))

        for item_type, projected_items in iter_obj:
            label = projected_items[0]
            # Group specific label
            if isinstance(label, dict):
                label = label.get(group_uuid)
                if label is None:
                    continue

            if item_type == 'node':
                # This means that the path is associated with a node
                # Hence we compose the full path
                label = self.path + self.delimiter + label

            # Sanity check....
            path = label.split(self._delimiter)
            if len(path) <= len(self._path_list):
                continue

            # Get the fully qualified path to the next level
            path_string = self._delimiter.join(path[: len(self._path_list) + 1])
            if path_string not in yielded and path[: len(self._path_list)] == self._path_list:
                yielded.append(path_string)
                try:
                    yield GroupPathX(
                        path=path_string,
                        cls=self.cls,
                        warn_invalid_child=self._warn_invalid_child,
                        node_cache=projected_items[1] if item_type == 'node' and add_cache else None,
                        group_cache=projected_items[1] if item_type == 'group' and add_cache else None,
                    )
                except InvalidPath:
                    if self._warn_invalid_child:
                        warnings.warn(f'invalid path encountered: {path_string}')  # pylint: disable=no-member

    def __iter__(self) -> Iterator['GroupPathX']:
        """Iterate through all (direct) children of this path.
        A list is build immediately to avoid any cursor invalidation errors due to the database
        state being changed during the iteration...

        For memory efficient iterations, use the ``children`` property instead.
        """
        return iter(list(self.children))

    def walk(self, return_virtual: bool = True) -> Iterator['GroupPathX']:
        """Recursively iterate through all children of this path."""
        for child in self.children:
            if return_virtual or not child.is_virtual:
                yield child
            for sub_child in child.walk(return_virtual=return_virtual):
                if return_virtual or not sub_child.is_virtual:
                    yield sub_child

    def _build_tree(self, tree: Tree = None, parent=None, decorate=None):
        """Build a tree diagram of all children"""

        name = self.key
        if decorate is not None:
            suffix = []
            for dfunc in decorate:
                val = dfunc(self)
                if val is not None:
                    suffix.append(val)
            if suffix:
                name = name + ' ' + ' | '.join(suffix)

        if tree is None:
            tree = Tree()
            tree.create_node(name, self.path)
        else:
            tree.create_node(name, self.path, parent=parent)
        # Enable cache for children since we are just building the tree
        with use_cache(self):
            for child in self.children:
                child._build_tree(  # pylint: disable=protected-access
                    tree,
                    parent=self.path,
                    decorate=decorate,
                )
        return tree

    def show_tree(self, *decorate, decorate_by=None, **kwargs):
        """
        Show the tree of all children

        Path that are nodes are decorated with ``*``.
        Functions for decorating the leafs can be passed as positional arguments.
        Keyword arguments will be passed to the ``tree.show`` method.

        :param decorate: functions for decorating the leafs
        :param decorate_by: A list of pre-defined decorators, valid options can be found in the DECORATE_KEYS constant.
        :param kwargs: keyword arguments for the ``tree.show`` method
        """
        if not decorate:
            decorate = [decorate_node]
        if decorate_by:
            decorate = [DECORATE_KEYS[value] for value in decorate_by]

        tree = self._build_tree(decorate=decorate)
        return tree.show(**kwargs)

    def __truediv__(self, path: str) -> 'GroupPathX':
        """Return a child ``GroupPathX``, with a new path formed by appending ``path`` to the current path."""
        if not isinstance(path, str):
            raise TypeError(f'path is not a string: {path}')
        path = self._validate_path(path)
        child = GroupPathX(
            path=self.path + self.delimiter + path if self.path else path,
            cls=self.cls,
            warn_invalid_child=self._warn_invalid_child,
        )
        return child

    @property
    def parent(self) -> Optional['GroupPathX']:
        """Return the parent path."""
        if self.path_list:
            return GroupPathX(
                self.delimiter.join(self.path_list[:-1]),
                cls=self.cls,
                warn_invalid_child=self._warn_invalid_child,
            )
        return None

    @requires_not_node
    def add_node(self, node: Union[orm.Node, 'GroupAttr'], alias: str, force=False):
        """
        Add an node to the group with an alias.

        A group will be created if the path is virtual.
        """
        if not REGEX_ATTR.match(alias) and self._verbose:
            warnings.warn(
                f'Alias {alias} is not valid Python identifier'
                'you may consider using one for easier access with .browse access'
            )
        if self.is_virtual:
            self.get_or_create_group()
        if isinstance(node, GroupAttr):
            node = node().node

        # Check if the node to be added has an existing name for this group
        group = self.get_group()
        existing_name = get_alias(node, group)

        if existing_name is not None and alias != existing_name:
            if force is False:
                raise ValueError(f'Cannot add {node} with alias: {alias}, because it already has one: {existing_name}.')
            else:
                warnings.warn(f'Overwriting alias: {existing_name} with: {alias} for this group')

        # Check if this path is in use already
        target_path = self[alias]
        if not target_path.is_virtual:
            if target_path.is_group:
                raise PathIsGroupError(target_path)
            if not force:
                raise PathIsNotVirtualError(self[alias])
            # Unlink existing node
            warnings.warn(f"Unsetting existing node: {target_path.node}'s alias")
            target_path.unlink()

        set_alias(node, group, alias)
        self.get_group().add_nodes(node)

    def __setitem__(self, alias, node):
        """Set a node to the group with an alias."""
        self.add_node(node, alias, force=True)

    def add_nodes(self, nodes: dict, force=False):
        """
        Add multiple node to the group with an alias.

        A group will be created if the path is virtual.
        """
        if self.is_virtual:
            self.get_or_create_group()

        # Check if the node to be added has an existing name for this group
        group = self.get_group()
        aliases = list(nodes.keys())
        existing_names = [path.key for path in self.fast_iter]
        for alias in aliases:
            if alias in existing_names:
                if force is False:
                    raise ValueError(f'Cannot add {nodes[alias]} with alias: {alias}, because it already has one.')

        # Now finished checking set the alias and add the nodes to the group
        for alias in aliases:
            if alias in existing_names:
                self[alias].unlink()
            set_alias(nodes[alias], group, alias)
        # Add the nodes in bulk
        self.get_group().add_nodes(nodes.values())

    @requires_node
    def rename(self, alias: str):
        """Update the alias of this Node"""
        if not REGEX_ATTR.match(alias):
            warnings.warn(
                f'Alias {alias} is not valid Python identifier - you may consider using one for easier access.'
            )

        if not self.is_node:
            raise PathIsGroupError(self)
        node = self.node
        if not self.parent[alias].is_virtual:
            raise ValueError(f'Alias {alias} has been used already.')
        set_alias(node, self.parent.get_group(), alias)

    @requires_node
    def unlink(self, save_previous=True):
        """Update the alias of this Node"""
        node = self.node
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
        existing = [path.node.pk for path in self.children if path.is_node]
        missing = []
        for node in self.get_group().nodes:
            if node.pk not in existing:
                missing.append(node)
        return missing

    @property
    def browse_nodes(self):
        """Return a ``NodeAttr`` instance, for attribute access to child nodes."""
        return NodeAttr(self)


def set_alias(node, group, alias: str, suffix=''):
    """Set the alias field of a Node for a specific group"""
    alias_dict = node.base.extras.get(GROUP_ALIAS_KEY + suffix, {})
    if not isinstance(alias_dict, dict):
        alias_dict = {}
    alias_dict[group.uuid] = alias
    node.base.extras.set(GROUP_ALIAS_KEY + suffix, alias_dict)
    return node


def delete_alias(node, group, save_previous=True):
    """Delete the alias field of a Node for a specific group"""
    alias_dict = node.base.extras.get(GROUP_ALIAS_KEY, {})
    if not isinstance(alias_dict, dict):
        alias_dict = {}

    previous_alias = alias_dict.pop(group.uuid, None)
    node.base.extras.set(GROUP_ALIAS_KEY, alias_dict)
    # Save previously used alias
    if save_previous:
        set_alias(node, group, previous_alias, '_deleted')
    return node


def get_alias(node, group, suffix=''):
    """Get the alias field of a Node for a specific group"""
    alias_dict = node.base.extras.get(GROUP_ALIAS_KEY + suffix, {})
    if not isinstance(alias_dict, dict):
        alias_dict = {}
    return alias_dict.get(group.uuid)


class NodeAttr(GroupAttr):
    """Like ``GroupAttr`` but only include nodes"""

    def __dir__(self):
        """Return a list of available attributes."""
        return [c.path_list[-1] for c in self._group_path.children if REGEX_ATTR.match(c.path_list[-1]) and c.is_node]


def decorate_node(path) -> Optional[str]:
    """Decrate paths tha are nodes with ``*``"""
    if path.is_node:
        return '*'
    return None


def decorate_group(path) -> Optional[str]:
    """Decrate paths that are groups with ``*``"""
    if path.is_group:
        return '*'
    return None


def decorate_with_exit_status(path) -> Optional[str]:
    """Decrate paths that are nodes with process states"""

    if path.is_node:
        node = path.node
        if isinstance(node, ProcessNode):
            if node.is_finished:
                return f'[{node.exit_status}]'
            return f'[{node.process_state.value}]'
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
            node = path.node
            return f'{node.uuid[:n_char]}'
        return None

    return func


def none_unless_node(func):
    """Decorator - return None if path is not a node"""

    @wraps(func)
    def wrapper(path):
        if not path.is_node:
            return None
        return func(path)

    return wrapper


def none_if_virtual(func):
    """Decorator - return None if path is not a node"""

    @wraps(func)
    def wrapper(path):
        if not path.is_virtual:
            return None
        return func(path)

    return wrapper


def none_unless_group(func):
    """Decorator - return None if path is not a node"""

    @wraps(func)
    def wrapper(path):
        if not path.is_group:
            return None
        return func(path)

    return wrapper


def decorate_with_uuid(path) -> Optional[str]:
    """Decrate the nodes with their UUIDs"""
    if path.is_node:
        return f'{path.node.uuid[:12]}'
    if path.is_group:
        return f'{path.group.uuid[:12]}'
    return None


def decorate_with_pk(path) -> Optional[str]:
    """Decrate the nodes with their UUIDs"""
    if path.is_node:
        return f'{path.node.pk}'
    if path.is_group:
        return f'{path.group.pk}'
    return None


def decorate_with_label(path) -> Optional[str]:
    """Decrate nodes with their labels"""
    if path.is_node:
        return f'{path.node.label}'
    if path.is_group:
        return f'{path.group.label}'
    return None


@none_unless_node
def decorate_with_group_names(path) -> Optional[str]:
    """Decorate nodes with the name of the group they belong to"""
    node = path.node
    query = orm.QueryBuilder().append(orm.Node, filters={'id': node.id})
    query.append(orm.Group, with_node=orm.Node, project=['label'])
    groups = [entry[0] for entry in query.all()]
    return ', '.join(groups)


@contextmanager
def use_cache(gp: GroupPathX):
    """Context manager to temporarily enable caching when iterating a GroupPath object"""
    old = gp.add_cache_in_iter
    gp.add_cache_in_iter = True
    yield gp
    gp.add_cache_in_iter = old


@contextmanager
def no_cache(gp: GroupPathX):
    """Context manager to temporarily enable caching when iterating a GroupPath object"""
    old = gp.add_cache_in_iter
    gp.add_cache_in_iter = False
    yield gp
    gp.add_cache_in_iter = old


@contextmanager
def only_nodes(gp: GroupPathX):
    """Context manager to temporarily limit the iteration to nodes only when iterating a GroupPath object"""
    old = gp.only_nodes_in_iter
    gp.only_nodes_in_iter = True
    yield gp
    gp.only_nodes_in_iter = old


DECORATE_KEYS = {
    'label': decorate_with_label,
    'pk': decorate_with_pk,
    'group': decorate_group,
    'node': decorate_node,
    'group_name': decorate_with_group_names,
    'exit_status': decorate_with_exit_status,
    'uuid': decorate_with_uuid,
    'uuid_first_12': decorate_with_uuid_first_n(12),
}
