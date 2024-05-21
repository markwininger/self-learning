#!/usr/local/bin python3.6

try:
    import logging
    import sys

    from doSsh import ssh
    from apiGet import api_get
except ImportError:
    print(f"{sys.exc_info()}")


def do_command(
    command,
    my_url,
    my_user=None,
    my_pass=None,
    protocol="api",
    my_modifiers=None,
    headers="",
):
    """
    A function that takes in a command, url, user, password, protocol, modifiers, and
    headers. It then tries to run the command based on the protocol. If the protocol is api,
    it will run the api_get function. If the protocol is ssh, it will run the ssh function.

    :param command: The command to run
    :param my_url: The URL of the array
    :param my_user: username
    :param my_pass: The password for the array
    :param protocol: api or ssh, defaults to api (optional)
    :param my_modifiers: This is a dictionary of key/value pairs that are used to modify the
    API call
    :param headers: This is a dictionary of headers to be passed to the API call
    :return: The output of the command
    """
    try:
        if protocol == "api":
            do_command = api_get(
                my_url=my_url,
                name=command,
                my_user=my_user,
                my_pass=my_pass,
                key=my_modifiers,
                headers=headers,
            )
        elif protocol == "ssh":
            do_command = ssh(
                cmd=command,
                host=my_url,
                my_user=my_user,
                my_pass=my_pass,
                encoding="utf-8",
            )
        logger.debug(f"{do_command}")
        return do_command
    except (SystemExit, KeyboardInterrupt):
        raise
    except Exception as e:
        logger.exception("Exception occurred while contacting array")


logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.WARNING
)
logger = logging.getLogger(__name__)
