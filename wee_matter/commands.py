
import weechat

from wee_matter.server import connect_server, disconnect_server

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

def server_connect_command_cb(args):
    return connect_server(args[0])

def server_disconnect_command_cb(args):
    return disconnect_server(args[0])

def server_command_cb(args):
    command, args = args[0], args[1:]

    if command == "add":
        server_add_command_cb(args)
    if command == "connect":
        server_connect_command_cb(args)
    if command == "disconnect":
        server_disconnect_command_cb(args)

    return weechat.WEECHAT_RC_OK

def matter_command_cb(data, buffer, args):
    split_args = list(filter(bool, args.split(" ")))
    command, args = split_args[0], split_args[1:]

    if command == "server":
        server_command_cb(args)

    return weechat.WEECHAT_RC_OK

def setup_commands():
    weechat.hook_command(
         "matter",
         "Mattermost chat protocol command",
         # Synopsis
        (
            "server add <server-name> <hostname> ||"
            "server connect, disconnect <server-name> ||"
        ),
        # Description
        (
            "server: add Matrix servers\n"
            "server: connect, disconnect Matrix servers\n"
        ),
        # Completions
        (
            "server %(matrix_server_commands)|%* ||"
        ),
        "matter_command_cb",
        ""
    )
