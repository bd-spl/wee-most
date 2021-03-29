
import weechat
import wee_matter

server_default_config = {
    "username": "",
    "password": "",
    "port": "443",
    "protocol": "https",
}

def setup_server_config(server_name, key, value, override=False):
    config_key = "server." + server_name + "." + key

    if not weechat.config_is_set_plugin(config_key) or override:
        weechat.config_set_plugin(
            config_key,
            value
        )

def server_add_command_usage(buffer):
    weechat.prnt(buffer, "Usage: /matter server add <server-name> <server-domain>")

def server_add_command(args, buffer):
    if 2 != len(args.split()):
        server_add_command_usage(buffer)
        return weechat.WEECHAT_RC_ERROR

    server_name, _, server_url = args.partition(" ")

    for config, default_value in server_default_config.items():
        setup_server_config(server_name, config, default_value)

    setup_server_config(server_name, "address", server_url)

    weechat.prnt(buffer, "Server added. You should now configure your username and password.")
    weechat.prnt(buffer, "/set plugins.var.python.wee-matter.server.%s.*" % server_name)

    return weechat.WEECHAT_RC_OK

def connect_command_usage(buffer):
    weechat.prnt(buffer, "Usage: /matter connect <server-name>")

def connect_command(args, buffer):
    if 1 != len(args.split()):
        connect_command_usage(buffer)
        return weechat.WEECHAT_RC_ERROR
    return wee_matter.server.connect_server(args)

def disconnect_command_usage(buffer):
    weechat.prnt(buffer, "Usage: /matter connect <server-name>")

def disconnect_command(args, buffer):
    if 1 != len(args.split()):
        disconnect_command_usage(buffer)
        return weechat.WEECHAT_RC_ERROR
    return wee_matter.server.disconnect_server(args)

def matter_server_command_usage(buffer):
    weechat.prnt(buffer,
        (
            "Usage: /matter server add <server-name> <server-domain>"
        )
    )

def server_command(args, buffer):
    if 0 == len(args.split()):
        matter_server_command_usage(buffer)
        return weechat.WEECHAT_RC_ERROR

    command, _, args = args.partition(" ")

    if command == "add":
        server_add_command(args, buffer)

    return weechat.WEECHAT_RC_OK

def matter_command_usage(buffer):
    weechat.prnt(buffer,
        (
            "Usage: \n"
            "    /matter server add <server-name> <server-domain>\n"
            "    /matter connect <server-name>\n"
            "    /matter disconnect <server-name>\n"
        )
    )

def matter_command_cb(data, buffer, command):
    if 0 == len(command.split()):
        matter_command_usage(buffer)
        return weechat.WEECHAT_RC_ERROR

    prefix, _, args = command.partition(" ")

    if prefix == "server":
        return server_command(args, buffer)
    if prefix == "connect":
        return connect_command(args, buffer)
    if prefix == "disconnect":
        return disconnect_command(args, buffer)

    # Send a plain mattermost command

    server = wee_matter.server.get_server_from_buffer(buffer)
    channel_id = weechat.buffer_get_string(buffer, "localvar_channel_id")

    wee_matter.http.run_post_command(channel_id, "/{}".format(command), server, "singularity_cb", buffer)

    return weechat.WEECHAT_RC_OK

def reply_command_usage(buffer):
    weechat.prnt(buffer, "Usage: /reply <post-id> <message>")

def reply_command_cb(data, buffer, args):
    if 2 != len(args.split(' ', 1)):
        reply_command_usage(buffer)
        return weechat.WEECHAT_RC_ERROR

    short_post_id, _, message = args.partition(" ")

    line_data = wee_matter.post.find_buffer_last_post_line_data(buffer, short_post_id)
    if not line_data:
        weechat.prnt(buffer, "Can't find post id for \"%s\"" % short_post_id)
        return weechat.WEECHAT_RC_ERROR

    tags = wee_matter.post.get_line_data_tags(line_data)

    post_id = wee_matter.post.find_reply_to_in_tags(tags)
    if not post_id:
        post_id = wee_matter.post.find_post_id_in_tags(tags)

    post = wee_matter.post.build_post_from_input_data(buffer, message)
    post = post._replace(parent_id=post_id)

    server = wee_matter.server.get_server_from_buffer(buffer)

    wee_matter.http.run_post_post(post, server, "post_post_cb", buffer)

    return weechat.WEECHAT_RC_OK

def react_command_usage(buffer):
    weechat.prnt(buffer, "Usage: /react <post-id> <emoji-name>")

def react_command_cb(data, buffer, args):
    if 2 != len(args.split()):
        react_command_usage(buffer)
        return weechat.WEECHAT_RC_ERROR

    short_post_id, _, emoji_name = args.partition(" ")
    post_id = wee_matter.post.find_full_post_id(buffer, short_post_id)
    if not post_id:
        weechat.prnt(buffer, "Can't find post id for \"%s\"" % short_post_id)
        return weechat.WEECHAT_RC_ERROR

    server = wee_matter.server.get_server_from_buffer(buffer)
    wee_matter.http.run_post_reaction(emoji_name, post_id, server, "singularity_cb", buffer)

    return weechat.WEECHAT_RC_OK

def unreact_command_usage(buffer):
    weechat.prnt(buffer, "Usage: /unreact <post-id> <emoji-name>")

def unreact_command_cb(data, buffer, args):
    if 2 != len(args.split()):
        unreact_command_usage(buffer)
        return weechat.WEECHAT_RC_ERROR

    short_post_id, _, emoji_name = args.partition(" ")
    post_id = find_full_post_id(buffer, short_post_id)
    if not post_id:
        weechat.prnt(buffer, "Can't find post id for \"%s\"" % short_post_id)
        return weechat.WEECHAT_RC_ERROR

    server = wee_matter.server.get_server_from_buffer(buffer)
    wee_matter.http.run_delete_reaction(emoji_name, post_id, server, "singularity_cb", buffer)

    return weechat.WEECHAT_RC_OK

def delete_post_command_cb_usage(buffer):
    weechat.prnt(buffer, "Usage: /delete <post-id>")

def delete_post_command_cb(data, buffer, args):
    if 1 != len(args.split()):
        delete_post_command_usage(buffer)
        return weechat.WEECHAT_RC_ERROR

    post_id = wee_matter.post.find_full_post_id(buffer, args)
    if not post_id:
        weechat.prnt(buffer, "Can't find post id for \"%s\"" % args)
        return weechat.WEECHAT_RC_ERROR

    server = wee_matter.server.get_server_from_buffer(buffer)

    wee_matter.http.run_delete_post(post_id, server, "singularity_cb", buffer)

    return weechat.WEECHAT_RC_OK

def setup_commands():
    weechat.hook_command(
        "matter",
        "Mattermost chat protocol command",
         # Synopsis
        (
            "server add <server-name> <hostname> ||"
            "connect <server-name> ||"
            "disconnect <server-name> ||"
            "<mattermost-command>"
        ),
        # Description
        (
            "server: add Matrix servers\n"
            "connect Matrix servers\n"
            "disconnect Matrix servers\n"
            "send a plain mattermost command\n"
        ),
        # Completions
        (
            "server add ||"
            "connect ||"
            "disconnect %(mattermost_server_commands) ||"
        ),
        "matter_command_cb",
        ""
    )

    weechat.hook_command("reply", "Reply to a post", "<post-id> <message>", "Reply to a post", "", "reply_command_cb", "")
    weechat.hook_command("react", "React to a post", "<post-id> <emoji-name>", "React to a post", "", "react_command_cb", "")
    weechat.hook_command("unreact", "Unreact to a post", "<post-id> <emoji-name>", "Unreact to a post", "", "unreact_command_cb", "")
    weechat.hook_command("delete", "Delete a post", "<post-id>", "Delete a post", "", "delete_post_command_cb", "")

    weechat.hook_focus("chat", "channel_click_cb", "")

    weechat.hook_completion("irc_channels", "complete channels for mattermost", "channel_completion_cb", "")
    weechat.hook_completion("irc_privates", "complete dms/mpdms for mattermost", "private_completion_cb", "")
    weechat.hook_completion("mattermost_server_commands", "complete server names for mattermost", "server_completion_cb", "")
