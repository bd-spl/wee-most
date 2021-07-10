
import weechat
import os
from typing import NamedTuple

download_dir = os.environ.get('XDG_DOWNLOAD_DIR')
if not download_dir:
    download_dir = '~/Downloads'

class PluginConfig:
    Setting = NamedTuple(
            "Setting",
            [
                ("key", str),
                ("default", str),
                ("desc", str),
            ]
    )

    general_settings = [
        Setting(
            key= 'autoconnect',
            default= '',
            desc= 'Comma separated list of server names to automatically connect to at start',
        ),
        Setting(
            key= 'download_location',
            default= download_dir + '/wee-matter',
            desc= 'Location for storing downloaded files',
        ),
    ]

    server_settings = [
        Setting(
            key= 'url',
            default= '',
            desc= 'URL of {} server',
        ),
        Setting(
            key= 'password',
            default= '',
            desc= 'Password for authentication to {} server',
        ),
        Setting(
            key= 'username',
            default= '',
            desc= 'Username for authentication to {} server',
        ),
    ]

    def get_download_location(self):
        return weechat.config_get_plugin("download_location")

    def get_auto_connect_servers(self):
        auto_connect = weechat.config_get_plugin("autoconnect")
        return list(filter(bool, auto_connect.split(",")))

    def get_server_config(self, server_name, key):
        option = "server." + server_name + "." + key
        config_value = weechat.config_get_plugin(option)
        expanded_value = weechat.string_eval_expression(config_value, {}, {}, {})
        return expanded_value

    def _add_setting(self, s):
        if weechat.config_is_set_plugin(s.key):
            return

        weechat.config_set_plugin(s.key, s.default)
        weechat.config_set_desc_plugin(s.key, '%s (default: "%s")' % (s.desc, s.default))

    def add_server_options(self, server_name):
        for s in self.server_settings:
            self._add_setting(Setting(
                key= "server." + server_name + "." + s.key,
                default= s.default,
                desc= s.desc.format(server_name),
                ))

    def setup(self):
        for s in self.general_settings:
            self._add_setting(s)
