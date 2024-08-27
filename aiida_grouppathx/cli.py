"""
Commandline interface
"""

import click
from aiida.cmdline.commands.cmd_data import verdi_data
from aiida.cmdline.params import arguments
from aiida.cmdline.utils import decorators, echo
from aiida.cmdline.utils.echo import echo_error, echo_success

# pylint: disable=import-outside-toplevel


@verdi_data.group('gpx')
def grouppathx_cli():
    """Command line interface for aiida-grouppathx"""


@grouppathx_cli.command('show-tree')
@decorators.with_dbenv()
@click.argument('path')
def show_tree(path):
    """Print a tree diagram of the group"""
    from aiida_grouppathx import GroupPathX

    gpx = GroupPathX(path)
    output = gpx.show_tree(stdout=False)
    click.echo(output)


@grouppathx_cli.command('show')
@decorators.with_dbenv()
@click.argument('path')
@click.option('--include-deleted', is_flag=True, default=False)
def show(path, include_deleted):
    """Show a path, if the path corresponds to a Node or a Group"""
    from aiida_grouppathx import GroupPathX
    from aiida_grouppathx.pathx import GROUP_ALIAS_KEY

    gpx = GroupPathX(path)
    node = gpx.get_node()
    # If the path corresponds to a group, then show the information of the Node
    if node:
        from aiida.cmdline.utils.common import get_node_info

        click.echo(get_node_info(node))
        return

    # If the path corresponds to a group, then show the information of the group
    group = gpx.get_group()
    if group:
        from aiida.common import timezone
        from aiida.common.utils import str_timedelta
        from tabulate import tabulate

        desc = group.description
        now = timezone.now()

        table = []
        table.append(['Group label', group.label])
        table.append(['Group type_string', group.type_string])
        table.append(['Group description', desc if desc else '<no description>'])
        echo.echo(tabulate(table))

        table = []
        header = ['PK', 'Alias', 'Type', 'Created']
        if include_deleted:
            header = ['PK', 'Alias', 'Alias(deleted)', 'Type', 'Created']

        echo.echo('# Nodes:')
        for node in group.nodes:
            row = []
            row.append(node.pk)
            alias = node.base.extras.get(GROUP_ALIAS_KEY, {}).get(group.uuid, '')
            row.append(alias)
            if include_deleted:
                alias = node.base.extras.get(GROUP_ALIAS_KEY + '_deleted', {}).get(group.uuid, '')
                row.append(alias)

            row.append(node.node_type.rsplit('.', 2)[1])
            row.append(str_timedelta(now - node.ctime, short=True, negative_to_zero=True))
            table.append(row)
        echo.echo(tabulate(table, headers=header))
        return

    echo_error(f'Path: {path} does not corresppond to a Node or a Group.')


@grouppathx_cli.command('add-node')
@decorators.with_dbenv()
@click.argument('path')
@click.argument('alias')
@arguments.NODE()
@click.option('--force', is_flag=True, default=False)
def add_node(path, alias, node, force):
    """Add a node to a specific path with alias"""
    from aiida_grouppathx import GroupPathX

    gpx = GroupPathX(path)
    gpx.add_node(node, alias, force)
    echo_success(f'Added {node} to path {path} with alias {alias}.')


@grouppathx_cli.command('alias')
@decorators.with_dbenv()
@arguments.NODE()
def show_alias(node):
    """Show the path(s) of a node"""
    from aiida import orm

    from aiida_grouppathx.pathx import GROUP_ALIAS_KEY, GroupPathX

    alias_dict = node.base.extras.get(GROUP_ALIAS_KEY)
    if alias_dict is None:
        echo_error(f'Node {node} is not associated with any GroupPathX.')
    for key, value in alias_dict.items():
        group = orm.Group.collection.get(uuid=key)
        path_obj = GroupPathX(group.label)[value]
        click.echo(path_obj.path)


@grouppathx_cli.command('unlink')
@click.argument('path')
@decorators.with_dbenv()
def unlink(path):
    """Unlink a path that corresponds to a Node"""
    from aiida_grouppathx import GroupPathX

    obj = GroupPathX(path)
    if obj.get_node():
        obj.unlink()
    else:
        echo_error(f'Path: {path} does not corresponds to a node')
