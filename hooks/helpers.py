from os import path, pardir


def parent_dir(dir_path):
    if not path.isdir(dir_path):
        dir_path = path.dirname(dir_path)

    return path.abspath(path.join(dir_path, pardir))
