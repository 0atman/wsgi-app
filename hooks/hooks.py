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
    config, local_unit,
    Hooks
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

# Create the hooks helper which automatically registers the
# required hooks based on the available tags in your playbook.
# By default, running a hook (such as 'config-changed') will
# result in running all tasks tagged with that hook name.
ansible_hooks = charmhelpers.contrib.ansible.AnsibleHooks(
    playbook_path='playbook.yml'
)
hooks = Hooks()


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


@hooks.hook('pgsql-relation-changed', 'config-changed')
def pgsql_relation():
    """
    Setup relation to a postgresql database

    Sets the DATABASE_URL environment variable
    """

    log('Hook function: pgsql_relation')

    for relation_id in relation_ids('pgsql'):
        database_name = relation_get(
            "database",
            rid=relation_id
        )
        database_host = relation_get(
            "host",
            rid=relation_id
        )

        if 'pgsql' in relations() and database_name and database_host:
            # Prepare the charm for postgres database relation
            # By putting database settings in environment variables

            database_url = build_url(
                scheme='postgresql',
                domain=database_host,
                port=relation_get("port"),
                username=relation_get("user"),
                password=relation_get("password"),
                path=database_name
            )

            update_property_in_json_file(
                env_file_path, 'DATABASE_URL', database_url
            )

            # Reset wsgi relation settings
            wsgi_relation()


@hooks.hook('pgsql-relation-broken')
def pgsql_relation_broken():
    """
    Run when postgres relation has gone away
    Remove "DATABASE_URL" environment variable
    """

    log('Hook function: pgsql_relation_broken')

    env_vars = parse_json_file(env_file_path)

    if 'DATABASE_URL' in env_vars:
        del env_vars['DATABASE_URL']

        update_property_in_json_file(env_file_path, env_vars)

        # Reset wsgi relation settings
        wsgi_relation()


@hooks.hook('start', 'config-changed')
def update_target():
    """
    Run the "update-charm" make target within the project
    """

    log('Hook function: update_target')

    config_data = ansible_config()

    required_configs = [
        'build_label',
        'archive_filename',
        'code_dir',
        'update_make_target'
    ]

    # Check all required configs are set
    if items_are_not_empty(config_data, required_configs):
        env_vars = parse_json_file(env_file_path)

        # Execute make target with all environment variables
        sh.make(
            config_data['update_make_target'],
            directory=path.join(config_data.get('code_dir', ''), 'current'),
            _env=env_vars
        )


@hooks.hook('wsgi-file-relation-changed', 'config-changed')
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

    open_port(config_data['listen_port'])


@hooks.hook('wsgi-relation-broken')
def wsgi_relation_broken():
    """
    When WSGI relation (e.g.: gunicorn) goes away

    """

    log('Hook function: wsgi_relation_broken')

    config_data = ansible_config()

    close_port(config_data['listen_port'])


if __name__ == "__main__":
        hooks.execute(sys.argv)
