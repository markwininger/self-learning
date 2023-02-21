#!/usr/local/bin python3.6

try:
    import json
    import logging
    import sys

    from doCommand import do_command
except ImportError:
    print(f"{sys.exc_info()}")


"""
This function takes a URL, username, and password and returns the number of configs,
zones, and aliases on the switch

:param my_url: the IP address of the switch
:param my_user: the username to login to the switch
:param my_pass: password
:return: the number of cfg, zone, and alias entries in the zone list.
"""


def brcd_zone_info(my_url, my_user, my_pass):
    with open("brcdConfig.json", "r") as brcdConfig:
        brocade_config = json.load(brcdConfig)
    zone_list = do_command(
        brocade_config["config"]["api_command"],
        my_url,
        my_user=my_user,
        my_pass=my_pass,
        protocol="ssh",
    )
    logger.debug(zone_list)
    cfg_counter = 0
    zone_counter = 0
    alias_counter = 0
    for line in zone_list:
        if "cfg:" in line:
            cfg_counter += 1
        if "zone:" in line:
            zone_counter += 1
        if "alias:" in line:
            alias_counter += 1
    logger.debug(f"{cfg_counter}")
    logger.debug(f"{zone_counter}")
    logger.debug(f"{alias_counter}")
    return cfg_counter, zone_counter, alias_counter


logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.WARNING
)
logger = logging.getLogger(__name__)

if __name__ == "__main__":
    brcd_zone_info()
