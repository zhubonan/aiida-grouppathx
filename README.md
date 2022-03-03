[![Build Status][ci-badge]][ci-link]
[![Coverage Status][cov-badge]][cov-link]
[![Docs status][docs-badge]][docs-link]
[![PyPI version][pypi-badge]][pypi-link]

# aiida-grouppathx

AiiDA plugin provides the `GroupPathX` class.

This plugin was kickstarted using
[AiiDA plugin cutter](https://github.com/aiidateam/aiida-plugin-cutter),
intended to help developers get started with their AiiDA plugins.

## Features and usage

 This package is provides a enhanced version of `GroupPath` - `GroupPathX`.
 The main feature is that it allows nodes stored undert a group to be *named* by an alias.
 This way, one can address a specific `Node` as `GroupPath('mygroup/structure1')`.
 In addition, a `show_tree` method is provided for visualising the content of a specific `GroupPathX`,
 similiar too the command line tool `tree` that works on the file system.
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
path.add_node(Int(1).store(), 'int1')
path['group2'].add_node(Int(1).store(), 'int2')

path.show_tree()
```

gives

```
group1
├── group2
│   └── int2*
└── int1*
```

where the `*` highlights that a leaf is a `Node` rather than a group.
This kind of mark up can be customised, for example, to show the status of workflow nodes.

```python
def decorate_name(path):
    if path.is_node:
        return ' ' + str(path.get_node())
path.show_tree()
```

gives:

```
group1
├── group2
│   └── int2 uuid: de79d244-d3bb-4f61-9d3a-b3f09e1afb72 (pk: 7060) value: 1
└── int1 uuid: e2f70643-0c25-4ae5-929a-a3e055969d10 (pk: 7059) value: 1
```

The stored nodes can be access through:

```
group1['group2/int2'].get_node()  # Gives node de89d2
group1.browse.group2.int2().get_node(  # Also gives node de89d2
```


Please see the `pathx.py` for the extended methods, and the official documentation for the concept of `GroupPath`.

## Installation

```shell
pip install aiida-grouppathx
verdi quicksetup  # better to set up a new profile
verdi plugin list aiida.calculations  # should now show your calclulation plugins
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
