#!/usr/local/bin python3.6

try:
    import json
    import logging
    import sys
    import requests
except ImportError:
    print(f"{sys.exc_info()}")

requests.packages.urllib3.disable_warnings()


"""
This function performs an API GET against a URL, with optional key and headers, and
returns the json response

:param my_url: https://my.url.com/api/v1/
:param name: "devices"
:param my_user: The basic authentication username
:param my_pass: "my_password"
:param key: The key is the unique identifier for the object you want to get
:param headers: {'Content-Type': 'application/json'}
:return: The json response returned by API GET
"""


def api_get(my_url, name, my_user, my_pass, key=None, headers=None):
    base_url = my_url
    new_url = base_url + name + "/" + key if key else base_url + name
    logger.debug(f"{new_url}")
    response = requests.get(
        new_url, auth=(my_user, my_pass), headers=headers, verify=False
    )
    logger.debug(f"{response}")
    return json.loads(response.text)


logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.WARNING
)
logger = logging.getLogger(__name__)
