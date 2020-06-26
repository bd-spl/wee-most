
import weechat

from wee_matter.server import (connect_server, disconnect_server,
                               get_server_from_buffer)
from wee_matter.room import build_post_from_input_data, find_full_post_id

from wee_matter.http import (run_post_post, run_post_reaction)

server_default_config = {
    "username": "",
    "password": "",
    "port": 443,
    "protocol": "https",
}

def setup_server_config(server_name, key, value, override=False):
    config_key = "server." + server_name + "." + key

    if not weechat.config_is_set_plugin(config_key) or override:
        weechat.config_set_plugin(
            config_key,
            value
        )

def server_add_command_cb(args):
    server_name = args[0]
    server_url = args[1]

    for config, default_value in server_default_config.items():
        setup_server_config(server_name, config, default_value)

    setup_server_config(server_name, "address", server_url)

    weechat.prnt("", "Server added. You should now configure your username and password.")

    return weechat.WEECHAT_RC_OK

def connect_command_cb(args):
    return connect_server(args[0])

def disconnect_command_cb(args):
    return disconnect_server(args[0])

def server_command_cb(args):
    command, args = args[0], args[1:]

    if command == "add":
        server_add_command_cb(args)

    return weechat.WEECHAT_RC_OK

def matter_command_cb(data, buffer, args):
    split_args = list(filter(bool, args.split(" ")))
    command, args = split_args[0], split_args[1:]

    if command == "server":
        server_command_cb(args)
    if command == "connect":
        connect_command_cb(args)
    if command == "disconnect":
        disconnect_command_cb(args)

    return weechat.WEECHAT_RC_OK

def reply_command_cb(data, buffer, args):
    short_post_id, message = args.split(' ', 1)

    post_id = find_full_post_id(buffer, short_post_id)

    post = build_post_from_input_data(buffer, message)
    post = post._replace(parent_id=post_id)

    server = get_server_from_buffer(buffer)

    run_post_post(post, server, "post_post_cb", buffer)

    return weechat.WEECHAT_RC_OK

def react_command_cb(data, buffer, args):
    short_post_id, emoji_name = args.split(' ')
    post_id = find_full_post_id(buffer, short_post_id)

    server = get_server_from_buffer(buffer)
    run_post_reaction(emoji_name, post_id, server, "singularity_cb", buffer)

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
        ),
        # Description
        (
            "server: add Matrix servers\n"
            "connect Matrix servers\n"
            "disconnect Matrix servers\n"
        ),
        # Completions
        (
            "server %(mattermost_server_commands)|%* ||"
            "connect %(mattermost_server_commands)|%* ||"
            "disconnect %(mattermost_server_commands)|%* ||"
        ),
        "matter_command_cb",
        ""
    )

    weechat.hook_command(
        "reply",
        "Reply to a post",
        (
            "<post-id> <message> ||"
        ),
        (
            "Reply to a post"
        ),
        "",
        "reply_command_cb",
        ""
    )

    weechat.hook_command(
        "react",
        "React to a post",
        (
            "<post-id> <emoji-name> ||"
        ),
        (
            "React to a post"
        ),
        "",
        "react_command_cb",
        ""
    )


    weechat.hook_focus("chat", "channel_click_cb", "")

    weechat.hook_completion("irc_channels", "complete channels for mattermost", "channel_completion_cb", "")
    weechat.hook_completion("irc_privates", "complete dms/mpdms for mattermost", "private_completion_cb", "")
    weechat.hook_completion("mattermost_server_commands", "complete server names for mattermost", "server_completion_cb", "")
