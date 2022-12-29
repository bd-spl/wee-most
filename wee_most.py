# Copyright (c) 2022 Damien Tardy-Panis <damien.dev@tardypad.me>
# Released under the GNU GPLv3 license.
# Forked from wee_matter, inspired by wee_slack

import json
import os
import platform
import re
import socket
import subprocess
import time
import urllib.request
import weechat

from collections import namedtuple
from functools import wraps
from ssl import SSLWantReadError
from websocket import (create_connection, WebSocketConnectionClosedException,
                       WebSocketTimeoutException, ABNF)

## config

class PluginConfig:
    Setting = namedtuple("Setting", ["name", "default", "description", "type"])

    general_settings = [
        Setting(
            name = "autoconnect",
            default = "",
            description = "Comma separated list of server names to automatically connect to at start",
            type = "list",
        ),
        Setting(
            name = "bot_suffix",
            default = " [BOT]",
            description = "The suffix for bot names",
            type = "string",
        ),
        Setting(
            name = "buflist_color_away_nick",
            default = "true",
            description = "Use nicklist_away color for direct messages channels name in buflist if user is not online",
            type = "boolean",
        ),
        Setting(
            name = "channel_loading_indicator",
            default = "…",
            description = "Indicator for channels being loaded with content",
            type = "string",
        ),
        Setting(
            name = "channel_prefix_direct_away",
            default = "-",
            description = "The prefix of buffer names for direct messages channels if user status is \"away\"",
            type = "string",
        ),
        Setting(
            name = "channel_prefix_direct_dnd",
            default = "@",
            description = "The prefix of buffer names for direct messages channels if user status is \"do not disturb\"",
            type = "string",
        ),
        Setting(
            name = "channel_prefix_direct_offline",
            default = " ",
            description = "The prefix of buffer names for direct messages channels if user status is \"offline\"",
            type = "string",
        ),
        Setting(
            name = "channel_prefix_direct_online",
            default = "+",
            description = "The prefix of buffer names for direct messages channels if user status is \"online\"",
            type = "string",
        ),
        Setting(
            name = "channel_prefix_group",
            default = "&",
            description = "The prefix of buffer names for group channels",
            type = "string",
        ),
        Setting(
            name = "channel_prefix_private",
            default = "%",
            description = "The prefix of buffer names for private channels",
            type = "string",
        ),
        Setting(
            name = "channel_prefix_public",
            default = "#",
            description = "The prefix of buffer names for public channels",
            type = "string",
        ),
        Setting(
            name = "color_attachment_field",
            default = "default",
            description = "Color for the message attachment fields",
            type = "string",
        ),
        Setting(
            name = "color_attachment_link",
            default = "/gray",
            description = "Color for the message attachment links",
            type = "string",
        ),
        Setting(
            name = "color_attachment_title",
            default = "*",
            description = "Color for the message attachment title",
            type = "string",
        ),
        Setting(
            name = "color_bot_suffix",
            default = "darkgray",
            description = "Color for the bot suffix in message attachments",
            type = "string",
        ),
        Setting(
            name = "color_channel_muted",
            default = "darkgray",
            description = "Color for the muted channels in the buflist",
            type = "string",
        ),
        Setting(
            name = "color_deleted",
            default = "red",
            description = "Color for deleted messages",
            type = "string",
        ),
        Setting(
            name = "color_parent_reply",
            default = "lightgreen",
            description = "Color for parent message of a reply",
            type = "string",
        ),
        Setting(
            name = "color_quote",
            default = "yellow",
            description = "Color for quoted messages",
            type = "string",
        ),
        Setting(
            name = "color_reaction",
            default = "darkgray",
            description = "Color for the messages reactions",
            type = "string",
        ),
        Setting(
            name = "color_reaction_own",
            default = "gray",
            description = "Color for the messages reactions you have added",
            type = "string",
        ),
        Setting(
            name = "download_location",
            default = os.environ.get("XDG_DOWNLOAD_DIR", "~/Downloads") + "/wee_most",
            description = "Location for storing downloaded files",
            type = "string",
        ),
        Setting(
            name = "nick_full_name",
            default = "false",
            description = "Use full name instead of username as nick",
            type = "boolean",
        ),
        Setting(
            name = "reaction_group",
            default = "true",
            description = "Group reactions by emoji",
            type = "boolean",
        ),
        Setting(
            name = "reaction_nick_colorize",
            default = "true",
            description = "Colorize the reaction nick with the user color",
            type = "boolean",
        ),
        Setting(
            name = "reaction_nick_show",
            default = "false",
            description = "Display the nick of the user(s) alongside the reaction",
            type = "boolean",
        ),
    ]

    server_settings = [
        Setting(
            name = "command_2fa",
            default = "",
            description = "Shell command to retrieve the 2FA token",
            type = "string",
        ),
        Setting(
            name = "password",
            default = "",
            description = "Password for authentication to {} server",
            type = "string",
        ),
        Setting(
            name = "url",
            default = "",
            description = "URL of {} server",
            type = "string",
        ),
        Setting(
            name = "username",
            default = "",
            description = "Username for authentication to {} server",
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
        autoconnect = weechat.config_get_plugin(key)
        return list(filter(None, autoconnect.split(",")))

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
                type = "string"
                ))

    def setup(self):
        for s in self.general_settings:
            self._add_setting(s)

## completion

def load_default_emojis():
    emojis_file_path = weechat.info_get("weechat_data_dir", "") + "/wee_most_emojis"
    try:
        with open(emojis_file_path, "r") as emojis_file:
            for emoji in emojis_file:
                default_emojis.append(emoji.rstrip())
    except:
        pass

def channel_completion_cb(data, completion_item, current_buffer, completion):
    for server in servers.values():
        weechat.hook_completion_list_add(completion, server.id, 0, weechat.WEECHAT_LIST_POS_SORT)
        for team in server.teams.values():
            for channel in team.channels.values():
                buffer_name = weechat.buffer_get_string(channel.buffer, "short_name")
                weechat.hook_completion_list_add(completion, buffer_name, 0, weechat.WEECHAT_LIST_POS_SORT)

    return weechat.WEECHAT_RC_OK

def private_completion_cb(data, completion_item, current_buffer, completion):
    for server in servers.values():
        for channel in server.channels.values():
            buffer_name = weechat.buffer_get_string(channel.buffer, "short_name")
            weechat.hook_completion_list_add(completion, buffer_name, 0, weechat.WEECHAT_LIST_POS_SORT)
    return weechat.WEECHAT_RC_OK


def server_completion_cb(data, completion_item, current_buffer, completion):
    for server_id in servers:
        weechat.hook_completion_list_add(completion, server_id, 0, weechat.WEECHAT_LIST_POS_SORT)
    return weechat.WEECHAT_RC_OK

def slash_command_completion_cb(data, completion_item, current_buffer, completion):
    slash_commands = [ "away", "code", "collapse", "dnd", "echo", "expand", "groupmsg", "header",
                       "help", "invite", "invite_people", "join", "kick", "leave", "logout", "me",
                       "msg", "mute", "offline", "online", "purpose", "rename", "search", "settings",
                       "shortcuts", "shrug", "status" ]

    for slash_command in slash_commands:
        weechat.hook_completion_list_add(completion, slash_command, 0, weechat.WEECHAT_LIST_POS_SORT)
    return weechat.WEECHAT_RC_OK

def nick_completion_cb(data, completion_item, current_buffer, completion):
    server = get_server_from_buffer(current_buffer)
    if not server:
        return weechat.WEECHAT_RC_OK

    channel = server.get_channel_from_buffer(current_buffer)
    if not channel:
        return weechat.WEECHAT_RC_OK

    for user in channel.users.values():
        weechat.completion_list_add(completion, user.username, 1, weechat.WEECHAT_LIST_POS_SORT)
        weechat.completion_list_add(completion, "@" + user.username, 1, weechat.WEECHAT_LIST_POS_SORT)

    return weechat.WEECHAT_RC_OK

def emoji_completion_cb(data, completion_item, current_buffer, completion):
    server = get_server_from_buffer(current_buffer)
    if not server:
        return weechat.WEECHAT_RC_OK

    for emoji in default_emojis:
        weechat.completion_list_add(completion, ":" + emoji + ":", 0, weechat.WEECHAT_LIST_POS_SORT)

    for emoji in server.custom_emojis:
        weechat.completion_list_add(completion, ":" + emoji + ":", 0, weechat.WEECHAT_LIST_POS_SORT)

    return weechat.WEECHAT_RC_OK

def mention_completion_cb(data, completion_item, current_buffer, completion):
    server = get_server_from_buffer(current_buffer)
    if not server:
        return weechat.WEECHAT_RC_OK

    for mention in mentions:
        weechat.completion_list_add(completion, mention, 0, weechat.WEECHAT_LIST_POS_SORT)

    return weechat.WEECHAT_RC_OK

def setup_completions():
    weechat.hook_completion("irc_channels", "complete channels for Mattermost", "channel_completion_cb", "")
    weechat.hook_completion("irc_privates", "complete dms/mpdms for Mattermost", "private_completion_cb", "")
    weechat.hook_completion("mattermost_server_commands", "complete server names for Mattermost", "server_completion_cb", "")
    weechat.hook_completion("mattermost_slash_commands", "complete Mattermost slash commands", "slash_command_completion_cb", "")
    weechat.hook_completion("nicks", "complete @-nicks for Mattermost", "nick_completion_cb", "")
    weechat.hook_completion("emojis", "complete :emojis: for Mattermost", "emoji_completion_cb", "")
    weechat.hook_completion("mentions", "complete @-mentions for Mattermost", "mention_completion_cb", "")

## commands

Command = namedtuple("Command", ["name", "args", "description", "completion"])

commands = [
    Command(
        name = "server add",
        args = "<server-name>",
        description = "add a server",
        completion = "",
    ),
    Command(
        name = "connect",
        args = "<server-name>",
        description = "connect to a server",
        completion = "",
    ),
    Command(
        name = "disconnect",
        args = "<server-name>",
        description = "disconnect from a server",
        completion = "%(mattermost_server_commands)",
    ),
    Command(
        name = "slash",
        args = "<mattermost-command>",
        description = "send a plain slash command",
        completion = "%(mattermost_slash_commands)",
    ),
    Command(
        name = "reply",
        args = "<post-id> <message>",
        description = "reply to a post",
        completion = "",
    ),
    Command(
        name = "react",
        args = "<post-id> <emoji-name>",
        description = "react to a post",
        completion = "",
    ),
    Command(
        name = "unreact",
        args = "<post-id> <emoji-name>",
        description = "remove a reaction to a post",
        completion = "",
    ),
    Command(
        name = "delete",
        args = "<post-id>",
        description = "delete a post",
        completion = "",
    ),
]

def mattermost_channel_buffer_required(f):
    @wraps(f)
    def wrapper(args, buffer):
        buffer_name = weechat.buffer_get_string(buffer, "name")
        buffer_type = weechat.buffer_get_string(buffer, "localvar_type")
        if not buffer_name.startswith("wee_most.") or buffer_type == "server":
            command_name = f.__name__.replace("command_", "", 1)
            weechat.prnt("", '{}wee_most: command "{}" must be executed on a Mattermost channel buffer'.format(weechat.prefix("error"), command_name))
            return weechat.WEECHAT_RC_ERROR

        return f(args, buffer)

    return wrapper


def command_server_add(args, buffer):
    if 1 != len(args.split()):
        write_command_error("server add " + args, "Error with subcommand arguments")
        return weechat.WEECHAT_RC_ERROR

    config.add_server_options(args)

    weechat.prnt("", 'Server "%s" added. You should now configure it.' % args)
    weechat.prnt("", "/set plugins.var.python.wee_most.server.%s.*" % args)

    return weechat.WEECHAT_RC_OK

def command_connect(args, buffer):
    if 1 != len(args.split()):
        write_command_error("connect " + args, "Error with subcommand arguments")
        return weechat.WEECHAT_RC_ERROR
    return connect_server(args)

def command_disconnect(args, buffer):
    if 1 != len(args.split()):
        write_command_error("disconnect " + args, "Error with subcommand arguments")
        return weechat.WEECHAT_RC_ERROR
    return disconnect_server(args)

def command_server(args, buffer):
    if 0 == len(args.split()):
        write_command_error("server " + args, "Error with subcommand arguments")
        return weechat.WEECHAT_RC_ERROR

    command, _, args = args.partition(" ")

    if command == "add":
        return command_server_add(args, buffer)

    write_command_error("server " + command + " " + args, "Invalid server subcommand")
    return weechat.WEECHAT_RC_ERROR

@mattermost_channel_buffer_required
def command_slash(args, buffer):
    if 0 == len(args.split()):
        write_command_error("slash " + args, "Error with subcommand arguments")
        return weechat.WEECHAT_RC_ERROR

    server = get_server_from_buffer(buffer)
    channel = server.get_channel_from_buffer(buffer)

    if hasattr(channel, 'team'):
        team_id = channel.team.id
    else:
        team_id = list(server.teams.keys())[0]

    run_post_command(team_id, channel.id, "/{}".format(args), server, "singularity_cb", buffer)

    return weechat.WEECHAT_RC_OK

def mattermost_command_cb(data, buffer, command):
    if 0 == len(command.split()):
        write_command_error("", "Missing subcommand")
        return weechat.WEECHAT_RC_ERROR

    prefix, _, args = command.partition(" ")
    command_function_name = "command_" + prefix

    if command_function_name not in globals():
        write_command_error(command, "Invalid subcommand")
        return weechat.WEECHAT_RC_ERROR

    return globals()[command_function_name](args, buffer)

@mattermost_channel_buffer_required
def command_reply(args, buffer):
    if 2 != len(args.split(" ", 1)):
        write_command_error("reply " + args, "Error with subcommand arguments")
        return weechat.WEECHAT_RC_ERROR

    post_id, _, message = args.partition(" ")

    server = get_server_from_buffer(buffer)

    line_data = find_buffer_last_post_line_data(buffer, post_id)
    if not line_data:
        server.print_error('Cannot find post id for "%s"' % post_id)
        return weechat.WEECHAT_RC_ERROR

    tags = get_line_data_tags(line_data)

    channel = server.get_channel_from_buffer(buffer)
    post = channel.posts[post_id]

    new_post = {
        "channel_id": channel.id,
        "message": message,
        "root_id": post.root_id or post.id,
    }

    run_post_post(new_post, server, "post_post_cb", buffer)

    return weechat.WEECHAT_RC_OK

@mattermost_channel_buffer_required
def command_react(args, buffer):
    if 2 != len(args.split()):
        write_command_error("react " + args, "Error with subcommand arguments")
        return weechat.WEECHAT_RC_ERROR

    post_id, _, emoji_name = args.partition(" ")
    emoji_name = emoji_name.strip(":")

    server = get_server_from_buffer(buffer)

    run_post_reaction(emoji_name, post_id, server, "singularity_cb", buffer)

    return weechat.WEECHAT_RC_OK

@mattermost_channel_buffer_required
def command_unreact(args, buffer):
    if 2 != len(args.split()):
        write_command_error("unreact " + args, "Error with subcommand arguments")
        return weechat.WEECHAT_RC_ERROR

    post_id, _, emoji_name = args.partition(" ")
    emoji_name = emoji_name.strip(":")

    server = get_server_from_buffer(buffer)

    run_delete_reaction(emoji_name, post_id, server, "singularity_cb", buffer)

    return weechat.WEECHAT_RC_OK

@mattermost_channel_buffer_required
def command_delete(args, buffer):
    if 1 != len(args.split()):
        write_command_error("delete " + args, "Error with subcommand arguments")
        return weechat.WEECHAT_RC_ERROR

    server = get_server_from_buffer(buffer)

    run_delete_post(args, server, "singularity_cb", buffer)

    return weechat.WEECHAT_RC_OK

def write_command_error(args, message):
    weechat.prnt("", weechat.prefix("error") + message + ' "/mattermost ' + args + '" (help on command: /help mattermost)')

def setup_commands():
    weechat.hook_command(
        "mattermost",
        "Mattermost commands",
        "||".join([c.name + " " + c.args for c in commands]),
        "\n".join([c.name.rjust(10) + ": " + c.description for c in commands]),
        "||".join([c.name + " " + c.completion for c in commands]),
        "mattermost_command_cb",
        ""
    )

## file

class File:
    def __init__(self, server, **kwargs):
        self.id = kwargs["id"]
        self.name = kwargs["name"]
        self.url = server.url + "/api/v4/files/" + kwargs["id"]

def prepare_download_location(server):
    location = os.path.expanduser(config.download_location)

    if not os.path.exists(location):
        try:
            os.makedirs(location)
        except:
            server.print_error("Failed to create directory at files_download_location: {}".format(location))

    return location

def open_file(file_path):
    if platform.system() == "Darwin":       # macOS
        weechat.hook_process('open "{}"'.format(file_path), 100, "", "")
    elif platform.system() == "Windows":    # Windows
        os.startfile(file_path)
        weechat.hook_process(file_path, 100, "", "")
    else:                                   # linux variants
        weechat.hook_process('xdg-open "{}"'.format(file_path), 100, "", "")

def file_get_cb(data, command, rc, out, err):
    server_id, file_path = data.split("|")
    server = servers[server_id]

    if rc != 0:
        server.print_error("An error occurred while downloading file")
        return weechat.WEECHAT_RC_ERROR

    open_file(file_path)

    return weechat.WEECHAT_RC_OK

def find_file_id_in_tags(tags):
    for tag in tags:
        if tag.startswith("file_id_"):
            return tag[8:]

    return None

## post

class Post:
    def __init__(self, server, **kwargs):
        self.id = kwargs["id"]
        self.root_id = kwargs["root_id"]
        self.channel = server.get_channel(kwargs["channel_id"])
        self.message = kwargs["message"]
        self.type = kwargs["type"]
        self.date = int(kwargs["create_at"]/1000)
        self.read = False

        self.user = server.users[kwargs["user_id"]]

        self.files = []
        if "metadata" in kwargs and "files" in kwargs["metadata"]:
            for file_data in kwargs["metadata"]["files"]:
                self.files.append(File(server, **file_data))

        self.reactions = []
        if "metadata" in kwargs and "reactions" in kwargs["metadata"]:
            for reaction_data in kwargs["metadata"]["reactions"]:
                self.reactions.append(Reaction(server, **reaction_data))

        self.attachments = kwargs["props"].get("attachments", [])
        self.from_bot = kwargs["props"].get("from_bot", False) or kwargs["props"].get("from_webhook", False)
        self.username_override = kwargs["props"].get("override_username")

    def get_last_line_text(self):
        if self.files:
            last_file = self.files[-1]
            return "[{}]({})".format(last_file.name, last_file.url)

        return self.message.split("\n")[-1]

    def add_reaction(self, reaction):
        self.reactions.append(reaction)

    def remove_reaction(self, reaction):
        for i, r in enumerate(self.reactions):
            if r.user == reaction.user and r.emoji_name == reaction.emoji_name:
                del self.reactions[i]

    def get_reactions_line(self):
        if not self.reactions:
            return ""

        my_username = self.channel.server.me.username

        reactions_string = []

        if config.reaction_group:
            reactions_groups = {}
            for r in self.reactions:
                if r.emoji_name in reactions_groups:
                    reactions_groups[r.emoji_name].append(r.user)
                else:
                    reactions_groups[r.emoji_name] = [ r.user ]

            for name, users in reactions_groups.items():
                colorized_name = colorize_sentence(name, config.color_reaction)
                for u in users:
                    if u.username == my_username:
                        colorized_name = colorize_sentence(name, config.color_reaction_own)
                        break

                if config.reaction_nick_show:
                    users_string = []
                    for u in users:
                        user_string = u.nick
                        if config.reaction_nick_colorize:
                            user_string = colorize_sentence(user_string, u.color)
                        users_string.append(user_string)

                    reaction_string = ":{}:({})".format(colorized_name, ",".join(users_string))
                else:
                    reaction_string = ":{}:{}".format(colorized_name, len(users))

                reactions_string.append(reaction_string)

        else:
            for r in self.reactions:
                if r.user.username == my_username:
                    colorized_name = colorize_sentence(r.emoji_name, config.color_reaction_own)
                else:
                    colorized_name = colorize_sentence(r.emoji_name, config.color_reaction)

                if config.reaction_nick_show:
                    user_string = u.nick
                    if config.reaction_nick_colorize:
                        user_string = colorize_sentence(user_string, r.user.color)

                    reaction_string = ":{}:({})".format(colorized_name, user_string)
                else:
                    reaction_string = ":{}:".format(colorized_name)

                reactions_string.append(reaction_string)

        return " [{}]".format(" ".join(reactions_string))

class Reaction:
    def __init__(self, server, **kwargs):
        self.user = server.users[kwargs["user_id"]]
        self.emoji_name = kwargs["emoji_name"]

def post_post_cb(buffer, command, rc, out, err):
    server = get_server_from_buffer(buffer)

    if rc != 0:
        server.print_error("Cannot send post")
        return weechat.WEECHAT_RC_ERROR

    return weechat.WEECHAT_RC_OK

def build_quote_message(message):
    if 69 < len(message):
        message = "%s…" % message[:69].strip()
    return message

def colorize_sentence(sentence, color):
    return "{}{}{}".format(weechat.color(color), sentence, weechat.color("reset"))

def build_nick(user, from_bot, username_override):
    nick_prefix = weechat.config_string(weechat.config_get("weechat.look.nick_prefix"))
    nick_prefix_color_name = weechat.config_string(
        weechat.config_get("weechat.color.chat_nick_prefix")
    )

    nick_suffix = weechat.config_string(weechat.config_get("weechat.look.nick_suffix"))
    nick_suffix_color_name = weechat.config_string(
        weechat.config_get("weechat.color.chat_nick_suffix")
    )

    if username_override:
        nick = username_override
    else:
        nick = user.nick

    nick = colorize_sentence(nick, user.color)

    if from_bot:
        nick += colorize_sentence(config.bot_suffix, config.color_bot_suffix)

    return (
        colorize_sentence(nick_prefix, nick_prefix_color_name)
        + nick
        + colorize_sentence(nick_suffix, nick_suffix_color_name)
    )

def build_message_with_attachments(message, attachments):
    if message:
        msg_parts = [ message ]
    else:
        msg_parts = []

    for attachment in attachments:
        msg_parts.append(build_attachment(attachment))

    return "\n\n".join(msg_parts)

def build_attachment(attachment):
    att = []

    if attachment["pretext"]:
        att.append(attachment["pretext"])

    if attachment["author_name"]:
        att.append(attachment["author_name"])

    title = ""
    # write link as markdown link for later generic formatting
    if attachment["title"] and attachment["title_link"]:
        title = attachment["title"] + " [](" + attachment["title_link"] + ")"
    elif attachment["title"]:
        title = attachment["title"]
    elif attachment["title_link"]:
        title = "[](" + attachment["title_link"] + ")"

    if title:
        att.append(colorize_sentence(format_style(title), config.color_attachment_title))

    if attachment["text"]:
        att.append(attachment["text"])

    if attachment["fields"]:
        for field in attachment["fields"]:
            field_text = ""
            if field["title"] and field["value"]:
                field_text = field["title"] + ": " + field["value"]
            elif field["value"]:
                field_text = field["value"]

            if field_text:
                att.append(colorize_sentence(format_style(field_text), config.color_attachment_field))

    if attachment["footer"]:
        att.append(attachment["footer"])

    return format_markdown_links("\n".join(att))

def format_style(text):
    text = re.sub(
            r"(^| )(?:\*\*\*|___)([^*\n`]+)(?:\*\*\*|___)(?=[^\w]|$)",
            r"\1{}{}\2{}{}".format(
                weechat.color("bold"), weechat.color("italic"), weechat.color("-bold"), weechat.color("-italic")
                ),
            text,
            flags=re.MULTILINE,
            )
    text = re.sub(
            r"(^| )(?:\*\*|__)([^*\n`]+)(?:\*\*|__)(?=[^\w]|$)",
            r"\1{}\2{}".format(
                weechat.color("bold"), weechat.color("-bold")
                ),
            text,
            flags=re.MULTILINE,
            )
    text = re.sub(
            r"(^| )(?:\*|_)([^*\n`]+)(?:\*|_)(?=[^\w]|$)",
            r"\1{}\2{}".format(
                weechat.color("italic"), weechat.color("-italic")
                ),
            text,
            flags=re.MULTILINE,
            )
    return text

def format_markdown_links(text):
    links = []

    def link_repl(match):
        nonlocal links
        text, url = match.groups()
        counter = len(links) + 1
        links.append(colorize_sentence("[{}] {}".format(counter, url), config.color_attachment_link))
        if text:
            return "{} [{}]".format(text, counter)
        return "[{}]".format(counter)

    p = re.compile('\[([^]]*)\]\(([^\)*]*)\)')
    new_text = p.sub(link_repl, text)

    if links:
        return new_text + "\n" + "\n".join(links)

    return new_text

def get_line_data_tags(line_data):
    tags = []

    tags_count = weechat.hdata_integer(weechat.hdata_get("line_data"), line_data, "tags_count")
    for i in range(tags_count):
        tag = weechat.hdata_string(weechat.hdata_get("line_data"), line_data, "{}|tags_array".format(i))
        tags.append(tag)

    return tags

def is_post_line_data(line_data, post_id):
    post_id_tag = "post_id_{}".format(post_id)
    tags = get_line_data_tags(line_data)

    for tag in tags:
        if tag.startswith(post_id_tag):
            return True

def find_buffer_last_post_line_data(buffer, post_id):
    lines = weechat.hdata_pointer(weechat.hdata_get("buffer"), buffer, "lines")
    line = weechat.hdata_pointer(weechat.hdata_get("lines"), lines, "last_line")

    line_data = weechat.hdata_pointer(weechat.hdata_get("line"), line, "data")
    while True:
        if is_post_line_data(line_data, post_id):
            return line_data
        line = weechat.hdata_pointer(weechat.hdata_get("line"), line, "prev_line")
        if "" == line:
            return None
        line_data = weechat.hdata_pointer(weechat.hdata_get("line"), line, "data")

def find_buffer_first_post_line_data(buffer, post_id):
    lines = weechat.hdata_pointer(weechat.hdata_get("buffer"), buffer, "lines")
    line = weechat.hdata_pointer(weechat.hdata_get("lines"), lines, "first_line")

    line_data = weechat.hdata_pointer(weechat.hdata_get("line"), line, "data")
    while True:
        if is_post_line_data(line_data, post_id):
            return line_data
        line = weechat.hdata_pointer(weechat.hdata_get("line"), line, "next_line")
        if "" == line:
            return None
        line_data = weechat.hdata_pointer(weechat.hdata_get("line"), line, "data")

def find_post_id_in_tags(tags):
    for tag in tags:
        if tag.startswith("post_id_"):
            return tag[8:]

    return None

## channel

CHANNEL_TYPES = {
    "D": "direct",
    "G": "group",
    "O": "public", # ordinary
    "P": "private",
}

NICK_GROUPS = {
    "away": "1|Away",
    "dnd": "2|Do not disturb",
    "offline": "3|Offline",
    "online": "0|Online",
    "unknown": "9|Unknown",
}

class ChannelBase:
    def __init__(self, server, **kwargs):
        self.id = kwargs["id"]
        self.type = CHANNEL_TYPES.get(kwargs["type"])
        self.title = kwargs["header"]
        self.server = server
        self.name = self._format_name(kwargs["display_name"], kwargs["name"])
        self.buffer = None
        self.posts = {}
        self.users = {}
        self._is_loading = False
        self._is_muted = None
        self.last_post_id = None
        self.last_read_post_id = None

        self._create_buffer()

    def _create_buffer(self):
        buffer_name = self._format_buffer_name()
        self.buffer = weechat.buffer_new(buffer_name, "channel_input_cb", "", "", "")

        weechat.buffer_set(self.buffer, "short_name", self.name)
        weechat.buffer_set(self.buffer, "title", self.title)

        weechat.buffer_set(self.buffer, "localvar_set_server_id", self.server.id)
        weechat.buffer_set(self.buffer, "localvar_set_channel_id", self.id)
        weechat.buffer_set(self.buffer, "localvar_set_type", "channel")

        weechat.buffer_set(self.buffer, "nicklist", "1")

        weechat.buffer_set(self.buffer, "highlight_words", ",".join(self.server.highlight_words))
        weechat.buffer_set(self.buffer, "localvar_set_nick", self.server.me.nick)

    def _update_buffer_name(self):
        prefix = ""
        if self._is_loading:
            prefix += config.channel_loading_indicator

        color = ""
        if self._is_muted:
            color = weechat.color(config.color_channel_muted)

        weechat.buffer_set(self.buffer, "short_name", color + prefix + self.name)

    def load(self, muted):
        if muted:
            self.mute()
        else:
            self.unmute()

        self.set_loading(True)

        EVENTROUTER.enqueue_request(
            "run_get_read_channel_posts",
            self.id, self.server, "hydrate_channel_read_posts_cb", self.buffer
        )

        EVENTROUTER.enqueue_request(
            "run_get_channel_members",
            self.id, self.server, 0, "hydrate_channel_users_cb", "{}|{}|0".format(self.server.id, self.id)
        )

    def update_post_reactions(self, post_id):
        if post_id not in self.posts:
            return

        line_data = find_buffer_last_post_line_data(self.buffer, post_id)
        if not line_data:
            return

        post = self.posts[post_id]

        new_message = format_style(post.get_last_line_text()) + post.get_reactions_line()
        weechat.hdata_update(weechat.hdata_get("line_data"), line_data, {"message": new_message})

    def remove_post(self, post_id):
        del self.posts[post_id]

        lines = weechat.hdata_pointer(weechat.hdata_get("buffer"), self.buffer, "lines")
        line = weechat.hdata_pointer(weechat.hdata_get("lines"), lines, "last_line")
        line_data = weechat.hdata_pointer(weechat.hdata_get("line"), line, "data")

        # find last line of this post
        while line and not is_post_line_data(line_data, post_id):
            line = weechat.hdata_pointer(weechat.hdata_get("line"), line, "prev_line")
            line_data = weechat.hdata_pointer(weechat.hdata_get("line"), line, "data")

        # find all lines of this post
        pointers = []
        while line and is_post_line_data(line_data, post_id):
            pointers.append(line)
            line = weechat.hdata_pointer(weechat.hdata_get("line"), line, "prev_line")
            line_data = weechat.hdata_pointer(weechat.hdata_get("line"), line, "data")
        pointers.reverse()

        if not pointers:
            return

        lines = [""] * len(pointers)
        lines[0] = colorize_sentence("(deleted)", config.color_deleted)

        for pointer, line in zip(pointers, lines):
            line_data = weechat.hdata_pointer(weechat.hdata_get("line"), pointer, "data")
            weechat.hdata_update(weechat.hdata_get("line_data"), line_data, {"message": line})

    def edit_post(self, post):
        tags = "post_id_%s" % post.id

        first_initial_line_data = find_buffer_first_post_line_data(self.buffer, post.id)
        if not first_initial_line_data:
            return

        initial_tags = get_line_data_tags(first_initial_line_data)
        initial_post_id = find_post_id_in_tags(initial_tags)

        initial_message = weechat.hdata_string(weechat.hdata_get("line_data"), first_initial_line_data, "message")
        initial_message_date = weechat.hdata_time(weechat.hdata_get("line_data"), first_initial_line_data, "date")
        initial_message_prefix = weechat.hdata_string(weechat.hdata_get("line_data"), first_initial_line_data, "prefix")

        full_initial_message = initial_message_prefix + "\t" + colorize_sentence(build_quote_message(format_style(initial_message)), config.color_quote)
        weechat.prnt_date_tags(self.buffer, initial_message_date, "notify_none", full_initial_message)

        new_message = format_style(post.message) + post.get_reactions_line()

        if post.read:
            tags += ",notify_none"

        full_message = build_nick(post.user, post.from_bot, post.username_override) + "\t" + new_message
        weechat.prnt_date_tags(self.buffer, post.date, tags, full_message)

    def write_post(self, post):
        self.posts[post.id] = post

        if post.root_id:
            self._write_reply_message_lines(post)
        else:
            self._write_message_lines(post)

    def _write_reply_message_lines(self, post):
        tags = "post_id_%s" % post.id

        parent_line_data = find_buffer_first_post_line_data(self.buffer, post.root_id)
        if not parent_line_data:
            return

        parent_message = weechat.hdata_string(weechat.hdata_get("line_data"), parent_line_data, "message")
        parent_message_date = weechat.hdata_time(weechat.hdata_get("line_data"), parent_line_data, "date")
        parent_message_prefix = weechat.hdata_string(weechat.hdata_get("line_data"), parent_line_data, "prefix")

        full_parent_message = parent_message_prefix + "\t" + colorize_sentence(build_quote_message(format_style(parent_message)), config.color_parent_reply)
        weechat.prnt_date_tags(self.buffer, parent_message_date, "quote,notify_none", full_parent_message)

        parent_message_prefix = weechat.string_remove_color(parent_message_prefix, "")
        own_prefix = weechat.buffer_get_string(self.buffer, "localvar_nick")

        if post.read:
            tags += ",notify_none"
        elif parent_message_prefix == own_prefix and parent_message_prefix != post.user.nick:
            # if somebody (not us) reply to our post
            tags += ",notify_highlight"
        elif self.type in ['direct', 'group']:
            tags += ",notify_private"
        else:
            tags += ",notify_message"

        if post.message:
            full_message = build_nick(post.user, post.from_bot, post.username_override) + "\t" + format_style(post.message)
            if not post.files:
                full_message += post.get_reactions_line()
            weechat.prnt_date_tags(self.buffer, post.date, tags, full_message)

        self._write_file_lines(post)

        self.last_post_id = post.id

    def _write_message_lines(self, post):
        tags = "post_id_%s" % post.id

        # remove tabs to prevent display issue on multiline messages
        # where the part before the tab would be interpreted as the prefix
        tab_width = weechat.config_integer(weechat.config_get("weechat.look.tab_width"))
        message = post.message.replace("\t", " " * tab_width)

        if post.read:
            tags += ",notify_none"
        elif self.type in ['direct', 'group']:
            tags += ",notify_private"
        else:
            tags += ",notify_message"

        if post.attachments:
            message = build_message_with_attachments(message, post.attachments)

        if post.type in [ "system_join_channel", "system_join_team" ]:
            prefix = weechat.config_string(weechat.config_get("weechat.look.prefix_join"))
            message = "{}{}".format(prefix, message)
        elif post.type in [ "system_leave_channel", "system_leave_team" ]:
            prefix = weechat.config_string(weechat.config_get("weechat.look.prefix_quit"))
            message = "{}{}".format(prefix, message)

        if message:
            full_message = build_nick(post.user, post.from_bot, post.username_override) + "\t" + format_style(message)
            if not post.files:
                full_message += post.get_reactions_line()
            weechat.prnt_date_tags(self.buffer, post.date, tags, full_message)

        self._write_file_lines(post)

        self.last_post_id = post.id

    def _write_file_lines(self, post):
        if not post.files:
            return

        for file in post.files[:-1]:
            weechat.prnt_date_tags(
                self.buffer,
                post.date,
                "post_id_" + post.id + ",file_id_" + file.id,
                "\t[{}]({})".format(file.name, file.url)
            )

        last_file = post.files[-1]
        message = "\t[{}]({})".format(last_file.name, last_file.url) + post.get_reactions_line()

        weechat.prnt_date_tags(
            self.buffer,
            post.date,
            "post_id_" + post.id + ",file_id_" + last_file.id,
            message
        )

    def mark_as_read(self):
        if self.last_post_id and self.last_post_id == self.last_read_post_id: # prevent spamming on buffer switch
            return

        run_post_channel_view(self.id, self.server, "singularity_cb", self.buffer)

        self.last_read_post_id = self.last_post_id

    def add_user(self, user_id):
        if user_id not in self.server.users:
            return

        user = self.server.users[user_id]

        if user.deleted:
            return

        self.users[user_id] = user

        color = ""
        if weechat.config_string_to_boolean(weechat.config_string(weechat.config_get("irc.look.color_nicks_in_nicklist"))):
            color = user.color

        weechat.nicklist_add_nick(self.buffer, "", user.nick, color, "", color, 1)

    def update_nicklist(self):
        for user in self.users.values():
            self.update_nicklist_user(user)

        self.remove_empty_nick_groups()

    def update_nicklist_user(self, user):
        group = self._get_nick_group(user.status)
        color = ""

        nick = weechat.nicklist_search_nick(self.buffer, "", user.nick)
        weechat.nicklist_remove_nick(self.buffer, nick)

        if weechat.config_string_to_boolean(weechat.config_string(weechat.config_get("irc.look.color_nicks_in_nicklist"))):
            if user.status == "online":
                color = user.color
            else:
                color = weechat.config_string(weechat.config_get("weechat.color.nicklist_away"))

        weechat.nicklist_add_nick(self.buffer, group, user.nick, color, "", color, 1)

    def remove_empty_nick_groups(self):
        root = weechat.hdata_pointer(weechat.hdata_get("buffer"), self.buffer, "nicklist_root")
        group = weechat.hdata_pointer(weechat.hdata_get("nick_group"), root, "children")

        while group:
            if not weechat.hdata_pointer(weechat.hdata_get("nick_group"), group, "last_nick"):
                # tried deleting or marking group as not visible via hdata_update but it doesn't seem to work
                name = weechat.hdata_string(weechat.hdata_get("nick_group"), group, "name")
                g = weechat.nicklist_search_group(self.buffer, "", name)
                weechat.nicklist_remove_group(self.buffer, g)

            group = weechat.hdata_pointer(weechat.hdata_get("nick_group"), group, "next_group")

    def set_loading(self, loading):
        self._is_loading = loading
        self._update_buffer_name()

    def is_loading(self):
        return self._is_loading

    def mute(self):
        self._is_muted = True
        self._update_buffer_name()

        weechat.buffer_set(self.buffer, "notify", "1") # highlight only

    def unmute(self):
        self._is_muted = False
        self._update_buffer_name()

        # using "/buffer notify reset" doesn't seem to do the trick
        buffer_full_name = weechat.buffer_get_string(self.buffer, "full_name")
        weechat.command(self.buffer, "/mute /unset weechat.notify.{}".format(buffer_full_name))

    def _get_nick_group(self, status):
        name = NICK_GROUPS.get(status)
        if not name:
            name = NICK_GROUPS.get("unknown")

        group = weechat.nicklist_search_group(self.buffer, "", name)
        if not group:
            group = weechat.nicklist_add_group(self.buffer, "", name, "weechat.color.nicklist_group", 1)

        return group

    def _format_buffer_name(self):
        parent_buffer_name = weechat.buffer_get_string(self.server.buffer, "name")
        # use "!" character so that the buffer gets sorted just after the server buffer and before all teams buffers
        return "{}.!.{}".format(parent_buffer_name[:-1], self.name)

    def _format_name(self, display_name, name):
        final_name = display_name

        name_override = config.get_value("channel." + name);

        if name_override:
            final_name = name_override

        return config.get_value("channel_prefix_" + self.type) + final_name

    def unload(self):
        weechat.buffer_close(self.buffer)

class DirectMessagesChannel(ChannelBase):
    def __init__(self, server, **kwargs):
        super(DirectMessagesChannel, self).__init__(server, **kwargs)
        self.user = self._get_user(kwargs["name"])
        self._status = None

    def set_status(self, status):
        self._status = status
        self._update_buffer_name()

    def _update_buffer_name(self):
        prefix = ""
        if self._is_loading:
            prefix += config.channel_loading_indicator

        if NICK_GROUPS.get(self._status):
            prefix += config.get_value("channel_prefix_direct_" + self._status)
        else:
            prefix += "?"

        color = ""
        if self._is_muted:
            color = weechat.color(config.color_channel_muted)
        if self._status != "online" and config.buflist_color_away_nick:
            color += weechat.color("|" + weechat.config_string(weechat.config_get("weechat.color.nicklist_away")))

        weechat.buffer_set(self.buffer, "short_name", color + prefix + self.name)

    def _format_name(self, display_name, name):
        return self._get_user(name).nick

    def _get_user(self, name):
        match = re.match("(\w+)__(\w+)", name)

        user = self.server.users[match.group(1)]
        if user.username == self.server.me.username:
            user = self.server.users[match.group(2)]

        return user

class GroupChannel(ChannelBase):
    def __init__(self, server, **kwargs):
        super(GroupChannel, self).__init__(server, **kwargs)

class PrivateChannel(ChannelBase):
    def __init__(self, team, **kwargs):
        self.team = team
        super(PrivateChannel, self).__init__(team.server, **kwargs)

    def _format_buffer_name(self):
        parent_buffer_name = weechat.buffer_get_string(self.team.buffer, "name")
        return "{}.{}".format(parent_buffer_name[:-1], self.name)

class PublicChannel(ChannelBase):
    def __init__(self, team, **kwargs):
        self.team = team
        super(PublicChannel, self).__init__(team.server, **kwargs)

    def _format_buffer_name(self):
        parent_buffer_name = weechat.buffer_get_string(self.team.buffer, "name")
        return "{}.{}".format(parent_buffer_name[:-1], self.name)

def channel_input_cb(data, buffer, input_data):
    server = get_server_from_buffer(buffer)

    post = {
        "channel_id": weechat.buffer_get_string(buffer, "localvar_channel_id"),
        "message": input_data,
    }

    run_post_post(post, server, "post_post_cb", buffer)

    return weechat.WEECHAT_RC_OK

def hydrate_channel_posts_cb(buffer, command, rc, out, err):
    server = get_server_from_buffer(buffer)

    if rc != 0:
        server.print_error("An error occurred while hydrating channel")
        return weechat.WEECHAT_RC_ERROR

    channel = server.get_channel_from_buffer(buffer)

    response = json.loads(out)

    response["order"].reverse()
    for post_id in response["order"]:
        builded_post = Post(server, **response["posts"][post_id])
        channel.write_post(builded_post)

    if "" != response["next_post_id"]:
        EVENTROUTER.enqueue_request(
            "run_get_channel_posts_after",
            builded_post.id, builded_post.channel.id, server, "hydrate_channel_posts_cb", buffer
        )
    else:
        channel.set_loading(False)

    return weechat.WEECHAT_RC_OK

def hydrate_channel_read_posts_cb(buffer, command, rc, out, err):
    server = get_server_from_buffer(buffer)

    if rc != 0:
        server.print_error("An error occurred while hydrating channel")
        return weechat.WEECHAT_RC_ERROR

    channel = server.get_channel_from_buffer(buffer)

    response = json.loads(out)

    if not response["order"]:
        return weechat.WEECHAT_RC_OK

    response["order"].reverse()
    for post_id in response["order"]:
        post = Post(server, **response["posts"][post_id])
        post.read = True
        channel.write_post(post)

    channel.last_read_post_id = post.id

    weechat.buffer_set(buffer, "unread", "-")
    weechat.buffer_set(buffer, "hotlist", "-1")

    if "" != response["next_post_id"]:
        EVENTROUTER.enqueue_request(
            "run_get_channel_posts_after",
            post.id, post.channel.id, server, "hydrate_channel_posts_cb", buffer
        )
    else:
        post.channel.set_loading(False)

    return weechat.WEECHAT_RC_OK

def hydrate_channel_users_cb(data, command, rc, out, err):
    server_id, channel_id, page = data.split("|")
    page = int(page)
    server = servers[server_id]
    channel = server.get_channel(channel_id)

    if rc != 0:
        server.print_error("An error occurred while hydrating channel users")
        return weechat.WEECHAT_RC_ERROR

    response = json.loads(out)

    if len(response) == 200:
        EVENTROUTER.enqueue_request(
            "run_get_channel_members",
            channel.id, server, page+1, "hydrate_channel_users_cb", "{}|{}|{}".format(server_id, channel_id, page+1)
        )

    for user_data in response:
        channel.add_user(user_data["user_id"])

    return weechat.WEECHAT_RC_OK

def update_channel_mute_status_cb(data, command, rc, out, err):
    server_id, page = data.split("|")
    page = int(page)
    server = servers[server_id]

    if rc != 0:
        server.print_error("An error occurred while updating channel mute status")
        return weechat.WEECHAT_RC_ERROR

    response = json.loads(out)

    if len(response) == 100:
        EVENTROUTER.enqueue_request(
            "run_get_user_channel_members",
            server, page+1, "update_channel_mute_status_cb", "{}|{}".format(server_id, page+1)
        )

    for member_data in response:
        channel = server.get_channel(member_data["channel_id"])
        if channel:
            muted = member_data["notify_props"]["mark_unread"] != "all"
            channel.load(muted)

    return weechat.WEECHAT_RC_OK

def hydrate_channel_users_status_cb(data, command, rc, out, err):
    server_id, channel_id = data.split("|")
    server = servers[server_id]
    channel = server.get_channel(channel_id)

    if rc != 0:
        server.print_error("An error occurred while hydrating channel users status")
        return weechat.WEECHAT_RC_ERROR

    response = json.loads(out)

    for user_data in response:
        user_id = user_data["user_id"]
        if user_id not in channel.users:
            continue
        user = channel.users[user_id]
        user.status = user_data["status"]

    channel.update_nicklist()

    return weechat.WEECHAT_RC_OK

def update_direct_message_channels_name(server_id, command, rc, out, err):
    server = servers[server_id]

    if rc != 0:
        server.print_error("An error occurred while updating direct message channels name")
        return weechat.WEECHAT_RC_ERROR

    response = json.loads(out)

    for user_data in response:
        channel = server.get_direct_messages_channel(user_data["user_id"])
        if channel:
            channel.set_status(user_data["status"])

    return weechat.WEECHAT_RC_OK

def update_custom_emojis(data, command, rc, out, err):
    server_id, page = data.split("|")
    page = int(page)
    server = servers[server_id]

    if rc != 0:
        server.print_error("An error occurred while updating custom emojis")
        return weechat.WEECHAT_RC_ERROR

    response = json.loads(out)

    for emoji in response:
        server.custom_emojis.append(emoji["name"])

    if len(response) == 150:
        EVENTROUTER.enqueue_request(
            "run_get_custom_emojis",
            server, page+1, "update_custom_emojis", "{}|{}".format(server.id, page+1)
        )

    return weechat.WEECHAT_RC_OK

def remove_channel_user(buffer, user):
    nick = weechat.nicklist_search_nick(buffer, "", user.nick)
    weechat.nicklist_remove_nick(buffer, nick)

def build_channel_name_from_channel_data(channel_data, server):
    channel_name = channel_data["name"]
    if "" != channel_data["display_name"]:
        prefix = config.get_value("channel_prefix_" + CHANNEL_TYPES.get(channel_data["type"]))
        channel_name = prefix + channel_data["display_name"]
    else:
        match = re.match("(\w+)__(\w+)", channel_data["name"])

        if match:
            user = server.users[match.group(1)]
            if user.username == server.me.username:
                user = server.users[match.group(2)]
            channel_name = user.nick

    return channel_name

def create_channel_from_channel_data(channel_data, server):
    if channel_data["type"] == "D":
        if channel_data["last_post_at"] == 0:
            return;

        match = re.match("(\w+)__(\w+)", channel_data["name"])
        if match.group(1) in server.closed_channels or match.group(2) in server.closed_channels:
            return;

        channel = DirectMessagesChannel(server, **channel_data)
        server.channels[channel.id] = channel
    elif channel_data["type"] == "G":
        if channel_data["id"] in server.closed_channels:
            return;

        channel = GroupChannel(server, **channel_data)
        server.channels[channel.id] = channel
    else:
        team = server.teams[channel_data["team_id"]]

        if channel_data["type"] == "P":
            channel = PrivateChannel(team, **channel_data)
        elif channel_data["type"] == "O":
            channel = PublicChannel(team, **channel_data)
        else:
            server.print_error("Unknown channel type " + channel_data["type"])
            channel = PublicChannel(team, **channel_data)

        team.channels[channel.id] = channel

def set_channel_properties_from_channel_data(channel_data, server):
    buffer = server.get_channel(channel_data["id"]).buffer

    channel_name = build_channel_name_from_channel_data(channel_data, server)
    weechat.buffer_set(buffer, "short_name", channel_name)
    weechat.buffer_set(buffer, "title", channel_data["header"])

def buffer_switch_cb(data, signal, buffer):
    for server in servers.values():
        channel = server.get_channel_from_buffer(buffer)
        if channel:
            channel.mark_as_read()
            EVENTROUTER.enqueue_request(
                "run_post_users_status_ids",
                list(channel.users.keys()), server, "hydrate_channel_users_status_cb", "{}|{}".format(server.id, channel.id)
            )
            break

    return weechat.WEECHAT_RC_OK

def chat_line_event_cb(data, signal, hashtable):
    tags = hashtable["_chat_line_tags"].split(",")

    if data == "download":
        file_id = find_file_id_in_tags(tags)
        if not file_id:
            return weechat.WEECHAT_RC_OK
    else:
        post_id = find_post_id_in_tags(tags)
        if not post_id:
            return weechat.WEECHAT_RC_OK

    buffer = hashtable["_buffer"]

    if data == "delete":
        weechat.command(buffer, "/input send /mattermost delete {}".format(post_id))
    elif data == "reply":
        weechat.command(buffer, "/cursor stop")
        weechat.command(buffer, "/input insert /mattermost reply {}\\x20".format(post_id))
    elif data == "react":
        weechat.command(buffer, "/cursor stop")
        weechat.command(buffer, "/input insert /mattermost react {} :".format(post_id))
    elif data == "unreact":
        weechat.command(buffer, "/cursor stop")
        weechat.command(buffer, "/input insert /mattermost unreact {} :".format(post_id))
    elif data == "download":
        server = get_server_from_buffer(buffer)
        file_path = prepare_download_location(server) + "/" + file_id
        if os.path.isfile(file_path):
            open_file(file_path)
        else:
            run_get_file(file_id, file_path, server, "file_get_cb", "{}|{}".format(server.id, file_path))

    return weechat.WEECHAT_RC_OK

def handle_multiline_message_cb(data, modifier, buffer, string):
    for server in servers.values():
        if server.get_channel_from_buffer(buffer):
            if "\n" in string and not string[0] == "/":
                channel_input_cb(data, buffer, string)
                return ""
            return string

    return string

## server

class User:
    def __init__(self, **kwargs):
        self.id = kwargs["id"]
        self.username = kwargs["username"]
        self.first_name = kwargs["first_name"]
        self.last_name = kwargs["last_name"]
        self.status = None
        self.deleted = kwargs["delete_at"] != 0
        self.color = weechat.info_get("nick_color_name", self.username)

    @property
    def nick(self):
        nick = self.username

        if config.nick_full_name and self.first_name and self.last_name:
            nick = "{} {}".format(self.first_name, self.last_name)

        return nick

class Server:
    def __init__(self, id):
        self.id = id

        if not config.is_server_valid(id):
            raise ValueError("Invalid server id " + id)

        self.url = config.get_server_config(id, "url").strip("/")
        self.username = config.get_server_config(id, "username")
        self.password = config.get_server_config(id, "password")
        self.command_2fa = config.get_server_config(id, "command_2fa")

        if not self.url or not self.username or not self.password:
            raise ValueError("Server " + id + " is not fully configured")

        self.token = ""
        self.me = None
        self.highlight_words = []
        self.users = {}
        self.teams = {}
        self.buffer = None
        self.channels = {}
        self.worker = None
        self.reconnection_loop_hook = ""
        self.closed_channels = []
        self.custom_emojis = []

        self._create_buffer()

    def _create_buffer(self):
        # use "*" character so that the buffer is unique and gets sorted before all server buffers
        buffer_name = "wee_most.{}*".format(self.id)
        self.buffer = weechat.buffer_new(buffer_name, "", "", "", "")
        weechat.buffer_set(self.buffer, "short_name", self.id)
        weechat.buffer_set(self.buffer, "localvar_set_server_id", self.id)
        weechat.buffer_set(self.buffer, "localvar_set_type", "server")

        buffer_merge(self.buffer)

    def init_me(self, **kwargs):
        self.me = User(**kwargs)
        self.me.color = weechat.config_string(weechat.config_get("weechat.color.chat_nick_self"))

        if kwargs["notify_props"]["first_name"] == "true":
            self.highlight_words.append(kwargs["first_name"])

        if kwargs["notify_props"]["channel"] == "true":
            self.highlight_words.extend(mentions)

        if kwargs["notify_props"]["mention_keys"]:
            self.highlight_words.extend(kwargs["notify_props"]["mention_keys"].split(","))

    def print(self, message):
        weechat.prnt(self.buffer, message)

    def print_error(self, message):
        weechat.prnt(self.buffer, weechat.prefix("error") + message)

    def get_channel(self, channel_id):
        if channel_id in self.channels:
            return self.channels[channel_id]

        for team in self.teams.values():
            if channel_id in team.channels:
                return team.channels[channel_id]

        return None

    def get_channel_from_buffer(self, buffer):
        channel_id = weechat.buffer_get_string(buffer, "localvar_channel_id")

        if not channel_id:
            return None

        if channel_id in self.channels:
            return self.channels[channel_id]

        for team in self.teams.values():
            if channel_id in team.channels:
                return team.channels[channel_id]

        return None

    def get_direct_messages_channels(self):
        channels = []

        for channel in self.channels.values():
            if isinstance(channel, DirectMessagesChannel):
                channels.append(channel)

        return channels

    def get_direct_messages_channel(self, user_id):
        for channel in self.channels.values():
            if isinstance(channel, DirectMessagesChannel) and channel.user.id == user_id:
                return channel

    def fetch_direct_message_channels_user_status(self):
        user_ids = []

        for channel in self.get_direct_messages_channels():
            user_ids.append(channel.user.id)

        EVENTROUTER.enqueue_request(
            "run_post_users_status_ids",
            user_ids, self, "update_direct_message_channels_name", self.id
        )

    def get_post(self, post_id):
        for channel in self.channels.values():
            if post_id in channel.posts:
                return channel.posts[post_id]

        for team in self.teams.values():
            for channel in team.channels.values():
                if post_id in channel.posts:
                    return channel.posts[post_id]

        return None

    def is_connected(self):
        return self.worker

    def add_team(self, team):
        self.teams[team.id] = team

    def retrieve_2fa_token(self):
        try:
            out = subprocess.check_output(self.command_2fa, shell=True)
        except (subprocess.CalledProcessError):
            self.print_error("Failed to retrieve 2FA token")
            return ""

        return out.decode("utf-8")

    def unload(self):
        self.print("Unloading server")

        servers.pop(self.id)

        if self.worker:
            close_worker(self.worker)
        if self.reconnection_loop_hook:
            weechat.unhook(self.reconnection_loop_hook)

        for channel in self.channels.values():
            channel.unload()
        for team in self.teams.values():
            team.unload()

        weechat.buffer_close(self.buffer)

class Team:
    def __init__(self, server, **kwargs):
        self.server = server
        self.id = kwargs["id"]
        self.name = kwargs["display_name"]
        self.buffer = None
        self.channels = {}

        self._create_buffer()

    def _create_buffer(self):
        parent_buffer_name = weechat.buffer_get_string(self.server.buffer, "name")[:-1]
        # use "*" character so that the buffer is unique and gets sorted before all team buffers
        buffer_name = "{}.{}*".format(parent_buffer_name, self.name)
        self.buffer = weechat.buffer_new(buffer_name, "", "", "", "")

        weechat.buffer_set(self.buffer, "short_name", self.name)
        weechat.buffer_set(self.buffer, "localvar_set_server_id", self.server.id)
        weechat.buffer_set(self.buffer, "localvar_set_type", "server")

        buffer_merge(self.buffer)

    def unload(self):
        for channel in self.channels.values():
            channel.unload()
        weechat.buffer_close(self.buffer)

def buffer_merge(buffer):
    if weechat.config_string(weechat.config_get("irc.look.server_buffer")) == "merge_with_core":
        weechat.buffer_merge(buffer, weechat.buffer_search_main())
    else:
        weechat.buffer_unmerge(buffer, 0)

def config_server_buffer_cb(data, key, value):
    for server in servers.values():
        buffer_merge(server.buffer)
        for team in server.teams.values():
            buffer_merge(team.buffer)
    return weechat.WEECHAT_RC_OK

def get_server_from_buffer(buffer):
    server_id = weechat.buffer_get_string(buffer, "localvar_server_id")

    if not server_id:
        return None

    return servers[server_id]

def get_buffer_user_status_cb(data, remaining_calls):
    buffer = weechat.current_buffer()

    for server in servers.values():
        channel = server.get_channel_from_buffer(buffer)
        if channel:
            EVENTROUTER.enqueue_request(
                "run_post_users_status_ids",
                list(channel.users.keys()), server, "hydrate_channel_users_status_cb", "{}|{}".format(server.id, channel.id)
            )
            break

    return weechat.WEECHAT_RC_OK

def get_direct_message_channels_user_status_cb(data, remaining_calls):
    for server in servers.values():
        server.fetch_direct_message_channels_user_status()

    return weechat.WEECHAT_RC_OK

def connect_server_team_channel(channel_id, server):
    EVENTROUTER.enqueue_request(
        "run_get_channel",
        channel_id, server, "connect_server_team_channel_cb", server.id
    )

def connect_server_team_channel_cb(server_id, command, rc, out, err):
    server = servers[server_id]

    if rc != 0:
        server.print_error("An error occurred while connecting team channel")
        return weechat.WEECHAT_RC_ERROR

    channel_data = json.loads(out)
    create_channel_from_channel_data(channel_data, server)

    return weechat.WEECHAT_RC_OK

def connect_server_team_channels_cb(server_id, command, rc, out, err):
    server = servers[server_id]

    if rc != 0:
        server.print_error("An error occurred while connecting team channels")
        return weechat.WEECHAT_RC_ERROR

    response = json.loads(out)
    for channel_data in response:
        if server.get_channel(channel_data["id"]):
            continue
        create_channel_from_channel_data(channel_data, server)

    server.fetch_direct_message_channels_user_status()

    EVENTROUTER.enqueue_request(
        "run_get_user_channel_members",
        server, 0, "update_channel_mute_status_cb", "{}|0".format(server.id)
    )

    return weechat.WEECHAT_RC_OK

def connect_server_users_cb(data, command, rc, out, err):
    server_id, page = data.split("|")
    page = int(page)
    server = servers[server_id]

    if rc != 0:
        server.print_error("An error occurred while connecting users")
        return weechat.WEECHAT_RC_ERROR

    response = json.loads(out)
    for user in response:
        if user["id"] == server.me.id:
            server.users[user["id"]] = server.me
        else:
            server.users[user["id"]] = User(**user)

    if len(response) == 200:
        EVENTROUTER.enqueue_request(
            "run_get_users",
            server, page+1, "connect_server_users_cb", "{}|{}".format(server.id, page+1)
        )
    else:
        EVENTROUTER.enqueue_request(
            "run_get_user_teams",
            server, "connect_server_teams_cb", server.id
        )

    return weechat.WEECHAT_RC_OK

def connect_server_preferences_cb(server_id, command, rc, out, err):
    server = servers[server_id]

    if rc != 0:
        server.print_error("An error occurred while connecting preferences")
        return weechat.WEECHAT_RC_ERROR

    response = json.loads(out)

    for pref in response:
        if pref["category"] in ["direct_channel_show", "group_channel_show"] and pref["value"] == "false":
            server.closed_channels.append(pref["name"])

    return weechat.WEECHAT_RC_OK

def connect_server_teams_cb(server_id, command, rc, out, err):
    server = servers[server_id]

    if rc != 0:
        server.print_error("An error occurred while connecting teams")
        return weechat.WEECHAT_RC_ERROR

    response = json.loads(out)

    for team_data in response:
        team = Team(server, **team_data)
        server.add_team(team)

        EVENTROUTER.enqueue_request(
            "run_get_user_team_channels",
            team.id, server, "connect_server_team_channels_cb", server.id
        )

    return weechat.WEECHAT_RC_OK

def connect_server_team_cb(server_id, command, rc, out, err):
    server = servers[server_id]

    if rc != 0:
        server.print_error("An error occurred while connecting team")
        return weechat.WEECHAT_RC_ERROR

    team_data = json.loads(out)

    team = Team(server, **team_data)
    server.add_team(team)

    EVENTROUTER.enqueue_request(
        "run_get_user_team_channels",
        team.id, server, "connect_server_team_channels_cb", server.id
    )

    return weechat.WEECHAT_RC_OK

def new_user_cb(server_id, command, rc, out, err):
    server = servers[server_id]

    if rc != 0:
        server.print_error("An error occurred while adding a new user")
        return weechat.WEECHAT_RC_ERROR

    response = json.loads(out)
    server.users[response["id"]] = User(**response)

    return weechat.WEECHAT_RC_OK

def connect_server_cb(server_id, command, rc, out, err):
    server = servers[server_id]

    if rc != 0:
        server.print_error("An error occurred while connecting")
        return weechat.WEECHAT_RC_ERROR

    token_search = re.search("[tT]oken: (\w*)", out)

    out = out.splitlines()[-1] # we remove the headers line
    response = json.loads(out)

    server.token = token_search.group(1)
    server.init_me(**response)

    try:
        worker = Worker(server)
    except:
        server.print_error("An error occurred while creating the websocket worker")
        return weechat.WEECHAT_RC_ERROR

    reconnection_loop_hook = weechat.hook_timer(5 * 1000, 0, 0, "reconnection_loop_cb", server.id)

    server.worker = worker
    server.reconnection_loop_hook = reconnection_loop_hook

    server.print("Connected to " + server_id)

    EVENTROUTER.enqueue_request(
        "run_get_custom_emojis",
        server, 0, "update_custom_emojis", "{}|0".format(server.id)
    )

    EVENTROUTER.enqueue_request(
        "run_get_users",
        server, 0, "connect_server_users_cb", "{}|0".format(server.id)
    )

    EVENTROUTER.enqueue_request(
        "run_get_preferences",
        server, "connect_server_preferences_cb", server.id
    )

    return weechat.WEECHAT_RC_OK

def connect_server(server_id):
    if server_id in servers:
        server = servers[server_id]

        if server != None and server.is_connected():
            server.print_error("Already connected")
            return weechat.WEECHAT_RC_ERROR

        if server != None:
            server.unload()

    try:
        server = Server(server_id)
    except ValueError as ve:
        weechat.prnt("", weechat.prefix("error") + str(ve))
        return weechat.WEECHAT_RC_ERROR

    server.print("Connecting to " + server_id)

    servers[server_id] = server

    EVENTROUTER.enqueue_request(
        "run_user_login",
        server, "connect_server_cb", server.id
    )

    return weechat.WEECHAT_RC_OK

def disconnect_server(server_id):
    server = servers[server_id]

    if not server.is_connected():
        server.print_error("Not connected")
        return weechat.WEECHAT_RC_ERROR

    rc = logout_user(server)

    if rc == weechat.WEECHAT_RC_OK:
        server.unload()

    return rc

def auto_connect():
    for server_id in config.autoconnect:
        connect_server(server_id)

def disconnect_all():
    for server_id in servers.copy():
        disconnect_server(server_id)

## http

def singularity_cb(buffer, command, rc, out, err):
    server = get_server_from_buffer(buffer)

    if rc != 0:
        server.print_error("An error occurred while performing a request")
        return weechat.WEECHAT_RC_ERROR

    return weechat.WEECHAT_RC_OK

def build_buffer_cb_data(url, cb, cb_data):
    return "{}|{}|{}".format(url, cb, cb_data)

class EventRouter:
    def __init__(self):
        self.enqueued_requests = []
        self.response_buffers = {}

    def enqueue_request(self, method, *params):
        self.enqueued_requests.append([method, params])

    def handle_next(self):
        if not self.enqueued_requests:
            return

        request = self.enqueued_requests.pop(0)
        eval(request[0])(*request[1])

    def buffered_response_cb(self, data, command, rc, out, err):
        arg_search = re.search("([^\|]*)\|([^\|]*)\|(.*)", data)
        response_buffer_name = arg_search.group(1)
        real_cb = arg_search.group(2)
        real_data = arg_search.group(3)

        if not response_buffer_name in self.response_buffers:
            self.response_buffers[response_buffer_name] = ""

        if rc == weechat.WEECHAT_HOOK_PROCESS_RUNNING:
            self.response_buffers[response_buffer_name] += out
            return weechat.WEECHAT_RC_OK

        response = self.response_buffers[response_buffer_name] + out
        del self.response_buffers[response_buffer_name]

        return eval(real_cb)(real_data, command, rc, response, err)

def handle_queued_request_cb(data, remaining_calls):
    EVENTROUTER.handle_next()
    return weechat.WEECHAT_RC_OK

def run_get_user_teams(server, cb, cb_data):
    url = server.url + "/api/v4/users/me/teams"
    weechat.hook_process_hashtable(
        "url:" + url,
        {
            "failonerror": "1",
            "httpheader": "Authorization: Bearer " + server.token,
        },
        REQUEST_TIMEOUT_MS,
        "buffered_response_cb",
        build_buffer_cb_data(url, cb, cb_data)
    )

def run_get_team(team_id, server, cb, cb_data):
    url = server.url + "/api/v4/teams/" + team_id
    weechat.hook_process_hashtable(
        "url:" + url,
        {
            "failonerror": "1",
            "httpheader": "Authorization: Bearer " + server.token,
        },
        REQUEST_TIMEOUT_MS,
        "buffered_response_cb",
        build_buffer_cb_data(url, cb, cb_data)
    )

def run_get_users(server, page, cb, cb_data):
    url = server.url + "/api/v4/users?per_page=200&page=" + str(page)
    weechat.hook_process_hashtable(
        "url:" + url,
        {
            "failonerror": "1",
            "httpheader": "Authorization: Bearer " + server.token,
        },
        REQUEST_TIMEOUT_MS,
        "buffered_response_cb",
        build_buffer_cb_data(url, cb, cb_data)
    )

def run_get_user(server, user_id, cb, cb_data):
    url = server.url + "/api/v4/users/" + user_id
    weechat.hook_process_hashtable(
        "url:" + url,
        {
            "failonerror": "1",
            "httpheader": "Authorization: Bearer " + server.token,
        },
        REQUEST_TIMEOUT_MS,
        "buffered_response_cb",
        build_buffer_cb_data(url, cb, cb_data)
    )

def run_get_custom_emojis(server, page, cb, cb_data):
    url = server.url + "/api/v4/emoji?per_page=150&page=" + str(page)
    weechat.hook_process_hashtable(
        "url:" + url,
        {
            "failonerror": "1",
            "httpheader": "Authorization: Bearer " + server.token,
        },
        REQUEST_TIMEOUT_MS,
        "buffered_response_cb",
        build_buffer_cb_data(url, cb, cb_data)
    )

# Logging out synchronously for usage in shutdown function
def logout_user(server):
    url = server.url + "/api/v4/users/logout"
    req = urllib.request.Request(url)
    req.add_header("Authorization", "Bearer " + server.token)

    try:
        urllib.request.urlopen(req, b'', 10 * 1000)
    except:
        server.print_error("An error occurred while disconnecting")
        return weechat.WEECHAT_RC_ERROR

    server.print("Disconnected")
    return weechat.WEECHAT_RC_OK

def run_user_login(server, cb, cb_data):
    url = server.url + "/api/v4/users/login"
    params = {
        "login_id": server.username,
        "password": server.password,
    }

    if server.command_2fa:
        token = server.retrieve_2fa_token()
        if not token:
            return weechat.WEECHAT_RC_ERROR
        params["token"] = token

    weechat.hook_process_hashtable(
        "url:" + url,
        {
            "failonerror": "1",
            "postfields": json.dumps(params),
            "header": "1",
        },
        REQUEST_TIMEOUT_MS,
        "buffered_response_cb",
        build_buffer_cb_data(url, cb, cb_data)
    )

def run_get_channel(channel_id, server, cb, cb_data):
    url = server.url + "/api/v4/channels/" + channel_id
    weechat.hook_process_hashtable(
        "url:" + url,
        {
            "failonerror": "1",
            "httpheader": "Authorization: Bearer " + server.token,
        },
        REQUEST_TIMEOUT_MS,
        "buffered_response_cb",
        build_buffer_cb_data(url, cb, cb_data)
    )

def run_get_user_team_channels(team_id, server, cb, cb_data):
    url = server.url + "/api/v4/users/me/teams/" + team_id + "/channels"
    weechat.hook_process_hashtable(
        "url:" + url,
        {
            "failonerror": "1",
            "httpheader": "Authorization: Bearer " + server.token,
        },
        REQUEST_TIMEOUT_MS,
        "buffered_response_cb",
        build_buffer_cb_data(url, cb, cb_data)
    )

def run_post_post(post, server, cb, cb_data):
    url = server.url + "/api/v4/posts"
    params = {
        "channel_id": post["channel_id"],
        "message": post["message"],
    }

    if "root_id" in post:
        params["root_id"] = post["root_id"]

    weechat.hook_process_hashtable(
        "url:" + url,
        {
            "failonerror": "1",
            "httpheader": "Authorization: Bearer " + server.token,
            "postfields": json.dumps(params),
        },
        REQUEST_TIMEOUT_MS,
        "buffered_response_cb",
        build_buffer_cb_data(url, cb, cb_data)
    )

def run_post_command(team_id, channel_id, command, server, cb, cb_data):
    url = server.url + "/api/v4/commands/execute"
    params = {
        "channel_id": channel_id,
        "team_id": team_id,
        "command": command,
    }

    weechat.hook_process_hashtable(
        "url:" + url,
        {
            "failonerror": "1",
            "httpheader": "Authorization: Bearer " + server.token,
            "postfields": json.dumps(params),
        },
        REQUEST_TIMEOUT_MS,
        "buffered_response_cb",
        build_buffer_cb_data(url, cb, cb_data)
    )

def run_get_read_channel_posts(channel_id, server, cb, cb_data):
    url = server.url + "/api/v4/users/me/channels/" + channel_id + "/posts/unread?limit_after=1"
    weechat.hook_process_hashtable(
        "url:" + url,
        {
            "failonerror": "1",
            "httpheader": "Authorization: Bearer " + server.token,
        },
        REQUEST_TIMEOUT_MS,
        "buffered_response_cb",
        build_buffer_cb_data(url, cb, cb_data)
    )

def run_get_channel_posts_after(post_id, channel_id, server, cb, cb_data):
    url = server.url + "/api/v4/channels/" + channel_id + "/posts?after=" + post_id
    weechat.hook_process_hashtable(
        "url:" + url,
        {
            "failonerror": "1",
            "httpheader": "Authorization: Bearer " + server.token,
        },
        REQUEST_TIMEOUT_MS,
        "buffered_response_cb",
        build_buffer_cb_data(url, cb, cb_data)
    )

def run_get_channel_members(channel_id, server, page, cb, cb_data):
    url = server.url + "/api/v4/channels/" + channel_id + "/members?per_page=200&page=" + str(page)
    weechat.hook_process_hashtable(
        "url:" + url,
        {
            "failonerror": "1",
            "httpheader": "Authorization: Bearer " + server.token,
        },
        REQUEST_TIMEOUT_MS,
        "buffered_response_cb",
        build_buffer_cb_data(url, cb, cb_data)
    )

def run_get_user_channel_members(server, page, cb, cb_data):
    url = server.url + "/api/v4/users/me/channel_members?pageSize=100&page=" + str(page)
    weechat.hook_process_hashtable(
        "url:" + url,
        {
            "failonerror": "1",
            "httpheader": "Authorization: Bearer " + server.token,
        },
        REQUEST_TIMEOUT_MS,
        "buffered_response_cb",
        build_buffer_cb_data(url, cb, cb_data)
    )

def run_post_users_status_ids(user_ids, server, cb, cb_data):
    url = server.url + "/api/v4/users/status/ids"
    weechat.hook_process_hashtable(
        "url:" + url,
        {
            "postfields": json.dumps(user_ids),
            "failonerror": "1",
            "httpheader": "Authorization: Bearer " + server.token,
        },
        REQUEST_TIMEOUT_MS,
        "buffered_response_cb",
        build_buffer_cb_data(url, cb, cb_data)
    )

def run_post_channel_view(channel_id, server, cb, cb_data):
    url = server.url + "/api/v4/channels/members/me/view"
    params = {
        "channel_id": channel_id,
    }

    weechat.hook_process_hashtable(
        "url:" + url,
        {
            "postfields": json.dumps(params),
            "failonerror": "1",
            "httpheader": "Authorization: Bearer " + server.token,
        },
        REQUEST_TIMEOUT_MS,
        "buffered_response_cb",
        build_buffer_cb_data(url, cb, cb_data)
    )

def run_post_reaction(emoji_name, post_id, server, cb, cb_data):
    url = server.url + "/api/v4/reactions"
    params = {
        "user_id": server.me.id,
        "post_id": post_id,
        "emoji_name": emoji_name,
        "create_at": int(time.time()),
    }

    weechat.hook_process_hashtable(
        "url:" + url,
        {
            "postfields": json.dumps(params),
            "failonerror": "1",
            "httpheader": "Authorization: Bearer " + server.token,
        },
        REQUEST_TIMEOUT_MS,
        "buffered_response_cb",
        build_buffer_cb_data(url, cb, cb_data)
    )

def run_delete_reaction(emoji_name, post_id, server, cb, cb_data):
    url = server.url + "/api/v4/users/me/posts/" + post_id + "/reactions/" + emoji_name

    weechat.hook_process_hashtable(
        "url:" + url,
        {
            "customrequest": "DELETE",
            "failonerror": "1",
            "httpheader": "Authorization: Bearer " + server.token,
        },
        REQUEST_TIMEOUT_MS,
        "buffered_response_cb",
        build_buffer_cb_data(url, cb, cb_data)
    )

def run_delete_post(post_id, server, cb, cb_data):
    url = server.url + "/api/v4/posts/" + post_id

    weechat.hook_process_hashtable(
        "url:" + url,
        {
            "customrequest": "DELETE",
            "failonerror": "1",
            "httpheader": "Authorization: Bearer " + server.token,
        },
        REQUEST_TIMEOUT_MS,
        "buffered_response_cb",
        build_buffer_cb_data(url, cb, cb_data)
    )

def run_get_file(file_id, file_out_path, server, cb, cb_data):
    url = server.url + "/api/v4/files/" + file_id

    weechat.hook_process_hashtable(
        "url:" + url,
        {
            "failonerror": "1",
            "file_out": file_out_path,
            "httpheader": "Authorization: Bearer " + server.token,
        },
        REQUEST_TIMEOUT_MS,
        "buffered_response_cb",
        build_buffer_cb_data(url, cb, cb_data)
    )

def run_get_preferences(server, cb, cb_data):
    url = server.url + "/api/v4/users/me/preferences"

    weechat.hook_process_hashtable(
        "url:" + url,
        {
            "failonerror": "1",
            "httpheader": "Authorization: Bearer " + server.token,
        },
        REQUEST_TIMEOUT_MS,
        "buffered_response_cb",
        build_buffer_cb_data(url, cb, cb_data)
    )

## websocket

class Worker:
    def __init__(self, server):
        self.last_ping_time = 0
        self.last_pong_time = 0

        url = server.url.replace("http", "ws", 1) + "/api/v4/websocket"
        self.ws = create_connection(url)
        self.ws.sock.setblocking(0)

        params = {
            "seq": 1,
            "action": "authentication_challenge",
            "data": {
                "token": server.token,
            }
        }

        self.hook_data_read = weechat.hook_fd(self.ws.sock.fileno(), 1, 0, 0, "receive_ws_callback", server.id)
        self.ws.send(json.dumps(params))

        self.hook_ping = weechat.hook_timer(5 * 1000, 0, 0, "ws_ping_cb", server.id)

def rehydrate_server_buffer(server, buffer):
    channel = server.get_channel_from_buffer(buffer)
    if not channel:
        return
    channel.set_loading(True)

    last_post_id = channel.last_post_id

    EVENTROUTER.enqueue_request(
        "run_get_channel_posts_after",
        last_post_id, channel.id, server, "hydrate_channel_posts_cb", buffer
    )

def rehydrate_server_buffers(server):
    server.print("Syncing...")
    for channel in server.channels.values():
        rehydrate_server_buffer(server, channel.buffer)
    for team in server.teams.values():
        for channel in team.channels.values():
            rehydrate_server_buffer(server, channel.buffer)

def reconnection_loop_cb(server_id, remaining_calls):
    server = servers[server_id]
    if server != None and server.is_connected():
        return weechat.WEECHAT_RC_OK

    server.print("Reconnecting...")

    try:
        new_worker = Worker(server)
    except:
        server.print_error("Reconnection issue. Trying again in a few seconds...")
        return weechat.WEECHAT_RC_ERROR

    server.worker = new_worker
    server.print("Reconnected.")
    rehydrate_server_buffers(server)
    return weechat.WEECHAT_RC_OK

def close_worker(worker):
    weechat.unhook(worker.hook_data_read)
    weechat.unhook(worker.hook_ping)
    worker.ws.close()

def handle_lost_connection(server):
    server.print("Connection lost.")
    close_worker(server.worker)
    server.worker = None

def ws_ping_cb(server_id, remaining_calls):
    server = servers[server_id]
    worker = server.worker

    if worker.last_pong_time < worker.last_ping_time:
        handle_lost_connection(server)
        return weechat.WEECHAT_RC_OK

    try:
        worker.ws.ping()
        worker.last_ping_time = time.time()
        server.worker = worker
    except (WebSocketConnectionClosedException, socket.error) as e:
        handle_lost_connection(server)

    return weechat.WEECHAT_RC_OK

def handle_posted_message(server, data, broadcast):
    post = json.loads(data["post"])

    if data["team_id"] and data["team_id"] not in server.teams:
        return

    channel = server.get_channel(broadcast["channel_id"])
    if not channel or channel.is_loading():
        return

    post = Post(server, **post)
    channel.write_post(post)

    if channel.buffer == weechat.current_buffer():
        post.channel.mark_as_read()

def handle_reaction_added_message(server, data, broadcast):
    reaction_data = json.loads(data["reaction"])

    channel = server.get_channel(broadcast["channel_id"])
    if not channel or reaction_data["post_id"] not in channel.posts:
        return

    post = channel.posts[reaction_data["post_id"]]
    post.add_reaction(Reaction(server, **reaction_data))
    channel.update_post_reactions(post.id)

def handle_reaction_removed_message(server, data, broadcast):
    reaction_data = json.loads(data["reaction"])

    channel = server.get_channel(broadcast["channel_id"])
    if not channel or reaction_data["post_id"] not in channel.posts:
        return

    post = channel.posts[reaction_data["post_id"]]
    post.remove_reaction(Reaction(server, **reaction_data))
    channel.update_post_reactions(post.id)

def handle_post_edited_message(server, data, broadcast):
    post_data = json.loads(data["post"])
    post = Post(server, **post_data)
    if server.get_post(post.id) is not None:
        post.channel.edit_post(post)

def handle_post_deleted_message(server, data, broadcast):
    post_data = json.loads(data["post"])
    post = Post(server, **post_data)
    if server.get_post(post.id) is not None:
        post.channel.remove_post(post.id)

def handle_channel_created_message(server, data, broadcast):
    connect_server_team_channel(data["channel_id"], server)

def handle_channel_member_updated_message(server, data, broadcast):
    channel_member_data = json.loads(data["channelMember"])
    if channel_member_data["user_id"] == server.me.id:
        channel = server.get_channel(channel_member_data["channel_id"])
        if channel:
            if channel_member_data["notify_props"]["mark_unread"] == "all":
                channel.unmute()
            else:
                channel.mute()

def handle_channel_updated_message(server, data, broadcast):
    channel_data = json.loads(data["channel"])
    set_channel_properties_from_channel_data(channel_data, server)

def handle_channel_viewed_message(server, data, broadcast):
    channel = server.get_channel(data["channel_id"])

    if channel:
        weechat.buffer_set(channel.buffer, "unread", "-")
        weechat.buffer_set(channel.buffer, "hotlist", "-1")

        channel.last_read_post_id = channel.last_post_id

def handle_user_added_message(server, data, broadcast):
    if data["user_id"] == server.me.id: # we are geing invited
        connect_server_team_channel(broadcast["channel_id"], server)
    else:
        channel = server.get_channel(broadcast["channel_id"])
        channel.add_user(data["user_id"])

def handle_group_added_message(server, data, broadcast):
    connect_server_team_channel(broadcast["channel_id"], server)

def handle_direct_added_message(server, data, broadcast):
    connect_server_team_channel(broadcast["channel_id"], server)

def handle_group_added_message(server, data, broadcast):
    connect_server_team_channel(broadcast["channel_id"], server)

def handle_new_user_message(server, data, broadcast):
    user_id = data["user_id"]
    EVENTROUTER.enqueue_request(
        "run_get_user",
        server, user_id, "new_user_cb", server.id
    )

def handle_user_removed_message(server, data, broadcast):
    if broadcast["channel_id"]:
        user = server.users[data["user_id"]]
        buffer = server.get_channel(broadcast["channel_id"]).buffer
        remove_channel_user(buffer, user)

def handle_added_to_team_message(server, data, broadcast):
    user = server.users[data["user_id"]]

    server.teams[data["team_id"]] = None

    EVENTROUTER.enqueue_request(
        "run_get_team",
        data["team_id"], server, "connect_server_team_cb", server.id
    )

def handle_leave_team_message(server, data, broadcast):
    user = server.users[data["user_id"]]
    team = server.teams.pop(data["team_id"])
    team.unload()

def handle_status_change_message(server, data, broadcast):
    # this event seems only to be triggered on own user
    user_id = data["user_id"]

    if user_id not in server.users:
        return

    user = server.users[user_id]
    user.status = data["status"]

    buffer = weechat.current_buffer()
    channel = server.get_channel_from_buffer(buffer)
    if channel and user_id in channel.users:
        channel.update_nicklist_user(user)
        channel.remove_empty_nick_groups()

    user_dm_channel = server.get_direct_messages_channel(user.id)
    if user_dm_channel:
        user_dm_channel.set_status(user.status)

def receive_ws_callback(server_id, data):
    server = servers[server_id]
    worker = server.worker

    while True:
        try:
            opcode, data = worker.ws.recv_data(control_frame=True)
        except SSLWantReadError:
            return weechat.WEECHAT_RC_OK
        except (WebSocketConnectionClosedException, socket.error) as e:
            return weechat.WEECHAT_RC_OK

        if opcode == ABNF.OPCODE_PONG:
            worker.last_pong_time = time.time()
            server.worker = worker
            return weechat.WEECHAT_RC_OK

        if data:
            message = json.loads(data.decode("utf-8"))
            if "event" in message:
                handler_function_name = "handle_" + message["event"] + "_message"
                if handler_function_name not in globals():
                    return weechat.WEECHAT_RC_OK
                globals()[handler_function_name](server, message["data"], message["broadcast"])

    return weechat.WEECHAT_RC_OK

## globals

EVENTROUTER = EventRouter()

buffered_response_cb = EVENTROUTER.buffered_response_cb

config = PluginConfig()

servers = {}

default_emojis = []

REQUEST_TIMEOUT_MS = 30 * 1000

mentions = ["@here", "@channel", "@all"]

## main

WEECHAT_SCRIPT_NAME = "wee_most"
WEECHAT_SCRIPT_DESCRIPTION = "Mattermost integration"
WEECHAT_SCRIPT_AUTHOR = "Damien Tardy-Panis <damien.dev@tardypad.me>"
WEECHAT_SCRIPT_VERSION = "0.2.0"
WEECHAT_SCRIPT_LICENSE = "GPL3"

weechat.register(
    WEECHAT_SCRIPT_NAME,
    WEECHAT_SCRIPT_AUTHOR,
    WEECHAT_SCRIPT_VERSION,
    WEECHAT_SCRIPT_LICENSE,
    WEECHAT_SCRIPT_DESCRIPTION,
    "shutdown_cb",
    ""
)

setup_commands()
load_default_emojis()
setup_completions()
config.setup()

if weechat.info_get("auto_connect", "") == '1':
    auto_connect()

weechat.hook_modifier("input_text_for_buffer", "handle_multiline_message_cb", "")
weechat.hook_signal("buffer_switch", "buffer_switch_cb", "")
weechat.hook_timer(int(0.2 * 1000), 0, 0, "handle_queued_request_cb", "")
weechat.hook_timer(60 * 1000, 0, 0, "get_buffer_user_status_cb", "")
weechat.hook_timer(60 * 1000, 0, 0, "get_direct_message_channels_user_status_cb", "")
weechat.hook_config("irc.look.server_buffer", "config_server_buffer_cb", "")

weechat.hook_hsignal("mattermost_cursor_delete", "chat_line_event_cb", "delete")
weechat.hook_hsignal("mattermost_cursor_reply", "chat_line_event_cb", "reply")
weechat.hook_hsignal("mattermost_cursor_react", "chat_line_event_cb", "react")
weechat.hook_hsignal("mattermost_cursor_unreact", "chat_line_event_cb", "unreact")
weechat.hook_hsignal("mattermost_cursor_download", "chat_line_event_cb", "download")

def shutdown_cb():
    disconnect_all()

    return weechat.WEECHAT_RC_OK
