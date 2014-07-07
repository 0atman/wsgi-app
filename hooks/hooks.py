#!/usr/bin/env python

# System
import sys
from shutil import rmtree
from os import path, mkdir
from datetime import datetime

# Local
import charmhelpers.contrib.ansible
from helpers import (
    build_url, parent_dir, ansible_config,
    set_env_var, get_env, set_env
)
from charmhelpers.core.hookenv import (
    relation_get, relation_set,
    open_port, close_port,
    config, local_unit,
    relations, relation_ids
)
from charmhelpers.core.host import log

# Globals (unfortunately)
charm_dir = parent_dir(__file__)
cache_dir = path.join(charm_dir, 'charm_cache')

# Create the hooks helper which automatically registers the
# required hooks based on the available tags in your playbook.
# By default, running a hook (such as 'config-changed') will
# result in running all tasks tagged with that hook name.
hooks = charmhelpers.contrib.ansible.AnsibleHooks(
    playbook_path='playbook.yml'
)


@hooks.hook('wsgi-file-relation-changed')
def wsgi_relation_joined_changed():
    template_vars = config()
    template_vars['local_unit'] = local_unit()
    log('Config options: ' + str(template_vars))
    ansible_data = ansible_config(charm_dir, template_vars)
    log('Ansible config options: ' + str(ansible_data))

    log_file_path = path.join(
        ansible_data['log_dir'],
        ansible_data['app_label'] + '-access.log'
    )

    env_dictionary = get_env(cache_dir)
    env_list = ["{0}={1}".format(k, v) for k, v in env_dictionary.items()]
    env_string = " ".join(env_list)

    wsgi_relation_settings = {
        'project_name': ansible_data.get('app_label', ''),
        'working_dir': path.join(ansible_data.get('code_dir', ''), 'current'),
        'python_path': ansible_data.get('python_path', ''),
        'wsgi_user': ansible_data.get('wsgi_user', ''),
        'wsgi_group': ansible_data.get('wsgi_group', ''),
        'port': ansible_data.get('listen_port', ''),
        'wsgi_access_logfile': log_file_path,
        'wsgi_wsgi_file': ansible_data.get('wsgi_application', ''),
        'wsgi_extra': '--error-logfile=' + log_file_path,
        'env_extra': env_string,
        'timestamp': datetime.now().isoformat()
    }

    log('wsgi relation settings: ' + str(wsgi_relation_settings))

    # Set these settings on any wsgi-file relations
    for relation_id in relation_ids('wsgi-file'):
        relation_set(
            relation_id=relation_id,
            **wsgi_relation_settings
        )

    log('Relation settings: ' + str(relation_get()))

    open_port(ansible_data['listen_port'])


@hooks.hook('wsgi-relation-broken')
def wsgi_relation_broken():
    template_vars = config()
    template_vars['local_unit'] = local_unit()
    ansible_data = ansible_config(charm_dir, template_vars)

    close_port(ansible_data['listen_port'])


@hooks.hook('pgsql-relation-broken')
def pgsql_relation_broken():
    env_vars = get_env(cache_dir)

    if 'DATABASE_URL' in env_vars:
        del env_vars['DATABASE_URL']

        set_env(env_vars)

        # Reset wsgi relation settings
        wsgi_relation_joined_changed()


@hooks.hook('pgsql-relation-joined', 'pgsql-relation-changed')
def pgsql_relation():
    database_name = relation_get("database")
    database_host = relation_get("host")

    if database_name and database_host:
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

        set_env_var(cache_dir, 'DATABASE_URL', database_url)

        # Reset wsgi relation settings
        wsgi_relation_joined_changed()


@hooks.hook('install', 'upgrade-charm')
def install():
    """Install ansible.

    The hook() helper decorating this install function ensures that after this
    function finishes, any tasks in the playbook tagged with install are
    executed.
    """

    # Recreate cache directory
    if path.isdir(cache_dir):
        rmtree(cache_dir)

    mkdir(cache_dir)

    # Setup ansible
    charmhelpers.contrib.ansible.install_ansible_support(from_ppa=True)


if __name__ == "__main__":
        hooks.execute(sys.argv)
