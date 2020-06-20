
import weechat
from typing import NamedTuple
import json
import re

servers = {}

Token = NamedTuple(
    "Token",
    [
        ("value", str)
    ]
)

Server = NamedTuple(
    "Server",
    [
        ("host", str),
        ("protocol", str),
        ("path", str),
        ("username", str),
        ("password", str),
        ("token", str)
    ],
)

def server_root_url(server: Server):
    return server.protocol + "://" + server.host + server.path

def get_server_config(server_name, key):
    key_prefix = "server." + server_name + "."
    return weechat.config_get_plugin(key_prefix + key)

def pop_server(server_name):
    if server_name not in servers:
        weechat.prnt("", "Server is not loaded")
        return

    return servers.pop(server_name)

def get_server(server_name):
    if server_name not in servers:
        weechat.prnt("", "Server is not loaded")
        return

    return servers[server_name]

def load_server(server_name):
    if server_name in servers:
        return servers[server_name]

    servers[server_name] = Server(
        host= get_server_config(server_name, "address"),
        protocol= "https",
        path= "",
        username= get_server_config(server_name, "username"),
        password= get_server_config(server_name, "password"),
        token= "",
    )

    return servers[server_name]

def is_connected(server: Server):
    return server.token != ""

def connect_server_cb(server_name, command, rc, out, err):
    search = re.search('token: (.*)', out)
    if None == search:
        return weechat.WEECHAT_RC_ERROR
    token = search.group(1)

    server = get_server(server_name)
    server = server._replace(token=token)
    servers[server_name] = server

    return weechat.WEECHAT_RC_OK

def connect_server(server_name):
    server = load_server(server_name)

    if is_connected(server):
        weechat.prnt("", "Already connected")
        return weechat.WEECHAT_RC_ERROR

    url = server_root_url(server) + "/api/v4/users/login"
    params = {
        "login_id": server.username,
        "password": server.password,
    }

    weechat.hook_process_hashtable(
        "url:" + url,
        {
            "postfields": json.dumps(params),
            "header": "1",
        },
        30 * 1000,
        "connect_server_cb",
        server_name
    )
    return weechat.WEECHAT_RC_OK

def disconnect_server_cb(server_name, command, rc, out, err):
    if rc != 0:
        weechat.prnt("", "An error occured when disconnecting")
        return weechat.WEECHAT_RC_ERROR

    pop_server(server_name)
    return weechat.WEECHAT_RC_OK

def disconnect_server(server_name):
    server = load_server(server_name)

    if not is_connected(server):
        weechat.prnt("", "Not connected")
        return weechat.WEECHAT_RC_ERROR

    url = server_root_url(server) + "/api/v4/users/logout"
    weechat.hook_process_hashtable(
        "url:" + url,
        {
            "post": "1",
            "httpheader": "\n".join([
                "Authorization: Bearer " + server.token,
                "Content-Type:",
            ]),
        },
        30 * 1000,
        "disconnect_server_cb",
        server_name
    )

    return weechat.WEECHAT_RC_OK

def auto_connect_servers():
    if not weechat.config_is_set_plugin("autoconnect"):
        weechat.config_set_plugin("autoconnect", "")

    auto_connect = weechat.config_get_plugin("autoconnect")
    return list(filter(bool, auto_connect.split(",")))

def auto_connect():
    for server_name in auto_connect_servers():
        connect_server(server_name)
