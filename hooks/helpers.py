# System
import json
from os import path, pardir
from urlparse import urlunparse

# Globals
env_vars_json_filename = 'env.json'


def set_env(cache_dir, env_vars):
    json_file_path = path.join(cache_dir, env_vars_json_filename)

    with open(json_file_path, 'w') as json_file:
        json_file.write(json.dumps(env_vars))


def set_env_var(cache_dir, key, value):
    env_vars = get_env(cache_dir)

    env_vars[key] = value

    set_env(cache_dir, env_vars)


def get_env(cache_dir):
    json_file_path = path.join(cache_dir, env_vars_json_filename)

    env_vars = {}

    if path.isfile(json_file_path):
        with open(json_file_path) as json_file:
            env_vars = json.loads(json_file.read())

    return env_vars


def parent_dir(dir_path):
    if not path.isdir(dir_path):
        dir_path = path.dirname(dir_path)

    return path.abspath(path.join(dir_path, pardir))


def build_url(
    scheme, domain,
    port=None, username=None, password=None,
    path='', params='', query='', fragment=''
):
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


def ansible_config(charm_dir, config_data):
    '''
    Collect config settings from an ansible role
    by reading both 'defaults/main.yml'
    and 'vars/main.yml'
    and appending their data to config_data
    '''

    # Local imports - 'cos they weren't ready earlier
    from jinja2 import Environment, FileSystemLoader

    # Setup template parser environment
    wsgi_role_path = path.join(charm_dir, 'roles', 'wsgi-app')
    template_env = Environment(loader=FileSystemLoader(wsgi_role_path))

    config_data = add_yaml_to_config(
        'defaults/main.yml', template_env, config_data
    )

    config_data = add_yaml_to_config(
        'vars/main.yml', template_env, config_data
    )

    return config_data


def add_yaml_to_config(template_path, template_env, config_data):
    import yaml
    from jinja2 import meta, UndefinedError

    # Find variables in template
    content = template_env.loader.get_source(template_env, template_path)
    template_parser = template_env.parse(content[0])
    template_variables = meta.find_undeclared_variables(template_parser)

    # Find undeclared variables not already in context
    undefined_variables = list(set(template_variables) - set(config_data))

    # Parse template
    template = template_env.get_template(template_path)
    yaml_content = template.render(config_data)
    new_variables = yaml.load(yaml_content)
    config_data.update(new_variables)

    # If any new variables were in the undeclared variables
    list_intersection = filter(
        lambda x: x in undefined_variables, new_variables
    )

    if list_intersection:
        add_yaml_to_config(template_path, template_env, config_data)
    elif undefined_variables:
        raise UndefinedError('Undefined variables: ' + str(undefined_variables))

    return config_data
