
import weechat
import wee_most
from collections import namedtuple
from functools import wraps
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
        if not buffer_name.startswith("wee-most.") or buffer_type == "server":
            command_name = f.__name__.replace("command_", "", 1)
            weechat.prnt("", 'wee-most: command "{}" must be executed on a Mattermost channel buffer'.format(command_name))
            return weechat.WEECHAT_RC_ERROR

        return f(args, buffer)

    return wrapper


def command_server_add(args, buffer):
    if 1 != len(args.split()):
        write_command_error("server add " + args, "Error with subcommand arguments")
        return weechat.WEECHAT_RC_ERROR

    config.add_server_options(args)

    weechat.prnt(buffer, 'Server "%s" added. You should now configure it.' % args)
    weechat.prnt(buffer, "/set plugins.var.python.wee-most.server.%s.*" % args)

    return weechat.WEECHAT_RC_OK

def command_connect(args, buffer):
    if 1 != len(args.split()):
        write_command_error("connect " + args, "Error with subcommand arguments")
        return weechat.WEECHAT_RC_ERROR
    return wee_most.server.connect_server(args)

def command_disconnect(args, buffer):
    if 1 != len(args.split()):
        write_command_error("disconnect " + args, "Error with subcommand arguments")
        return weechat.WEECHAT_RC_ERROR
    return wee_most.server.disconnect_server(args)

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

    server = wee_most.server.get_server_from_buffer(buffer)
    channel_id = weechat.buffer_get_string(buffer, "localvar_channel_id")

    wee_most.http.run_post_command(channel_id, "/{}".format(args), server, "singularity_cb", buffer)

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

    short_post_id, _, message = args.partition(" ")

    line_data = wee_most.post.find_buffer_last_post_line_data(buffer, short_post_id)
    if not line_data:
        weechat.prnt(buffer, 'Cannot find post id for "%s"' % short_post_id)
        return weechat.WEECHAT_RC_ERROR

    tags = wee_most.post.get_line_data_tags(line_data)

    post_id = wee_most.post.find_reply_to_in_tags(tags)
    if not post_id:
        post_id = wee_most.post.find_post_id_in_tags(tags)

    post = {
        "channel_id": weechat.buffer_get_string(buffer, "localvar_channel_id"),
        "message": message,
        "root_id": post_id,
    }

    server = wee_most.server.get_server_from_buffer(buffer)

    wee_most.http.run_post_post(post, server, "post_post_cb", buffer)

    return weechat.WEECHAT_RC_OK

@mattermost_channel_buffer_required
def command_react(args, buffer):
    if 2 != len(args.split()):
        write_command_error("react " + args, "Error with subcommand arguments")
        return weechat.WEECHAT_RC_ERROR

    short_post_id, _, emoji_name = args.partition(" ")
    post_id = wee_most.post.find_full_post_id(buffer, short_post_id)
    if not post_id:
        weechat.prnt(buffer, 'Cannot find post id for "%s"' % short_post_id)
        return weechat.WEECHAT_RC_ERROR

    server = wee_most.server.get_server_from_buffer(buffer)
    wee_most.http.run_post_reaction(emoji_name, post_id, server, "singularity_cb", buffer)

    return weechat.WEECHAT_RC_OK

@mattermost_channel_buffer_required
def command_unreact(args, buffer):
    if 2 != len(args.split()):
        write_command_error("unreact " + args, "Error with subcommand arguments")
        return weechat.WEECHAT_RC_ERROR

    short_post_id, _, emoji_name = args.partition(" ")
    post_id = find_full_post_id(buffer, short_post_id)
    if not post_id:
        weechat.prnt(buffer, 'Cannot find post id for "%s"' % short_post_id)
        return weechat.WEECHAT_RC_ERROR

    server = wee_most.server.get_server_from_buffer(buffer)
    wee_most.http.run_delete_reaction(emoji_name, post_id, server, "singularity_cb", buffer)

    return weechat.WEECHAT_RC_OK

@mattermost_channel_buffer_required
def command_delete(args, buffer):
    if 1 != len(args.split()):
        write_command_error("delete " + args, "Error with subcommand arguments")
        return weechat.WEECHAT_RC_ERROR

    post_id = wee_most.post.find_full_post_id(buffer, args)
    if not post_id:
        weechat.prnt(buffer, 'Cannot find post id for "%s"' % args)
        return weechat.WEECHAT_RC_ERROR

    server = wee_most.server.get_server_from_buffer(buffer)

    wee_most.http.run_delete_post(post_id, server, "singularity_cb", buffer)

    return weechat.WEECHAT_RC_OK

def write_command_error(args, message):
    buffer = weechat.buffer_search_main()
    weechat.prnt(buffer, message + ' "/mattermost ' + args + '" (help on command: /help mattermost)')

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
