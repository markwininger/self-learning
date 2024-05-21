#!/usr/local/bin python3.6

try:
    import json
    import logging
    import os
    import re
    import sys

    from brcdZoneInfo import brcd_zone_info
    from doCommand import do_command
    from doPandas import do_pandas
except ImportError:
    print(f"{sys.exc_info()}")


"""
This function takes a URL, username, and password and returns a pandas dataframe with
the switch name, WWN, version, number of online ports, number of ports with no SFP,
number of inactive ports, total number of ports, number of zone configs, total number of
zones, total number of aliases, and uptime

:param my_url: IP address of the switch
:param my_user: username
:param my_pass: password
"""


def brcd_switch_info(my_url, my_user, my_pass):
    with open("brcdConfig.json", "r") as brcdConfig:
        brocade_config = json.load(brcdConfig)

    switch_general = do_command(
        brocade_config["general_info"]["api_command"],
        my_url,
        my_user=my_user,
        my_pass=my_pass,
        protocol="ssh",
    )
    switch_uptime = do_command(
        brocade_config["uptime"]["api_command"],
        my_url,
        my_user=my_user,
        my_pass=my_pass,
        protocol="ssh",
    )
    switch_version = do_command(
        brocade_config["version"]["api_command"],
        my_url,
        my_user=my_user,
        my_pass=my_pass,
        protocol="ssh",
    )
    logger.debug(f"{switch_general}")
    logger.debug(f"{switch_uptime}")
    logger.debug(f"{switch_version}")
    configs, zones, aliases = brcd_zone_info(my_url, my_user, my_pass)
    count = 0
    count_no_sfp = 0
    count_online = 0
    count_inactive = 0
    for line in switch_general:
        if "switchName:" in line:
            switch_name = line.split()[1]
            logger.debug(f"{switch_name}")
        if "switchWwn:" in line:
            wwn = line.split()[1]
            logger.debug(f"{wwn}")
        if re.search(r"\d+\s+\d+\s+\d+(\s+\w+)+", line):
            state = line.split()[6]
            logger.debug(f"{state}")
            count += 1
            if state == brocade_config["port"]["state"]["online"]:
                count_online += 1
            if state == brocade_config["port"]["state"]["no_sfp"]:
                count_no_sfp += 1
            else:
                count_inactive += 1
    for line in switch_version:
        if "Fabric OS:" in line:
            version = line.split()[2]
    for line in switch_uptime:
        uptime = f"{line.split()[2]} {line.split()[3]}"
    table_info = {
        "Switch": [f"{switch_name}"],
        "WWN": [f"{wwn}"],
        "Version": [f"{version}"],
        "Online_Ports": [f"{count_online}"],
        "No_SFP_Ports": [f"{count_no_sfp}"],
        "Inactive_Ports": [f"{count_inactive}"],
        "Total_Ports": [f"{count}"],
        "Zone_Configs": [f"{configs}"],
        "Total_Zones": [f"{zones}"],
        "Total_Aliases": [f"{aliases}"],
        "Uptime": [f"{uptime}"],
    }
    do_pandas(table_info, os.environ["outfile1"])


logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.WARNING
)
logger = logging.getLogger(__name__)


if __name__ == "__main__":
    brcd_switch_info()
