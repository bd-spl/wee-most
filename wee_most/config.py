
import weechat
import os
from collections import namedtuple

download_dir = os.environ.get('XDG_DOWNLOAD_DIR')
if not download_dir:
    download_dir = '~/Downloads'

class PluginConfig:
    Setting = namedtuple("Setting", ["name", "default", "description"])

    general_settings = [
        Setting(
            name = 'autoconnect',
            default = '',
            description = 'Comma separated list of server names to automatically connect to at start',
        ),
        Setting(
            name = 'bot_suffix',
            default = ' [BOT]',
            description = 'The suffix for bot names',
        ),
        Setting(
            name = 'channel_loading_indicator',
            default = '…',
            description = 'Indicator for channels being loaded with content',
        ),
        Setting(
            name = 'channel_prefix_direct',
            default = '',
            description = 'The prefix of buffer names for direct messages channels',
        ),
        Setting(
            name = 'channel_prefix_group',
            default = '&',
            description = 'The prefix of buffer names for group channels',
        ),
        Setting(
            name = 'channel_prefix_private',
            default = '%',
            description = 'The prefix of buffer names for private channels',
        ),
        Setting(
            name = 'channel_prefix_public',
            default = '#',
            description = 'The prefix of buffer names for public channels',
        ),
        Setting(
            name = 'color_bot_suffix',
            default = 'darkgray',
            description = 'Color for the bot suffix in message attachments',
        ),
        Setting(
            name = 'color_deleted',
            default = 'red',
            description = 'Color for deleted messages',
        ),
        Setting(
            name = 'color_parent_reply',
            default = 'lightgreen',
            description = 'Color for parent message of a reply',
        ),
        Setting(
            name = 'color_quote',
            default = 'yellow',
            description = 'Color for quoted messages',
        ),
        Setting(
            name = 'color_reaction',
            default = 'darkgray',
            description = 'Color for the messages reactions',
        ),
        Setting(
            name = 'download_location',
            default = download_dir + '/wee-most',
            description = 'Location for storing downloaded files',
        ),
        Setting(
            name = 'group_reactions',
            default = "true",
            description = 'Group reactions by emoji',
        ),
        Setting(
            name = 'reaction_colorize_nick',
            default = "true",
            description = 'Colorize the reaction nick with the user color',
        ),
        Setting(
            name = 'reaction_show_nick',
            default = "false",
            description = 'Display the nick of the user(s) alongside the reaction',
        ),
    ]

    server_settings = [
        Setting(
            name = 'password',
            default = '',
            description = 'Password for authentication to {} server',
        ),
        Setting(
            name = 'url',
            default = '',
            description = 'URL of {} server',
        ),
        Setting(
            name = 'username',
            default = '',
            description = 'Username for authentication to {} server',
        ),
    ]

    def get_value(self, name):
        return weechat.config_get_plugin(name)

    def get_download_location(self):
        return weechat.config_get_plugin("download_location")

    def get_auto_connect_servers(self):
        auto_connect = weechat.config_get_plugin("autoconnect")
        return list(filter(bool, auto_connect.split(",")))

    def get_server_config(self, server_id, name):
        option = "server." + server_id + "." + name
        config_value = weechat.config_get_plugin(option)
        expanded_value = weechat.string_eval_expression(config_value, {}, {}, {})
        return expanded_value

    def is_server_valid(self, server_id):
        test_option = "server." + server_id + ".url"
        return weechat.config_is_set_plugin(test_option)

    def _add_setting(self, s):
        if weechat.config_is_set_plugin(s.name):
            return

        weechat.config_set_plugin(s.name, s.default)
        weechat.config_set_desc_plugin(s.name, '%s (default: "%s")' % (s.description, s.default))

    def add_server_options(self, server_id):
        for s in self.server_settings:
            self._add_setting(self.Setting(
                name = "server." + server_id + "." + s.name,
                default = s.default,
                description = s.description.format(server_id),
                ))

    def setup(self):
        for s in self.general_settings:
            self._add_setting(s)
