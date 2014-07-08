# System
import json
from os import path, pardir
from urlparse import urlunparse
from collections import namedtuple


def literal(**kw):
    """
    Create an "object literal"
    by creating a named tuple with keyword arguments
    """

    return namedtuple('literal', kw)(**kw)


def save_to_json_file(json_file_path, data_to_save):
    """
    Save a python object as json in a file
    """

    with open(json_file_path, 'w') as json_file:
        json_file.write(json.dumps(data_to_save))


def update_property_in_json_file(json_file_path, key, value):
    """
    Given a path to a file containing a JSON object
    Set the value of a property on that JSON object
    """

    json_data = parse_json_file(json_file_path)

    json_data[key] = value

    save_to_json_file(json_file_path, json_data)


def parse_json_file(json_file_path):
    """
    I think the name says it all...
    """

    env_vars = {}

    if path.isfile(json_file_path):
        with open(json_file_path) as json_file:
            env_vars = json.loads(json_file.read())

    return env_vars


def parent_dir(dir_path):
    """
    Get the parent dir from of the top directory for a path,
    regardless of whether the path ends in a filename or not

    > parent_dir('/my/favourite/directory')
    '/my/favourite'

    > parent_dir('/my/favourite/directory/my-file.txt')
    '/my/favourite'
    """

    if not path.isdir(dir_path):
        dir_path = path.dirname(dir_path)

    return path.abspath(path.join(dir_path, pardir))


def build_url(
    domain,
    scheme='http', port=None, username=None, password=None,
    path='', params='', query='', fragment=''
):
    """
    Build a URL from its parts

    This is just a proxy for urlunparse,
    but with more descriptive parameter names

    > build_url(domain='example.com', port=8080, path='users')
    'http://example.com:8080/users'
    """

    return urlunparse(
        (
            scheme,
            build_url_host(domain, port, username, password),
            path,
            params,
            query,
            fragment
        )
    )


def build_url_host(domain, port=None, username=None, password=None):
    """
    Build the host part of a URL from a domain, port, username and password

    > build_url_host('example.com')
    'example.com'

    > build_url_host('example.com', 8080)
    'example.com:8080'

    > build_url_host('example.com', 8080, 'robin')
    'robin@example.com:8080'

    > build_url_host('example.com', 8080, 'robin', 'mypassword')
    'robin:mypassword@example.com:8080'
    """

    host = domain

    if port:
        host = "{0}:{1}".format(domain, port)

    if username:
        credentials = username

        if password:
            credentials = "{0}:{1}".format(
                username, password
            )

        host = "{0}@{1}".format(credentials, host)

    return host


def add_ansible_config(charm_dir, config_data):
    """
    Collect config settings from an ansible role
    by reading both 'defaults/main.yml'
    and 'vars/main.yml'
    and appending their data to config_data
    """

    # Local imports - 'cos they weren't ready earlier
    from jinja2 import Environment, FileSystemLoader

    # Setup template parser environment
    wsgi_role_path = path.join(charm_dir, 'roles', 'wsgi-app')
    template_env = Environment(loader=FileSystemLoader(wsgi_role_path))

    config_data = update_from_yaml_template(
        'defaults/main.yml', template_env, config_data
    )

    config_data = update_from_yaml_template(
        'vars/main.yml', template_env, config_data
    )

    return config_data


def update_from_yaml_template(template_path, parser_env, data):
    """
    Given a path to a yaml file and a template parser environment
    add all data in the yaml file to the provided data dictionary
    """

    import yaml
    from jinja2 import meta, UndefinedError

    # Find variables in template
    content = parser_env.loader.get_source(parser_env, template_path)
    parsed_template = parser_env.parse(content[0])
    template_variables = meta.find_undeclared_variables(parsed_template)

    # Find undeclared variables not already in context
    undefined_variables = list(set(template_variables) - set(data))

    # Parse template
    template = parser_env.get_template(template_path)
    yaml_content = template.render(data)
    new_variables = yaml.load(yaml_content)
    data.update(new_variables)

    # If any new variables were in the undeclared variables
    list_intersection = filter(
        lambda x: x in undefined_variables, new_variables
    )

    if list_intersection:
        data = update_from_yaml_template(template_path, parser_env, data)
    elif undefined_variables:
        raise UndefinedError('Undefined variables: ' + str(undefined_variables))

    return data


def items_are_not_empty(test_dictionary, items_to_test):
    """
    For a list of keys, check all items in a dictionary with those key names
    are not empty

    > items_are_not_empty({'a': 'hi'}, ['a'])
    True

    > items_are_not_empty({'a': 'hi', 'b': ''}, ['a', 'b'])
    False

    > items_are_not_empty({'a': 'hi', 'b': ''}, ['a', 'c'])
    False

    > items_are_not_empty({'a': 'hi', 'b': '', 'c': 1}, ['a', 'c'])
    True

    """

    # A list of booleans representing whether items evaluate to True
    item_booleans = [bool(test_dictionary.get(k)) for k in items_to_test]

    # Return True only if all items are present and True
    return reduce(lambda x, y: x and y, item_booleans)
