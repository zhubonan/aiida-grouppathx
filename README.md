[![Build Status][ci-badge]][ci-link]
[![Coverage Status][cov-badge]][cov-link]
[![Docs status][docs-badge]][docs-link]
[![PyPI version][pypi-badge]][pypi-link]

# aiida-grouppathx

AiiDA plugin provides the `GroupPathX` class.

This plugin is the default output of the
[AiiDA plugin cutter](https://github.com/aiidateam/aiida-plugin-cutter),
intended to help developers get started with their AiiDA plugins.

## Repository contents

* [`.github/`](.github/): [Github Actions](https://github.com/features/actions) configuration
  * [`ci.yml`](.github/workflows/ci.yml): runs tests, checks test coverage and builds documentation at every new commit
  * [`publish-on-pypi.yml`](.github/workflows/publish-on-pypi.yml): automatically deploy git tags to PyPI - just generate a [PyPI API token](https://pypi.org/help/#apitoken) for your PyPI account and add it to the `pypi_token` secret of your github repository
* [`aiida_grouppathx/`](aiida_grouppathx/): The main source code of the plugin package
  * [`data/`](aiida_grouppathx/data/): A new `DiffParameters` data class, used as input to the `DiffCalculation` `CalcJob` class
  * [`calculations.py`](aiida_grouppathx/calculations.py): A new `DiffCalculation` `CalcJob` class
  * [`cli.py`](aiida_grouppathx/cli.py): Extensions of the `verdi data` command line interface for the `DiffParameters` class
  * [`helpers.py`](aiida_grouppathx/helpers.py): Helpers for setting up an AiiDA code for `diff` automatically
  * [`parsers.py`](aiida_grouppathx/parsers.py): A new `Parser` for the `DiffCalculation`
* [`docs/`](docs/): A documentation template ready for publication on [Read the Docs](http://aiida-diff.readthedocs.io/en/latest/)
* [`examples/`](examples/): An example of how to submit a calculation using this plugin
* [`tests/`](tests/): Basic regression tests using the [pytest](https://docs.pytest.org/en/latest/) framework (submitting a calculation, ...). Install `pip install -e .[testing]` and run `pytest`.
* [`.gitignore`](.gitignore): Telling git which files to ignore
* [`.pre-commit-config.yaml`](.pre-commit-config.yaml): Configuration of [pre-commit hooks](https://pre-commit.com/) that sanitize coding style and check for syntax errors. Enable via `pip install -e .[pre-commit] && pre-commit install`
* [`.readthedocs.yml`](.readthedocs.yml): Configuration of documentation build for [Read the Docs](https://readthedocs.org/)
* [`LICENSE`](LICENSE): License for your plugin
* [`README.md`](README.md): This file
* [`conftest.py`](conftest.py): Configuration of fixtures for [pytest](https://docs.pytest.org/en/latest/)
* [`pyproject.toml`](setup.json): Python package metadata for registration on [PyPI](https://pypi.org/) and the [AiiDA plugin registry](https://aiidateam.github.io/aiida-registry/) (including entry points)

See also the following video sequences from the 2019-05 AiiDA tutorial:

 * [run aiida-diff example calculation](https://www.youtube.com/watch?v=2CxiuiA1uVs&t=403s)
 * [aiida-diff CalcJob plugin](https://www.youtube.com/watch?v=2CxiuiA1uVs&t=685s)
 * [aiida-diff Parser plugin](https://www.youtube.com/watch?v=2CxiuiA1uVs&t=936s)
 * [aiida-diff computer/code helpers](https://www.youtube.com/watch?v=2CxiuiA1uVs&t=1238s)
 * [aiida-diff input data (with validation)](https://www.youtube.com/watch?v=2CxiuiA1uVs&t=1353s)
 * [aiida-diff cli](https://www.youtube.com/watch?v=2CxiuiA1uVs&t=1621s)
 * [aiida-diff tests](https://www.youtube.com/watch?v=2CxiuiA1uVs&t=1931s)
 * [Adding your plugin to the registry](https://www.youtube.com/watch?v=760O2lDB-TM&t=112s)
 * [pre-commit hooks](https://www.youtube.com/watch?v=760O2lDB-TM&t=333s)

For more information, see the [developer guide](https://aiida-diff.readthedocs.io/en/latest/developer_guide) of your plugin.


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
