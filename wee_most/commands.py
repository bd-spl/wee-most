
import weechat
import wee_most
from collections import namedtuple
from wee_most.globals import config

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
        name = "command",
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

def server_add_command(args, buffer):
    if 1 != len(args.split()):
        write_command_error(buffer, "server add " + args, "Error with subcommand arguments")
        return weechat.WEECHAT_RC_ERROR

    config.add_server_options(args)

    weechat.prnt(buffer, "Server \"%s\" added. You should now configure it." % args)
    weechat.prnt(buffer, "/set plugins.var.python.wee-most.server.%s.*" % args)

    return weechat.WEECHAT_RC_OK

def connect_command(args, buffer):
    if 1 != len(args.split()):
        write_command_error(buffer, "connect " + args, "Error with subcommand arguments")
        return weechat.WEECHAT_RC_ERROR
    return wee_most.server.connect_server(args)

def disconnect_command(args, buffer):
    if 1 != len(args.split()):
        write_command_error(buffer, "disconnect " + args, "Error with subcommand arguments")
        return weechat.WEECHAT_RC_ERROR
    return wee_most.server.disconnect_server(args)

def server_command(args, buffer):
    if 0 == len(args.split()):
        write_command_error(buffer, "server " + args, "Error with subcommand arguments")
        return weechat.WEECHAT_RC_ERROR

    command, _, args = args.partition(" ")

    if command == "add":
        return server_add_command(args, buffer)

    write_command_error(buffer, "server " + command + " " + args, "Invalid server subcommand")
    return weechat.WEECHAT_RC_ERROR

def slash_command(args, buffer):
    if 0 == len(args.split()):
        write_command_error(buffer, "command " + args, "Error with subcommand arguments")
        return weechat.WEECHAT_RC_ERROR

    server = wee_most.server.get_server_from_buffer(buffer)
    channel_id = weechat.buffer_get_string(buffer, "localvar_channel_id")

    wee_most.http.run_post_command(channel_id, "/{}".format(args), server, "singularity_cb", buffer)

    return weechat.WEECHAT_RC_OK

def mattermost_command_cb(data, buffer, command):
    if 0 == len(command.split()):
        write_command_error(buffer, "", "Missing subcommand")
        return weechat.WEECHAT_RC_ERROR

    prefix, _, args = command.partition(" ")

    if prefix == "server":
        return server_command(args, buffer)
    if prefix == "connect":
        return connect_command(args, buffer)
    if prefix == "disconnect":
        return disconnect_command(args, buffer)
    if prefix == "command":
        return slash_command(args, buffer)
    if prefix == "reply":
        return reply_command(args, buffer)
    if prefix == "react":
        return react_command(args, buffer)
    if prefix == "unreact":
        return unreact_command(args, buffer)
    if prefix == "delete":
        return delete_command(args, buffer)

    write_command_error(buffer, command, "Invalid subcommand")
    return weechat.WEECHAT_RC_ERROR

def reply_command(args, buffer):
    if 2 != len(args.split(' ', 1)):
        write_command_error(buffer, "reply " + args, "Error with subcommand arguments")
        return weechat.WEECHAT_RC_ERROR

    short_post_id, _, message = args.partition(" ")

    line_data = wee_most.post.find_buffer_last_post_line_data(buffer, short_post_id)
    if not line_data:
        weechat.prnt(buffer, "Can't find post id for \"%s\"" % short_post_id)
        return weechat.WEECHAT_RC_ERROR

    tags = wee_most.post.get_line_data_tags(line_data)

    post_id = wee_most.post.find_reply_to_in_tags(tags)
    if not post_id:
        post_id = wee_most.post.find_post_id_in_tags(tags)

    post = {
        'channel_id': weechat.buffer_get_string(buffer, "localvar_channel_id"),
        'message': message,
        'parent_id': post_id,
    }

    server = wee_most.server.get_server_from_buffer(buffer)

    wee_most.http.run_post_post(post, server, "post_post_cb", buffer)

    return weechat.WEECHAT_RC_OK

def react_command(args, buffer):
    if 2 != len(args.split()):
        write_command_error(buffer, "react " + args, "Error with subcommand arguments")
        return weechat.WEECHAT_RC_ERROR

    short_post_id, _, emoji_name = args.partition(" ")
    post_id = wee_most.post.find_full_post_id(buffer, short_post_id)
    if not post_id:
        weechat.prnt(buffer, "Can't find post id for \"%s\"" % short_post_id)
        return weechat.WEECHAT_RC_ERROR

    server = wee_most.server.get_server_from_buffer(buffer)
    wee_most.http.run_post_reaction(emoji_name, post_id, server, "singularity_cb", buffer)

    return weechat.WEECHAT_RC_OK

def unreact_command(args, buffer):
    if 2 != len(args.split()):
        write_command_error(buffer, "unreact " + args, "Error with subcommand arguments")
        return weechat.WEECHAT_RC_ERROR

    short_post_id, _, emoji_name = args.partition(" ")
    post_id = find_full_post_id(buffer, short_post_id)
    if not post_id:
        weechat.prnt(buffer, "Can't find post id for \"%s\"" % short_post_id)
        return weechat.WEECHAT_RC_ERROR

    server = wee_most.server.get_server_from_buffer(buffer)
    wee_most.http.run_delete_reaction(emoji_name, post_id, server, "singularity_cb", buffer)

    return weechat.WEECHAT_RC_OK

def delete_post_command(args, buffer):
    if 1 != len(args.split()):
        write_command_error(buffer, "delete " + args, "Error with subcommand arguments")
        return weechat.WEECHAT_RC_ERROR

    post_id = wee_most.post.find_full_post_id(buffer, args)
    if not post_id:
        weechat.prnt(buffer, "Can't find post id for \"%s\"" % args)
        return weechat.WEECHAT_RC_ERROR

    server = wee_most.server.get_server_from_buffer(buffer)

    wee_most.http.run_delete_post(post_id, server, "singularity_cb", buffer)

    return weechat.WEECHAT_RC_OK

def slash_command_completion_cb(data, completion_item, current_buffer, completion):
    slash_commands = ["away", "code", "collapse", "dnd", "echo", "expand", "groupmsg", "header", "help", "invite", "invite_people", "join", "kick", "leave", "logout", "me", "msg", "mute", "offline", "online", "purpose", "rename", "search", "settings", "shortcuts", "shrug", "status"]

    for slash_command in slash_commands:
        weechat.hook_completion_list_add(completion, slash_command, 0, weechat.WEECHAT_LIST_POS_SORT)
    return weechat.WEECHAT_RC_OK

def write_command_error(buffer, args, message):
    weechat.prnt(buffer, message + " \"/mattermost " + args + "\" (help on command: /help mattermost)")

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

    weechat.hook_focus("chat", "channel_click_cb", "")

    weechat.hook_completion("irc_channels", "complete channels for Mattermost", "channel_completion_cb", "")
    weechat.hook_completion("irc_privates", "complete dms/mpdms for Mattermost", "private_completion_cb", "")
    weechat.hook_completion("mattermost_server_commands", "complete server names for Mattermost", "server_completion_cb", "")
    weechat.hook_completion("mattermost_slash_commands", "complete Mattermost slash commands", "slash_command_completion_cb", "")
