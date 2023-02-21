#!/usr/local/bin python3.6

try:
    import json
    import logging
    import sys

    from doCommand import do_command
except ImportError:
    print(f"{sys.exc_info()}")

"""
This function takes a switch IP, username, and password and returns a dictionary of the
switch's port information

:param my_url: The IP address of the switch
:param my_user: username
:param my_pass: the password for the switch
:return: A dictionary of dictionaries.
"""


def brcd_interface_info(my_url, my_user, my_pass):
    with open("brcdConfig.json", "r") as brcdConfig:
        brocade_config = json.load(brcdConfig)
    port_list = {"Port_Index": {}}
    switch_port_name = do_command(
        brocade_config["port"]["api_command"]["port_id"],
        my_url,
        my_user=my_user,
        my_pass=my_pass,
        protocol="ssh",
    )
    switch_sfp = do_command(
        brocade_config["port"]["api_command"]["sfp_info"],
        my_url,
        my_user=my_user,
        my_pass=my_pass,
        protocol="ssh",
    )
    logger.debug(f"{switch_port_name}")
    logger.debug(f"{switch_sfp}")
    for line in switch_port_name:
        port_name = line.split()[3]
        port_num = line.split()[1].split(":")[0]
        slot_num = line.split()[2].split("t")[1]
        port_list["Port_Index"][f"{port_num}"] = {
            "Blade": f"{slot_num}",
            "Port": f"{port_name}",
        }
        logger.debug(f"{line}")
        logger.debug(f"{port_name}")
        logger.debug(f"{port_num}")
        logger.debug(f"{slot_num}")
        logger.debug(f"{port_list}")
    for line in switch_sfp:
        if "Serial No:" in line:
            slot = line.split()[1].split("/")[0]
            port = line.split()[2]
            serial = line.split()[9]
            temp_slot = f"slot{slot}"
            temp_port = port
            logger.debug(f"{line}")
            logger.debug(f"{slot}")
            logger.debug(f"{port}")
            logger.debug(f"{serial}")
            logger.debug(f"{temp_slot}")
            logger.debug(f"{temp_port}")
            for line in switch_port_name:
                if temp_slot in line and temp_port in line:
                    port_num = line.split()[1].split(":")[0]
                    port_list["Port_Index"][f"{port_num}"].update(
                        {"Serial": f"{serial}"}
                    )
    logger.debug(port_list)
    return port_list


logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.WARNING
)
logger = logging.getLogger(__name__)

if __name__ == "__main__":
    brcd_interface_info()
