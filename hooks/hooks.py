#!/usr/bin/env python

# System
import sys

# Local
import charmhelpers.contrib.ansible
from helpers import build_url
from charmhelpers.core.hookenv import (
    relation_get
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
    # Remove the postgres environment variable
    NotImplementedError(
        '''
        Clear the database URL environment variable
        '''
    )


@hooks.hook('pgsql-relation-joined', 'pgsql-relation-changed')
def pgsql_relation():
    database_name = relation_get("database")
    database_host = relation_get("host")

    if database_name and database_host:
        # Prepare the charm for postgres database relation
        # By putting database settings in a python settings file

        build_url(
            scheme='postgresql',
            domain=database_host,
            port=relation_get("port"),
            username=relation_get("user"),
            password=relation_get("password"),
            path=database_name
        )

    NotImplementedError(
        '''
        Set the environment variable
        for the database URL in gunicorn
        '''
    )


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
