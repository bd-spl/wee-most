
import weechat
import os
from typing import NamedTuple

download_dir = os.environ.get('XDG_DOWNLOAD_DIR')
if not download_dir:
    download_dir = '~/Downloads'

Setting = NamedTuple(
        "Setting",
        [
            ("default", str),
            ("desc", str),
        ]
)

general_settings = {
    'autoconnect': Setting(
        default= '',
        desc= 'Comma separated list of server names to automatically connect to at start',
    ),
    'download_location': Setting(
        default= download_dir + '/wee-matter',
        desc= 'Location for storing downloaded files',
    ),
}

server_settings = {
    'address': Setting(
        default= '',
        desc= 'Address of {} server',
    ),
    'password': Setting(
        default= '',
        desc= 'Password for authentication to {} server',
    ),
    'port': Setting(
        default= '443',
        desc= 'Port to use for connection to {} server',
    ),
    'protocol': Setting(
        default= 'https',
        desc= 'Protocol to use for connection to {} server',
    ),
    'username': Setting(
        default= '',
        desc= 'Username for authentication to {} server',
    ),
 }

def download_location():
    return weechat.config_get_plugin("download_location")

def auto_connect_servers():
    auto_connect = weechat.config_get_plugin("autoconnect")
    return list(filter(bool, auto_connect.split(",")))

def get_server_config(server_name, key):
    option = "server." + server_name + "." + key
    config_value = weechat.config_get_plugin(option)
    expanded_value = weechat.string_eval_expression(config_value, {}, {}, {})
    return expanded_value

def add_server_options(server_name, server_url):
    for key, (default, desc) in server_settings.items():
        option = "server." + server_name + "." + key

        if weechat.config_is_set_plugin(option):
            continue

        weechat.config_set_plugin(option, default)
        weechat.config_set_desc_plugin(option, '%s (default: "%s")' % (desc.format(server_name), default))

    weechat.config_set_plugin("server." + server_name + ".address", server_url)

def setup():
    for key, (default, desc) in general_settings.items():
        if weechat.config_is_set_plugin(key):
            continue

        weechat.config_set_plugin(key, default)
        weechat.config_set_desc_plugin(key, '%s (default: "%s")' % (desc, default))
