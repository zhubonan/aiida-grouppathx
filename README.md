[![Build Status][ci-badge]][ci-link]
[![Coverage Status][cov-badge]][cov-link]
[![PyPI version][pypi-badge]][pypi-link]

# aiida-grouppathx

AiiDA plugin provides the `GroupPathX` class.

This plugin was kickstarted using
[AiiDA plugin cutter](https://github.com/aiidateam/aiida-plugin-cutter),
intended to help developers get started with their AiiDA plugins.

## Features and usage

Interactive example at: [![Binder](https://mybinder.org/badge_logo.svg)](https://mybinder.org/v2/gh/zhubonan/aiida-nbexamples/HEAD)

### Organize AiiDA data with a file-system-like interface

This package provides a enhanced version of `GroupPath` - `GroupPathX`.
The main feature is that it allows nodes stored under a group to be *named* by an alias.
This way, one can address a specific `Node` as `GroupPath('mygroup/structure1')`.
In addition, a `show_tree` method is provided for visualising the content of a specific `GroupPathX`,
similar to the command line tool `tree` that works on the file system.
The goal is to provide a way for managing data with an interface what is similar to a file system based approach.

```
tree aiida_grouppathx

aiida_grouppathx
├── __init__.py
├── pathx.py
└── __pycache__
    ├── __init__.cpython-38.pyc
    └── pathx.cpython-38.pyc
```

In analogy:

```python
from aiida_grouppathx import GroupPathX
path = GroupPathX('group1')
path.get_or_create_group()
path['group2'].get_or_create_group()
path['int1'] = Int(1)
path['group2']['int1'] = Int(1)

path.show_tree()
```

gives

```
group1
├── group2
│   └── int2 *
└── int1 *
```

where the `*` highlights that a leaf is a `Node` rather than a group.
This kind of mark up can be customised, for example, to show the status of workflow nodes.

```python
def decorate_name(path):
    if path.is_node:
        return ' ' + str(path.get_node())
path.show_tree(decorate_name)
```

gives:

```
group1
├── group2
│   └── int2  uuid: de79d244-d3bb-4f61-9d3a-b3f09e1afb72 (pk: 7060) value: 1
└── int1  uuid: e2f70643-0c25-4ae5-929a-a3e055969d10 (pk: 7059) value: 1
```

Multiple decorators can be combined

```
from aiida_grouppathx import decorate_with_group_names, decorate_with_label decorate_with_uuid_first_n

path.show_tree(decorate_with_group_names, decorate_with_label, decorate_with_uuid_first_n())
```

output:

```
group1
├── group2
│   └── int2 group1/group2 |  | de79d244-d3b
└── int1 group1 |  | e2f70643-0c2
```

One can also use pre- defined decorators to decorate the output of `show_tree`:

```python
path.show_tree(decorate_by=['label', 'uuid_first_12'])
```

which is equivalent to the method above.


The stored nodes can be access through:

```
group1['group2/int2'].get_node()  # Gives node de89d2
group1.browse.group2.int2().get_node()  # Also gives node de89d2
```

and also

```
path.browse.<tab>
path.browse.int1()     # To access the `group1/int1` path
path.browse.int1().get_node()     # To access the `group1/int1` node
```

Please see the `pathx.py` for the extended methods, and the official documentation for the concept of `GroupPath`.

The package does not change how `Group` and `Node` operates in the AiiDA.
It is only built on top of the existing system as an alternative way to access the underlying data.

The nodes under a `GroupPathX` can be be added using `add_node` or `add_nodes` methods.
Existing node can be deleted or rename using `unlink` or `rename` methods.
Note that `unlink` does not dissociate the node from the actual group, but only removes its alias stored
inside the `extras` that is used by this package

## Keeping a limited number of active jobs

When performing high-throughput workflows, it may be necessary to limit the number of active jobs to avoid overloading the remote computer.
We provide a `GroupLauncher` method to achieve this.
The idea is to use a group path of jobs inputs as inputs,
and store the launched jobs in another `GropuPathX`, for example:

```python
from aiida_grouppathx import GroupPathX, GroupLauncher
launcher = GroupLauncher(GroupPathX('target_group'), max_concurrent=200, callback=launch_relax, source_gp=GroupPathX('source_group'))
launcher.launch()
```

Here the a callback function `launch_relax` is called for each node in the `source_group` with the node and its alias as the input arguments.
This callback function should launch the calculation/workchain and return a tuple of the `ProcessBuilder` object to be submitted to the AiiDA daemon,
and the alias to store the resulting `ProcessNode` inside the `target_group`.

Instead of using a `GroupPathX` as the source, one can also use a list of nodes and alias pairs the source by
passing them through the `source_key_obj_pairs` keyword argument.


## Installation

```shell
pip install aiida-grouppathx
verdi quicksetup  # better to set up a new profile
```

## Development

```shell
git clone https://github.com/zhubonan/aiida-grouppathx .
cd aiida-grouppathx
pip install --upgrade pip
pip install -e .[pre-commit,testing]  # install extra dependencies
pre-commit install  # install pre-commit hooks
pytest -v  # discover and run all tests
```

See the [developer guide](http://aiida-grouppathx.readthedocs.io/en/latest/developer_guide/index.html) for more information.

## License

MIT
## Contact

zhubonan@outlook.com


[ci-badge]: https://github.com/zhubonan/aiida-grouppathx/workflows/ci/badge.svg?branch=master
[ci-link]: https://github.com/zhubonan/aiida-grouppathx/actions
[cov-badge]: https://coveralls.io/repos/github/zhubonan/aiida-grouppathx/badge.svg?branch=master
[cov-link]: https://coveralls.io/github/zhubonan/aiida-grouppathx?branch=master
[docs-badge]: https://readthedocs.org/projects/aiida-grouppathx/badge
[docs-link]: http://aiida-grouppathx.readthedocs.io/
[pypi-badge]: https://badge.fury.io/py/aiida-grouppathx.svg
[pypi-link]: https://badge.fury.io/py/aiida-grouppathx
