
import weechat
from typing import NamedTuple
import json
import re

servers = {}

Server = NamedTuple(
    "Server",
    [
        ("name", str),
        ("host", str),
        ("port", str),
        ("protocol", str),
        ("path", str),
        ("username", str),
        ("password", str),
        ("user_id", str),
        ("user_name", str),
        ("user_token", str),
        ("users", dict),
        ("teams", dict),
        ("buffer", any),
        ("buffers", list),
        ("ws", any),
    ],
)

User = NamedTuple(
    "User",
    [
        ("id", str),
        ("username", str),
    ]
)

Team = NamedTuple(
    "Team",
    [
        ("id", str),
        ("name", str),
        ("display_name", str),
        ("buffer", any),
        ("buffers", list),
    ]
)

def server_root_url(server: Server):
    return server.protocol + "://" + server.host + server.path

def get_server(server_name):
    if server_name not in servers:
        weechat.prnt("", "Server is not loaded")
        return

    return servers[server_name]

from wee_matter.room import create_room
from wee_matter.websocket import create_ws

def get_server_config(server_name, key):
    key_prefix = "server." + server_name + "."

    config_key = key_prefix + key
    config_value = weechat.config_get_plugin(key_prefix + key)
    expanded_value = weechat.string_eval_expression(config_value, {}, {}, {})

    return expanded_value

def pop_server(server_name):
    if server_name not in servers:
        weechat.prnt("", "Server is not loaded")
        return

    return servers.pop(server_name)

def load_server(server_name):
    if server_name in servers:
        return servers[server_name]

    servers[server_name] = Server(
        name= server_name,
        host= get_server_config(server_name, "address"),
        port= get_server_config(server_name, "port"),
        protocol= get_server_config(server_name, "protocol"),
        path= "",
        username= get_server_config(server_name, "username"),
        password= get_server_config(server_name, "password"),
        user_id= "",
        user_name= "",
        user_token= "",
        users= {},
        teams= {},
        buffer= None,
        buffers= [],
        ws= None,
    )

    return servers[server_name]

def is_connected(server: Server):
    return server.user_token != ""

def connect_server_team_channels_cb(server_name, command, rc, out, err):
    if rc != 0:
        weechat.prnt("", "An error occured when connecting team channels")
        return weechat.WEECHAT_RC_ERROR

    server = get_server(server_name)

    response = json.loads(out)
    for room in response:
        create_room(room, server)

    return weechat.WEECHAT_RC_OK

def create_team(team_data, server):
    server_number = weechat.buffer_get_integer(server.buffer, "number")

    buffer = weechat.buffer_new("weematter." + team_data["display_name"], "", "", "", "")
    weechat.buffer_set(buffer, "number", str(server_number+1))

    weechat.buffer_set(buffer, "short_name", team_data["display_name"])
    weechat.buffer_set(buffer, "localvar_set_server_name", server.name)
    weechat.buffer_set(buffer, "localvar_set_server", team_data["display_name"])
    weechat.buffer_set(buffer, "localvar_set_type", "server")

    return Team(
        id= team_data["id"],
        name= team_data["name"],
        display_name= team_data["display_name"],
         buffer= buffer,
         buffers= [],
    )

def connect_server_teams_cb(server_name, command, rc, out, err):
    if rc != 0:
        weechat.prnt("", "An error occured when connecting teams")
        return weechat.WEECHAT_RC_ERROR

    server = get_server(server_name)

    response = json.loads(out)

    teams = {}
    for team in response:
        server.teams[team["id"]] = create_team(team, server)

    for team in response:
        url = server_root_url(server) + "/api/v4/users/" + server.user_id + "/teams/" + team["id"] + "/channels"
        weechat.hook_process_hashtable(
            "url:" + url,
            {
                "port": server.port,
                "httpheader": "Authorization: Bearer " + server.user_token,
            },
            30 * 1000,
            "connect_server_team_channels_cb",
            server_name
        )

    return weechat.WEECHAT_RC_OK

def connect_server_users_cb(server_name, command, rc, out, err):
    if rc != 0:
        weechat.prnt("", "An error occured when connecting users")
        return weechat.WEECHAT_RC_ERROR

    server = get_server(server_name)

    response = json.loads(out)
    users = {}
    for user in response:
        server.users[user["id"]] = User(
            id= user["id"],
            username= user["username"],
        )

    url = server_root_url(server) + "/api/v4/users/" + server.user_id + "/teams"
    weechat.hook_process_hashtable(
        "url:" + url,
        {
            "port": server.port,
            "httpheader": "Authorization: Bearer " + server.user_token,
        },
        30 * 1000,
        "connect_server_teams_cb",
        server_name
    )

    return weechat.WEECHAT_RC_OK

def connect_server_cb(server_name, command, rc, out, err):
    if rc != 0:
        weechat.prnt("", "An error occured when connecting")
        return weechat.WEECHAT_RC_ERROR

    token_search = re.search('[tT]oken: (\w*)', out)
    if None == token_search:
        weechat.prnt("", "User token not present in response")
        return weechat.WEECHAT_RC_ERROR

    out = out.splitlines()[-1] # we remove the headers
    response = json.loads(out)

    server = get_server(server_name)

    server = server._replace(
        user_id=response["id"],
        user_name=response["username"],
        user_token=token_search.group(1),
    )

    servers[server_name] = server._replace(
        ws=create_ws(server)
    )

    weechat.prnt("", "Connected to " + server_name)

    url = server_root_url(server) + "/api/v4/users"
    weechat.hook_process_hashtable(
        "url:" + url,
        {
            "port": server.port,
            "httpheader": "Authorization: Bearer " + server.user_token,
        },
        30 * 1000,
        "connect_server_users_cb",
        server_name
    )

    return weechat.WEECHAT_RC_OK

def create_server_buffer(server_name):
    buffer = weechat.buffer_new("weematter." + server_name, "", "", "", "")
    weechat.buffer_set(buffer, "short_name", server_name)
    weechat.buffer_set(buffer, "localvar_set_server_name", server_name)
    weechat.buffer_set(buffer, "localvar_set_type", "server")
    weechat.buffer_set(buffer, "localvar_set_server", server_name)

    return buffer

def connect_server(server_name):
    server = load_server(server_name)

    if is_connected(server):
        weechat.prnt("", "Already connected")
        return weechat.WEECHAT_RC_ERROR

    weechat.prnt("", "Connecting to " + server_name)

    buffer = create_server_buffer(server_name)

    server = get_server(server_name)._replace(
        buffer= buffer
    )
    servers[server_name] = server

    url = server_root_url(server) + "/api/v4/users/login"
    params = {
        "login_id": server.username,
        "password": server.password,
    }

    weechat.hook_process_hashtable(
        "url:" + url,
        {
            "port": server.port,
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

    weechat.prnt("", "Disconnected to " + server_name)

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
            "port": server.port,
            "post": "1",
            "httpheader": "\n".join([
                "Authorization: Bearer " + server.user_token,
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

def disconnect_all():
    for server_name, server in servers.items():
        disconnect_server(server_name)
