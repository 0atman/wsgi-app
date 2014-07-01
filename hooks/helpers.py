from os import path, pardir
from urlparse import urlunparse


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
        scheme,
        build_url_host(domain, port, username, password),
        path,
        params,
        query,
        fragment
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
