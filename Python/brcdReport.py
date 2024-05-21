#!/usr/local/bin python3.6

try:
    import logging
    import os
    import sys

    from brcdCrcInfo import brcd_crc_info
    from brcdSwitchInfo import brcd_switch_info
    from doEmail import do_email
except ImportError:
    print(f"{sys.exc_info()}")


"""
This function will take the URL, username, and password of a Brocade switch and return
the switch's model, serial number, firmware version, and uptime

:param my_url: The URL or IP address of the target
:param my_user: admin
:param my_pass: The basic authentication password
"""


def main(my_url, my_user, my_pass):
    brcd_switch_info(my_url, my_user, my_pass)
    brcd_crc_info(my_url, my_user, my_pass)


logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.WARNING
)
logger = logging.getLogger(__name__)


if __name__ == "__main__":
    my_user = os.environ["brcd_user"]
    my_pass = os.environ["brcd_pass"]
    switches = os.environ["nodes"]
    logger.debug(f"{my_user} {my_pass} {switches}")
    switch_list = switches.split(",")
    logger.debug(f"{switch_list}")
    for switch_name in switch_list:
        main(f"{switch_name}", my_user, my_pass)
