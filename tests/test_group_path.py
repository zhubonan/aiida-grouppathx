# pylint: disable=redefined-outer-name,unused-argument
"""Tests for GroupPathX"""

import pytest
from aiida import orm
from aiida.tools.groups.paths import (
    GroupAttr,
    GroupNotFoundError,
    InvalidPath,
    NoGroupsInPathError,
)
from click.testing import CliRunner

from aiida_grouppathx import GroupPathX, decorate_node
from aiida_grouppathx.cli import grouppathx_cli
from aiida_grouppathx.pathx import PathIsNotNodeError

# pylint:disable=protected-access


@pytest.fixture
def setup_groups(aiida_profile_clean):
    """Setup some groups for testing."""
    for label in ['a', 'a/b', 'a/c/d', 'a/c/e/g', 'a/f']:
        group, _ = orm.Group.collection.get_or_create(label)
        group.description = f'A description of {label}'
    yield


@pytest.mark.parametrize('path', ('/a', 'a/', '/a/', 'a//b'))
def test_invalid_paths(setup_groups, path):
    """Invalid paths should raise an ``InvalidPath`` exception."""
    with pytest.raises(InvalidPath):
        GroupPathX(path=path)


def test_root_path(setup_groups):
    """Test the root path properties"""
    group_path = GroupPathX()
    assert group_path.path == ''
    assert group_path.delimiter == '/'
    assert group_path.parent is None
    assert group_path.is_virtual
    assert group_path.group is None


def test_path_concatenation(setup_groups):
    """Test methods to build a new path."""
    group_path = GroupPathX()
    assert (group_path / 'a').path == 'a'
    assert (group_path / 'a' / 'b').path == 'a/b'
    assert (group_path / 'a/b').path == 'a/b'
    assert group_path['a/b'].path == 'a/b'
    assert GroupPathX('a/b/c') == GroupPathX('a/b') / 'c'


def test_path_existence(setup_groups):
    """Test existence of child "folders"."""
    group_path = GroupPathX()
    assert 'a' in group_path
    assert 'x' not in group_path


def test_group_retrieval(setup_groups):
    """Test retrieval of the actual group from a path.

    The ``group`` attribute will return None
    if no group is associated with the path
    """
    group_path = GroupPathX()
    assert group_path['x'].is_virtual
    assert not group_path['a'].is_virtual
    assert group_path.group is None
    assert isinstance(group_path['a'].group, orm.Group)


def test_group_creation(setup_groups):
    """Test creation of new groups."""
    group_path = GroupPathX()
    group, created = group_path['a'].get_or_create_group()
    assert isinstance(group, orm.Group)
    assert created is False
    group, created = group_path['x'].get_or_create_group()
    assert isinstance(group, orm.Group)
    assert created is True


def test_group_deletion(setup_groups):
    """Test deletion of existing groups."""
    group_path = GroupPathX()
    assert not group_path['a'].is_virtual
    group_path['a'].delete_group()
    assert group_path['a'].is_virtual
    with pytest.raises(GroupNotFoundError):
        group_path['a'].delete_group()


def test_path_iteration(setup_groups):
    """Test iteration of groups."""
    group_path = GroupPathX()
    assert len(group_path) == 1
    assert [(c.path, c.is_virtual) for c in group_path.children] == [('a', False)]
    child = next(group_path.children)
    assert child.parent == group_path
    assert len(child) == 3
    assert [(c.path, c.is_virtual) for c in sorted(child)] == [
        ('a/b', False),
        ('a/c', True),
        ('a/f', False),
    ]


def test_path_with_no_groups(setup_groups):
    """Test ``NoGroupsInPathError`` is raised if the path contains descendant groups."""
    group_path = GroupPathX()
    with pytest.raises(NoGroupsInPathError):
        list(group_path['x'])


def test_walk(setup_groups):
    """Test the ``GroupPathX.walk()`` function."""
    group_path = GroupPathX()
    assert [c.path for c in sorted(group_path.walk())] == [
        'a',
        'a/b',
        'a/c',
        'a/c/d',
        'a/c/e',
        'a/c/e/g',
        'a/f',
    ]


@pytest.mark.filterwarnings('ignore::UserWarning')
def test_walk_with_invalid_path(aiida_profile_clean):
    """Test the ``GroupPathX.walk`` method with invalid paths."""
    for label in ['a', 'a/b', 'a/c/d', 'a/c/e/g', 'a/f', 'bad//group', 'bad/other']:
        orm.Group.collection.get_or_create(label)
    group_path = GroupPathX()
    expected = [
        'a',
        'a/b',
        'a/c',
        'a/c/d',
        'a/c/e',
        'a/c/e/g',
        'a/f',
        'bad',
        'bad/other',
    ]
    assert [c.path for c in sorted(group_path.walk())] == expected


def test_walk_nodes(aiida_profile_clean):
    """Test the ``GroupPathX.walk_nodes()`` function."""
    group, _ = orm.Group.collection.get_or_create('a')
    node = orm.Data()
    node.base.attributes.set_many({'i': 1, 'j': 2})
    node.store()
    group.add_nodes(node)
    group_path = GroupPathX()
    assert [(r.group_path.path, r.node.base.attributes.all) for r in group_path.walk_nodes()] == [
        ('a', {'i': 1, 'j': 2})
    ]


def test_cls(aiida_profile_clean):
    """Test that only instances of `cls` or its subclasses are matched by ``GroupPathX``."""
    for label in ['a', 'a/b', 'a/c/d', 'a/c/e/g']:
        orm.Group.collection.get_or_create(label)
    for label in ['a/c/e', 'a/f']:
        orm.UpfFamily.collection.get_or_create(label)
    group_path = GroupPathX()
    assert sorted(c.path for c in group_path.walk()) == [
        'a',
        'a/b',
        'a/c',
        'a/c/d',
        'a/c/e',
        'a/c/e/g',
    ]
    group_path = GroupPathX(cls=orm.UpfFamily)
    assert sorted(c.path for c in group_path.walk()) == ['a', 'a/c', 'a/c/e', 'a/f']
    assert GroupPathX('a/b/c') != GroupPathX('a/b/c', cls=orm.UpfFamily)


def test_attr(aiida_profile_clean):
    """Test ``GroupAttr``."""
    for label in [
        'a',
        'a/b',
        'a/c/d',
        'a/c/e/g',
        'a/f',
        'bad space',
        'bad@char',
        '_badstart',
    ]:
        orm.Group.collection.get_or_create(label)
    group_path = GroupPathX()
    assert isinstance(group_path.browse.a.c.d, GroupAttr)
    assert isinstance(group_path.browse.a.c.d(), GroupPathX)
    assert group_path.browse.a.c.d().path == 'a/c/d'
    assert not set(dir(group_path.browse)).intersection(['bad space', 'bad@char', '_badstart'])
    with pytest.raises(AttributeError):
        group_path.browse.a.c.x  # pylint: disable=pointless-statement


def test_cls_label_clashes(aiida_profile_clean):
    """Test behaviour when multiple group classes have the same label."""
    group_01, _ = orm.Group.collection.get_or_create('a')
    node_01 = orm.Data().store()
    group_01.add_nodes(node_01)

    group_02, _ = orm.UpfFamily.collection.get_or_create('a')
    node_02 = orm.Data().store()
    group_02.add_nodes(node_02)

    # Requests for non-existing groups should return `None`
    assert GroupPathX('b').group is None

    assert GroupPathX('a').group_ids == [group_01.pk]
    assert GroupPathX('a').group.pk == group_01.pk
    expected = [('a', node_01.pk)]
    assert [(r.group_path.path, r.node.pk) for r in GroupPathX('a').walk_nodes()] == expected

    assert GroupPathX('a', cls=orm.UpfFamily).group_ids == [group_02.pk]
    assert GroupPathX('a', cls=orm.UpfFamily).group.pk == group_02.pk
    expected = [('a', node_02.pk)]
    assert [(r.group_path.path, r.node.pk) for r in GroupPathX('a', cls=orm.UpfFamily).walk_nodes()] == expected


def test_store_nodes(aiida_profile_clean):
    """
    Test storing nodes under the group
    """
    group = GroupPathX('mygroup')
    subgroup = group['mysubgroup']
    group.get_or_create_group()
    subgroup.get_or_create_group()
    assert not subgroup.is_virtual
    assert subgroup.is_group

    # Add node under the group
    node1 = orm.Int(1).store()
    group['int1'] = node1
    assert group['int1'].node

    # Change the name of the node
    group['int2'] = node1
    assert group['int2'].node
    assert group['int2'].is_node
    assert group['int1'].node is None
    assert node1.base.extras.get(group._extras_key) == {group.group.uuid: 'int2'}

    # Delete a node
    subgroup.add_node(node1, 'int1')
    group['int2'].unlink()
    assert group['int2'].is_virtual

    assert len(list(subgroup.children)) == 1
    assert len(list(group.children)) == 1

    # Should walk both the subgroup and the extra node
    assert len(list(group.walk())) == 2

    subgroup['int1'].rename('int2')
    assert subgroup['int2'].is_node

    with pytest.raises(PathIsNotNodeError):
        subgroup.rename('X')

    with pytest.raises(PathIsNotNodeError):
        subgroup.unlink()

    assert len(subgroup.list_nodes()) == 1
    assert len(group.list_nodes()) == 0
    assert len(subgroup['int2'].list_nodes()) == 0

    subgroup.group.add_nodes(orm.Int(2).store())
    assert len(subgroup.list_nodes_without_alias()) == 1

    # Check browse works
    assert group.browse.mysubgroup.int2().is_node


def test_build_tree(aiida_profile_clean):
    """Test printing a tree diagram of the paths"""

    group = GroupPathX('mygroup')
    subgroup = group['mysubgroup']
    group.get_or_create_group()
    subgroup.get_or_create_group()
    node1 = orm.Int(1).store()
    node1.label = 'X'
    node2 = orm.Int(1).store()

    group['node1'] = node1
    subgroup['node2'] = node2
    tree = group._build_tree(decorate=[decorate_node])
    treestring = tree.show(stdout=False)
    assert 'node1 *' in treestring
    assert 'mysubgroup' in treestring

    def mydecorate(path):
        if path.is_node:
            return '| label: ' + path.node.label
        return None

    tree = group._build_tree(decorate=[mydecorate])
    treestring = tree.show(stdout=False)
    assert 'node1 | label: X' in treestring

    def mydecorate2(path):
        if path.is_node:
            return 'uuid: ' + path.node.uuid
        return None

    tree = group._build_tree(decorate=[mydecorate, mydecorate2])
    treestring = tree.show(stdout=False)
    assert 'node1 | label: X | uuid: ' in treestring

    group.show_tree(decorate_by=['uuid', 'exit_status'])


def test_cli(setup_groups):
    """Test the CLI system"""

    node = orm.Dict({}).store()
    GroupPathX('a').add_node(node, 'Node1')

    runner = CliRunner()
    output = runner.invoke(grouppathx_cli, ['show-tree', 'a'])
    assert output.exit_code == 0
    assert 'Node1' in output.stdout

    output = runner.invoke(grouppathx_cli, ['show', 'a'])
    assert output.exit_code == 0
    assert 'Node1' in output.stdout

    # Test the add-node sub command
    node2 = orm.Dict({}).store()
    output = runner.invoke(grouppathx_cli, ['add-node', 'a', 'Node2', node2.uuid])
    assert output.exit_code == 0
    assert node2 in GroupPathX('a').group.nodes
    output = runner.invoke(grouppathx_cli, ['show', 'a'])
    assert output.exit_code == 0
    assert 'Node2' in output.stdout

    # Test unlink
    output = runner.invoke(grouppathx_cli, ['unlink', 'a/Node2'])
    # Unlink is only a soft delete
    assert node2 in GroupPathX('a').group.nodes
    paths = [x.key for x in GroupPathX('a')]
    assert 'Node2' not in paths

    output = runner.invoke(grouppathx_cli, ['show', 'a'])
    assert output.exit_code == 0
    assert 'Node2' not in output.stdout

    output = runner.invoke(grouppathx_cli, ['show', 'a', '--include-deleted'])
    assert output.exit_code == 0
    assert 'Node2' in output.stdout

    # Show Alias of a node
    output = runner.invoke(grouppathx_cli, ['alias', node.uuid])
    assert output.exit_code == 0
    assert 'a/Node1' in output.stdout
    assert 'a/Node2' not in output.stdout
