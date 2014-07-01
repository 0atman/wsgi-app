#!/usr/bin/env python

# System
import sys
from time import time
from os import path, makedirs, remove

# Local
import charmhelpers.contrib.ansible
from helpers import parent_dir
from jinja2 import Environment, FileSystemLoader
from charmhelpers.fetch import apt_install
from charmhelpers.core.hookenv import (
    relation_get, config, local_unit, relation_set
)

# Create the hooks helper which automatically registers the
# required hooks based on the available tags in your playbook.
# By default, running a hook (such as 'config-changed') will
# result in running all tasks tagged with that hook name.
hooks = charmhelpers.contrib.ansible.AnsibleHooks(
    playbook_path='playbook.yml'
)


@hooks.hook('pgsql-relation-broken')
def pgsql_relation_broken():
    build_label = config('build_label')

    # Config file path
    if build_label:
        unit_name = local_unit().replace('/', '-')
        config_file = path.join(
            "/srv",
            unit_name,
            "code",
            build_label,
            config('relation_config_dir'),
            'pgsql.py'
        )

    # Remove the file
    if path.isfile(config_file):
        remove(config_file)


@hooks.hook('pgsql-relation-joined', 'pgsql-relation-changed')
def pgsql_relation():
    database_name = relation_get("database")
    host = relation_get("host")
    build_label = config('build_label')

    if database_name and host and build_label:
        # Prepare the charm for postgres database relation
        # By putting database settings in a python settings file

        # Get database template
        charm_dir = parent_dir(__file__)
        jinja_env = Environment(loader=FileSystemLoader(charm_dir))
        database_template = jinja_env.get_template('templates/pgsql.tmpl')

        # Get database information
        apt_install(['python-psycopg2', 'postgresql-client'])

        # Get relation settings directory
        unit_name = local_unit().replace('/', '-')
        config_dir = path.join(
            "/srv",
            unit_name,
            "code",
            build_label,
            config('relation_config_dir')
        )

        # Make sure dir exists
        if not path.isdir(config_dir):
            makedirs(config_dir)

        # Database settings
        relation_context = database_template.render({
            "name": database_name,
            "host": host,
            "user": relation_get("user"),
            "password": relation_get("password")
        })

        # Write settings
        with open(path.join(config_dir, 'pgsql.py'), 'a') as config_file:
            config_file.write(relation_context)

        # Set timestamp to trigger service restart
        relation_set(wsgi_timestamp=time())


@hooks.hook('install', 'upgrade-charm')
def install():
    """Install ansible.

    The hook() helper decorating this install function ensures that after this
    function finishes, any tasks in the playbook tagged with install are
    executed.
    """
    charmhelpers.contrib.ansible.install_ansible_support(from_ppa=True)


if __name__ == "__main__":
        hooks.execute(sys.argv)
