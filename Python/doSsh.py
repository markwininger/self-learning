#!/usr/local/bin python3.6

try:
    import logging
    import sys
    import paramiko
except ImportError:
    print(f"{sys.exc_info()}")


"""
It takes a command, a host, a username, a password, and an encoding, and returns the
output of the command as a list of strings

:param cmd: The command to run on the remote host
:param host: the hostname or IP address of the remote server
:param my_user: The username to use to connect to the remote host
:param my_pass: the password for the user
:param encoding: utf-8
:return: A list of strings.
"""


def ssh(cmd, host, my_user, my_pass, encoding):
    client = paramiko.SSHClient()
    client.load_system_host_keys()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    host = host.rstrip()
    try:
        client.connect(host, username=my_user, password=my_pass, timeout=60)
    except (SystemExit, KeyboardInterrupt):
        raise
    except Exception as e:
        logger.exception(f"Exception occurred contacting {host}")
        return []
    stdin, stdout, stderr = client.exec_command(f"{cmd}")
    return stdout.readlines()


logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.WARNING
)
logger = logging.getLogger(__name__)
