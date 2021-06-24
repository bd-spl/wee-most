
import weechat
import os

def download_location():
    return weechat.config_get_plugin("download_location")

def get_server_config(server_name, key):
    key_prefix = "server." + server_name + "."

    config_key = key_prefix + key
    config_value = weechat.config_get_plugin(key_prefix + key)
    expanded_value = weechat.string_eval_expression(config_value, {}, {}, {})

    return expanded_value

def setup_download_location():
    if not weechat.config_is_set_plugin("download_location"):
        cache_dir = os.environ.get('XDG_CACHE_HOME')
        if not cache_dir:
            cache_dir = '~/.cache'

        weechat.config_set_plugin("download_location", cache_dir + "/wee-matter/downloads")

def setup():
    setup_download_location()
