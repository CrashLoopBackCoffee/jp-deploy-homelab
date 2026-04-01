import pathlib

import pulumi as p


def directory_content(path: pathlib.Path) -> list[str]:
    """
    Returns the contents of all files in a directory, sorted by path for determinism.
    """
    contents = []
    for file in sorted(path.rglob('*')):
        if file.is_file():
            contents.append(file.read_text())
    return contents


def stack_is_prod() -> bool:
    return p.get_stack() == 'prod'
