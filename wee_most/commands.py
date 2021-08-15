
import weechat
import wee_most
from wee_most.globals import config

def server_add_command_usage(buffer):
    weechat.prnt(buffer, "Usage: /mattermost server add <server-name>")

def server_add_command(args, buffer):
    if 1 != len(args.split()):
        server_add_command_usage(buffer)
        return weechat.WEECHAT_RC_ERROR

    config.add_server_options(args)

    weechat.prnt(buffer, "Server \"%s\" added. You should now configure it." % args)
    weechat.prnt(buffer, "/set plugins.var.python.wee-most.server.%s.*" % args)

    return weechat.WEECHAT_RC_OK

def connect_command_usage(buffer):
    weechat.prnt(buffer, "Usage: /mattermost connect <server-name>")

def connect_command(args, buffer):
    if 1 != len(args.split()):
        connect_command_usage(buffer)
        return weechat.WEECHAT_RC_ERROR
    return wee_most.server.connect_server(args)

def disconnect_command_usage(buffer):
    weechat.prnt(buffer, "Usage: /mattermost connect <server-name>")

def disconnect_command(args, buffer):
    if 1 != len(args.split()):
        disconnect_command_usage(buffer)
        return weechat.WEECHAT_RC_ERROR
    return wee_most.server.disconnect_server(args)

def mattermost_server_command_usage(buffer):
    weechat.prnt(buffer,
        (
            "Usage: /mattermost server add <server-name>"
        )
    )

def server_command(args, buffer):
    if 0 == len(args.split()):
        mattermost_server_command_usage(buffer)
        return weechat.WEECHAT_RC_ERROR

    command, _, args = args.partition(" ")

    if command == "add":
        server_add_command(args, buffer)

    return weechat.WEECHAT_RC_OK

def slash_command(args, buffer):
    server = wee_most.server.get_server_from_buffer(buffer)
    channel_id = weechat.buffer_get_string(buffer, "localvar_channel_id")

    wee_most.http.run_post_command(channel_id, "/{}".format(args), server, "singularity_cb", buffer)

    return weechat.WEECHAT_RC_OK

def mattermost_command_usage(buffer):
    weechat.prnt(buffer,
        (
            "Usage: \n"
            "    /mattermost server add <server-name>\n"
            "    /mattermost connect <server-name>\n"
            "    /mattermost disconnect <server-name>\n"
            "    /mattermost command <mattermost-command>\n"
            "    /mattermost reply <post-id> <message>\n"
            "    /mattermost react <post-id> <emoji-name>\n"
            "    /mattermost unreact <post-id> <emoji-name>\n"
            "    /mattermost delete <post-id>\n"
        )
    )

def mattermost_command_cb(data, buffer, command):
    if 0 == len(command.split()):
        mattermost_command_usage(buffer)
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

    return weechat.WEECHAT_RC_ERROR

def reply_command_usage(buffer):
    weechat.prnt(buffer, "Usage: /reply <post-id> <message>")

def reply_command(args, buffer):
    if 2 != len(args.split(' ', 1)):
        reply_command_usage(buffer)
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

def react_command_usage(buffer):
    weechat.prnt(buffer, "Usage: /react <post-id> <emoji-name>")

def react_command(args, buffer):
    if 2 != len(args.split()):
        react_command_usage(buffer)
        return weechat.WEECHAT_RC_ERROR

    short_post_id, _, emoji_name = args.partition(" ")
    post_id = wee_most.post.find_full_post_id(buffer, short_post_id)
    if not post_id:
        weechat.prnt(buffer, "Can't find post id for \"%s\"" % short_post_id)
        return weechat.WEECHAT_RC_ERROR

    server = wee_most.server.get_server_from_buffer(buffer)
    wee_most.http.run_post_reaction(emoji_name, post_id, server, "singularity_cb", buffer)

    return weechat.WEECHAT_RC_OK

def unreact_command_usage(buffer):
    weechat.prnt(buffer, "Usage: /unreact <post-id> <emoji-name>")

def unreact_command(args, buffer):
    if 2 != len(args.split()):
        unreact_command_usage(buffer)
        return weechat.WEECHAT_RC_ERROR

    short_post_id, _, emoji_name = args.partition(" ")
    post_id = find_full_post_id(buffer, short_post_id)
    if not post_id:
        weechat.prnt(buffer, "Can't find post id for \"%s\"" % short_post_id)
        return weechat.WEECHAT_RC_ERROR

    server = wee_most.server.get_server_from_buffer(buffer)
    wee_most.http.run_delete_reaction(emoji_name, post_id, server, "singularity_cb", buffer)

    return weechat.WEECHAT_RC_OK

def delete_post_command_usage(buffer):
    weechat.prnt(buffer, "Usage: /delete <post-id>")

def delete_post_command(args, buffer):
    if 1 != len(args.split()):
        delete_post_command_usage(buffer)
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

def setup_commands():
    weechat.hook_command(
        "mattermost",
        "Mattermost chat protocol command",
         # Synopsis
        (
            "server add <server-name> ||"
            "connect <server-name> ||"
            "disconnect <server-name> ||"
            "<mattermost-command> ||"
            "reply <post-id> <message> ||"
            "react <post-id> <emoji-name> ||"
            "unreact <post-id> <emoji-name>  ||"
            "delete <post-id>"
        ),
        # Description
        (
            "server: add Mattermost servers\n"
            "connect Mattermost servers\n"
            "disconnect Mattermost servers\n"
            "send a plain Mattermost command\n"
            "reply to a post\n"
            "react to a post\n"
            "unreact to a post\n"
            "delete a post\n"
        ),
        # Completions
        (
            "server add ||"
            "connect ||"
            "disconnect %(mattermost_server_commands) ||"
            "command %(mattermost_slash_commands) ||"
            "reply ||"
            "react ||"
            "unreact ||"
            "delete"
        ),
        "mattermost_command_cb",
        ""
    )

    weechat.hook_focus("chat", "channel_click_cb", "")

    weechat.hook_completion("irc_channels", "complete channels for Mattermost", "channel_completion_cb", "")
    weechat.hook_completion("irc_privates", "complete dms/mpdms for Mattermost", "private_completion_cb", "")
    weechat.hook_completion("mattermost_server_commands", "complete server names for Mattermost", "server_completion_cb", "")
    weechat.hook_completion("mattermost_slash_commands", "complete Mattermost slash commands", "slash_command_completion_cb", "")
