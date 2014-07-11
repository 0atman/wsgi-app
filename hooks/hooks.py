#!/usr/bin/env python

# System
import sys
from shutil import rmtree
from os import path, mkdir
from datetime import datetime

# Local
import sh
from helpers import (
    build_url, parent_dir, add_ansible_config,
    update_property_in_json_file, parse_json_file,
    items_are_not_empty
)
import charmhelpers.contrib.ansible
from charmhelpers.core.hookenv import (
    relation_get, relation_set,
    open_port, close_port,
    relation_ids, relations,
    config, local_unit
)
from charmhelpers.core.host import log

# Globals (unfortunately)
charm_dir = parent_dir(__file__)
cache_dir = path.join(charm_dir, 'charm_cache')
env_file_path = path.join(cache_dir, 'env.json')


def ansible_config():
    """
    Build ansible config data, extending current config_data
    and with the local unit name
    """

    config_data = config()
    config_data['local_unit'] = local_unit()
    return add_ansible_config(charm_dir, config_data)


def update_target():
    """
    Run the "update-charm" make target within the project
    """

    log('Hook function: update_target')

    config_data = ansible_config()

    required_configs = [
        'build_label',
        'archive_filename',
        'current_code_dir',
        'update_make_target'
    ]

    # Check all required configs are set
    if (
        items_are_not_empty(config_data, required_configs)
        and path.isdir(config_data['current_code_dir'])
    ):
        # Ensure make is installed
        apt_output = sh.apt_get.install('make')
        log('Installed make:')
        log(str(apt_output))

        env_vars = parse_json_file(env_file_path)

        # Execute make target with all environment variables
        make_output = sh.make(
            config_data['update_make_target'],
            directory=path.join(config_data['current_code_dir']),
            _env=env_vars
        )

        log('Make output:')
        log(str(make_output))


def link_database(
    scheme,
    database_host,
    port='',
    username='',
    password='',
    database_name=''
):
    """
    Create a link with a database
    by setting the DATABASE_URL environment variable
    """

    database_url = build_url(
        scheme='postgresql',
        domain=database_host,
        port=relation_get("port"),
        username=,
        password=relation_get("password"),
        path=database_name
    )

    update_property_in_json_file(
        env_file_path, 'DATABASE_URL', database_url
    )

    # Relation changed - re-run update target
    update_target()

    # Reset wsgi relation settings
    wsgi_relation()


# Create the hooks helper which automatically registers the
# required hooks based on the available tags in your playbook.
# By default, running a hook (such as 'config-changed') will
# result in running all tasks tagged with that hook name.
hooks = charmhelpers.contrib.ansible.AnsibleHooks(
    playbook_path='playbook.yml'
)


@hooks.hook('wsgi-file-relation-changed')
def wsgi_relation():
    """
    Setup relation for serving the WSGI file (e.g. gunicorn)

    Sets a whole bunch of relation settings
    including log file locations and environent variables
    """

    log('Hook function: wsgi_relation')

    config_data = ansible_config()

    log_file_path = path.join(
        config_data['log_dir'],
        config_data['app_label'] + '-access.log'
    )

    env_dictionary = parse_json_file(env_file_path)
    env_list = ["{0}={1}".format(k, v) for k, v in env_dictionary.items()]
    env_string = " ".join(env_list)

    wsgi_relation_settings = {
        'project_name': config_data.get('app_label', ''),
        'working_dir': path.join(config_data.get('code_dir', ''), 'current'),
        'python_path': config_data.get('python_path', ''),
        'wsgi_user': config_data.get('wsgi_user', ''),
        'wsgi_group': config_data.get('wsgi_group', ''),
        'port': config_data.get('listen_port', ''),
        'wsgi_access_logfile': log_file_path,
        'wsgi_wsgi_file': config_data.get('wsgi_application', ''),
        'wsgi_extra': '--error-logfile=' + log_file_path,
        'env_extra': env_string,
        'timestamp': datetime.now().isoformat()
    }

    # Set these settings on any wsgi-file relations
    for relation_id in relation_ids('wsgi-file'):
        log(
            'Setting wsgi-file relation settings: '
            + str(wsgi_relation_settings)
        )

        relation_set(
            relation_id=relation_id,
            **wsgi_relation_settings
        )

        # Relation changed - re-run update target
        update_target()

    open_port(config_data['listen_port'])


@hooks.hook('wsgi-relation-broken')
def wsgi_relation_broken():
    """
    When WSGI relation (e.g.: gunicorn) goes away
    """

    log('Hook function: wsgi_relation_broken')

    config_data = ansible_config()

    close_port(config_data['listen_port'])


@hooks.hook('pgsql-relation-changed')
def pgsql_relation():
    """
    Setup relation to a postgresql database
    (will replace any other database relations)
    """

    log('Hook function: pgsql_relation')

    host = relation_get("host")

    if 'pgsql' in relations() and host:
        link_database(
            scheme='postgresql',
            database_host=host,
            port=relation_get("port"),
            username=relation_get("user"),
            password=relation_get("password"),
            database_name=relation_get("database")
        )


@hooks.hook('mongodb-relation-changed')
def mongodb_relation():
    """
    Setup relation to a mongodb database
    (will replace any other database relations)
    """

    log('Hook function: mongodb_relation')

    host = relation_get("hostname")

    if 'mongodb' in relations() and host:
        link_database(
            scheme='mongodb',
            database_host=host,
            port=relation_get("port"),
            username=relation_get("user"),
            password=relation_get("password"),
            database_name=relation_get("database")
        )


@hooks.hook('pgsql-relation-broken', 'mongodb-relation-broken')
def unlink_database():
    """
    Remove "DATABASE_URL" environment variable
    """

    log('Function: unlink_database')

    env_vars = parse_json_file(env_file_path)

    if 'DATABASE_URL' in env_vars:
        del env_vars['DATABASE_URL']

        update_property_in_json_file(env_file_path, env_vars)

        # Reset wsgi relation settings
        wsgi_relation()


@hooks.hook('webservice-relation-changed')
def webservice_relation():
    """
    Create "WEBSERVICE_URL" environment variable from relation
    """

    log('Function: webservice_relation')

    webservice_url = build_url(
        scheme='http',
        domain=relation_get('hostname'),
        port=relation_get("port")
    )

    update_property_in_json_file(
        env_file_path, 'WEBSERVICE_URL', webservice_url
    )

    # Relation changed - re-run update target
    update_target()

    # Reset wsgi relation settings
    wsgi_relation()


@hooks.hook('webservice-relation-broken')
def unlink_webservice():
    """
    Remove "WEBSERVICE_URL" environment variable
    """

    log('Function: unlink_database')

    env_vars = parse_json_file(env_file_path)

    if 'WEBSERVICE_URL' in env_vars:
        del env_vars['WEBSERVICE_URL']

        update_property_in_json_file(env_file_path, env_vars)

        # Reset wsgi relation settings
        wsgi_relation()


@hooks.hook('install', 'upgrade-charm')
def install():
    """
    - Install ansible
    - Create the cache directory

    The hook() helper decorating this install function ensures that after this
    function finishes, any tasks in the playbook tagged with install are
    executed.
    """

    log('Hook function: install')

    # Recreate cache directory
    if path.isdir(cache_dir):
        rmtree(cache_dir)

    mkdir(cache_dir)

    # Setup ansible
    charmhelpers.contrib.ansible.install_ansible_support(from_ppa=True)


@hooks.hook('config-changed')
def config_changed():
    """
    Run everything which should be updated when config changes
    """

    pgsql_relation()
    mongodb_relation()
    wsgi_relation()
    update_target()


if __name__ == "__main__":
    hooks.execute(sys.argv)
