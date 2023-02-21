#!/usr/local/bin python3.6


try:
    import json
    import logging
    import os
    import re
    import sys

    from brcdInterfaceInfo import brcd_interface_info
    from doCommand import do_command
    from doPandas import do_pandas
except ImportError:
    print(f"{sys.exc_info()}")


"""
It takes a switch IP address, username, and password and returns a pandas dataframe with
the following columns:

:param my_url: the IP address of the switch
:param my_user: username
:param my_pass: the password for the switch
"""


def brcd_crc_info(my_url, my_user, my_pass):
    with open("brcdConfig.json", "r") as brcdConfig:
        brocade_config = json.load(brcdConfig)
    crc_info = do_command(
        brocade_config["port"]["api_command"]["crc_errors"],
        my_url,
        my_user=my_user,
        my_pass=my_pass,
        protocol="ssh",
    )
    logger.debug(f"{crc_info}")
    interface_info = brcd_interface_info(my_url, my_user, my_pass)
    logger.debug(interface_info)
    blade_list = []
    crc_list = []
    port_list = []
    port_index_list = []
    serial_list = []
    for line in crc_info:
        logger.debug(f"{line}")
        if re.search(r"\d\:", line):
            crc = line.split()[4]
            logger.debug(f"{crc}")
            if crc != "0":
                crc_list.append(f"{crc}")
                port_index = line.split()[0].split(":")[0]
                serial = interface_info["Port_Index"][f"{port_index}"]["Serial"]
                port = interface_info["Port_Index"][f"{port_index}"]["Port"]
                blade = interface_info["Port_Index"][f"{port_index}"]["Blade"]
                logger.debug(f"{serial}")
                logger.debug(f"{port}")
                logger.debug(f"{blade}")
                blade_list.append(f"{blade}")
                port_list.append(f"{port}")
                port_index_list.append(f"{port_index}")
                serial_list.append(f"{serial}")
    logger.debug(f"{port_index_list}")
    logger.debug(f"{blade_list}")
    logger.debug(f"{port_list}")
    logger.debug(f"{serial_list}")
    logger.debug(f"{crc_list}")
    table_info = {
        "Switch": f"{my_url}",
        "Port_Index": port_index_list,
        "Blade": blade_list,
        "Port": port_list,
        "Serial": serial_list,
        "CRC Errors": crc_list,
    }
    logger.debug(table_info)
    do_pandas(table_info, os.environ["outfile2"])


logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.WARNING
)
logger = logging.getLogger(__name__)


if __name__ == "__main__":
    brcd_crc_info()
