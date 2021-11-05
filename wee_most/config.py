
import weechat
import os
from collections import namedtuple

download_dir = os.environ.get('XDG_DOWNLOAD_DIR')
if not download_dir:
    download_dir = '~/Downloads'

class PluginConfig:
    Setting = namedtuple("Setting", ["name", "default", "description", "type"])

    general_settings = [
        Setting(
            name = 'autoconnect',
            default = '',
            description = 'Comma separated list of server names to automatically connect to at start',
            type = "list",
        ),
        Setting(
            name = 'bot_suffix',
            default = ' [BOT]',
            description = 'The suffix for bot names',
            type = "string",
        ),
        Setting(
            name = 'channel_loading_indicator',
            default = '…',
            description = 'Indicator for channels being loaded with content',
            type = "string",
        ),
        Setting(
            name = 'channel_prefix_direct',
            default = '',
            description = 'The prefix of buffer names for direct messages channels',
            type = "string",
        ),
        Setting(
            name = 'channel_prefix_group',
            default = '&',
            description = 'The prefix of buffer names for group channels',
            type = "string",
        ),
        Setting(
            name = 'channel_prefix_private',
            default = '%',
            description = 'The prefix of buffer names for private channels',
            type = "string",
        ),
        Setting(
            name = 'channel_prefix_public',
            default = '#',
            description = 'The prefix of buffer names for public channels',
            type = "string",
        ),
        Setting(
            name = 'color_bot_suffix',
            default = 'darkgray',
            description = 'Color for the bot suffix in message attachments',
            type = "string",
        ),
        Setting(
            name = 'color_deleted',
            default = 'red',
            description = 'Color for deleted messages',
            type = "string",
        ),
        Setting(
            name = 'color_parent_reply',
            default = 'lightgreen',
            description = 'Color for parent message of a reply',
            type = "string",
        ),
        Setting(
            name = 'color_quote',
            default = 'yellow',
            description = 'Color for quoted messages',
            type = "string",
        ),
        Setting(
            name = 'color_reaction',
            default = 'darkgray',
            description = 'Color for the messages reactions',
            type = "string",
        ),
        Setting(
            name = 'color_reaction_own',
            default = 'gray',
            description = 'Color for the messages reactions you have added',
            type = "string",
        ),
        Setting(
            name = 'download_location',
            default = download_dir + '/wee-most',
            description = 'Location for storing downloaded files',
            type = "string",
        ),
        Setting(
            name = 'reaction_group',
            default = "true",
            description = 'Group reactions by emoji',
            type = "boolean",
        ),
        Setting(
            name = 'reaction_nick_colorize',
            default = "true",
            description = 'Colorize the reaction nick with the user color',
            type = "boolean",
        ),
        Setting(
            name = 'reaction_nick_show',
            default = "false",
            description = 'Display the nick of the user(s) alongside the reaction',
            type = "boolean",
        ),
    ]

    server_settings = [
        Setting(
            name = 'password',
            default = '',
            description = 'Password for authentication to {} server',
            type = "string",
        ),
        Setting(
            name = 'url',
            default = '',
            description = 'URL of {} server',
            type = "string",
        ),
        Setting(
            name = 'username',
            default = '',
            description = 'Username for authentication to {} server',
            type = "string",
        ),
    ]

    def __getattr__(self, key):
        setting = None

        for s in self.general_settings:
            if s.name == key:
                setting = s
                break

        if not setting:
            # return non general setting value
            return weechat.config_get_plugin(key)

        get_func = getattr(self, "_get_" + s.type)
        return get_func(key)

    def _get_boolean(self, key):
        return weechat.config_string_to_boolean(weechat.config_get_plugin(key))

    def _get_string(self, key):
        return weechat.config_get_plugin(key)

    def _get_list(self, key):
        return weechat.config_get_plugin(key).split(",")

    def get_value(self, key):
        return getattr(self, key)

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
