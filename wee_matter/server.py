
import weechat
from typing import NamedTuple
import json
import time
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
        ("user", any),
        ("user_token", str),
        ("users", dict),
        ("teams", dict),
        ("buffer", any),
        ("buffers", list),
        ("worker", any),
        ("reconnection_loop_hook", str),
    ],
)

User = NamedTuple(
    "User",
    [
        ("id", str),
        ("username", str),
        ("color", str),
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
    root_url = server.protocol + "://" + server.host

    if (server.protocol == "https" and server.port != "443") or (server.protocol == "http" and server.port != "80"):
        root_url += ":" + server.port
    if server.path:
        root_url += server.path

    return root_url

def get_server(server_name):
    if server_name not in servers:
        return

    return servers[server_name]

def get_servers():
    return servers

def update_server_worker(server, worker):
    server = server._replace(worker=worker)
    servers[server.name] = server
    return server

def get_server_from_buffer(buffer):
    server_name = weechat.buffer_get_string(buffer, "localvar_server_name")
    return get_server(server_name)

def create_team_from_team_data(team_data, server):
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

def color_for_username(username):
    nick_colors = weechat.config_string(
         weechat.config_get("weechat.color.chat_nick_colors")
    ).split(",")

    nick_color_count = len(nick_colors)
    color_id = hash(username) % nick_color_count

    return nick_colors[color_id]

def create_user_from_user_data(user_data, server):
    return User(
        id= user_data["id"],
        username= user_data["username"],
        color= color_for_username(user_data["username"]),
    )

def is_connected(server: Server):
    return server.worker

def server_completion_cb(data, completion_item, current_buffer, completion):
    servers = get_servers()
    for server_name in servers:
        weechat.hook_completion_list_add(completion, server_name, 0, weechat.WEECHAT_LIST_POS_SORT)
    return weechat.WEECHAT_RC_OK

def unload_team(team):
    for buffer in team.buffers:
        weechat.buffer_close(buffer)
    weechat.buffer_close(team.buffer)

from wee_matter.room import create_room_from_channel_data
from wee_matter.websocket import create_worker, close_worker
from wee_matter.http import (run_get_user_teams, run_get_users,
                            run_user_login, run_user_logout,
                            run_get_user_team_channels)

def get_server_config(server_name, key):
    key_prefix = "server." + server_name + "."

    config_key = key_prefix + key
    config_value = weechat.config_get_plugin(key_prefix + key)
    expanded_value = weechat.string_eval_expression(config_value, {}, {}, {})

    return expanded_value

def load_server(server_name):
    user = User(
        id = "",
        username = "",
        color = "",
    )
    servers[server_name] = Server(
        name= server_name,
        host= get_server_config(server_name, "address"),
        port= get_server_config(server_name, "port"),
        protocol= get_server_config(server_name, "protocol"),
        path= "",
        username= get_server_config(server_name, "username"),
        password= get_server_config(server_name, "password"),
        user= user,
        user_token= "",
        users= {},
        teams= {},
        buffer= None,
        buffers= [],
        worker= None,
        reconnection_loop_hook= "",
    )

    return servers[server_name]

def unload_server(server_name):
    if server_name not in servers:
        weechat.prnt("", "Server is not loaded")
        return

    weechat.prnt("", "Unloading server")
    server = servers.pop(server_name)

    if server.worker:
        close_worker(server.worker)
    if server.reconnection_loop_hook:
        weechat.unhook(server.reconnection_loop_hook)

    for buffer in server.buffers:
        weechat.buffer_close(buffer)
    for team in server.teams.values():
        unload_team(team)

    weechat.buffer_close(server.buffer)

def connect_server_team_channel_cb(server_name, command, rc, out, err):
    if rc != 0:
        weechat.prnt("", "An error occured when connecting team channel")
        return weechat.WEECHAT_RC_ERROR

    server = get_server(server_name)

    channel_data = json.loads(out)
    create_room_from_channel_data(channel_data, server)

    return weechat.WEECHAT_RC_OK

def connect_server_team_channels_cb(server_name, command, rc, out, err):
    if rc != 0:
        weechat.prnt("", "An error occured when connecting team channels")
        return weechat.WEECHAT_RC_ERROR

    server = get_server(server_name)

    response = json.loads(out)
    for channel_data in response:
        create_room_from_channel_data(channel_data, server)

    return weechat.WEECHAT_RC_OK

def connect_server_users_cb(server_name, command, rc, out, err):
    if rc != 0:
        weechat.prnt("", "An error occured when connecting users")
        return weechat.WEECHAT_RC_ERROR

    server = get_server(server_name)

    response = json.loads(out)
    for user in response:
        if user["id"] == server.user.id:
            server.users[user["id"]] = server.user
        else:
            server.users[user["id"]] = create_user_from_user_data(user, server)

    run_get_user_teams(server.user.id, server, "connect_server_teams_cb", server.name)

    return weechat.WEECHAT_RC_OK

def connect_server_teams_cb(server_name, command, rc, out, err):
    if rc != 0:
        weechat.prnt("", "An error occured when connecting teams")
        return weechat.WEECHAT_RC_ERROR

    server = get_server(server_name)

    response = json.loads(out)

    for team_data in response:
        server.teams[team_data["id"]] = create_team_from_team_data(team_data, server)

    for team_data in response:
        run_get_user_team_channels(server.user.id, team_data["id"], server, "connect_server_team_channels_cb", server.name)

    return weechat.WEECHAT_RC_OK

def connect_server_team_cb(server_name, command, rc, out, err):
    if rc != 0:
        weechat.prnt("", "An error occured when connecting team")
        return weechat.WEECHAT_RC_ERROR

    server = get_server(server_name)

    team_data = json.loads(out)

    server.teams[team_data["id"]] = create_team_from_team_data(team_data, server)
    run_get_user_team_channels(server.user.id, team_data["id"], server, "connect_server_team_channels_cb", server.name)

    return weechat.WEECHAT_RC_OK

def connect_server_cb(server_name, command, rc, out, err):
    if rc != 0:
        weechat.prnt("", "An error occured when connecting")
        return weechat.WEECHAT_RC_ERROR

    token_search = re.search('[tT]oken: (\w*)', out)
    if None == token_search:
        weechat.prnt("", "User token not present in response")
        return weechat.WEECHAT_RC_ERROR

    out = out.splitlines()[-1] # we remove the headers line
    response = json.loads(out)

    server = get_server(server_name)

    user = User(
        id= response["id"],
        username= response["username"],
        color= weechat.config_string(weechat.config_get("weechat.color.chat_nick_self")),
    )

    server = server._replace(
        user_token=token_search.group(1),
        user= user,
    )

    worker = create_worker(server)
    if not worker:
        return weechat.WEECHAT_RC_ERROR
    reconnection_loop_hook = weechat.hook_timer(5 * 1000, 0, 0, "reconnection_loop_cb", server.name)

    server = server._replace(
        worker= worker,
        reconnection_loop_hook= reconnection_loop_hook,
    )
    servers[server_name] = server

    weechat.prnt("", "Connected to " + server_name)

    run_get_users(server, "connect_server_users_cb", server.name)

    return weechat.WEECHAT_RC_OK

def create_server_buffer(server_name):
    buffer = weechat.buffer_new("weematter." + server_name, "", "", "", "")
    weechat.buffer_set(buffer, "short_name", server_name)
    weechat.buffer_set(buffer, "localvar_set_server_name", server_name)
    weechat.buffer_set(buffer, "localvar_set_type", "server")
    weechat.buffer_set(buffer, "localvar_set_server", server_name)

    return buffer

def connect_server(server_name):
    server = get_server(server_name)

    if server != None and is_connected(server):
        weechat.prnt("", "Already connected")
        return weechat.WEECHAT_RC_ERROR

    if server != None:
        unload_server(server_name)

    server = load_server(server_name)

    weechat.prnt("", "Connecting to " + server_name)

    buffer = create_server_buffer(server_name)

    server = get_server(server_name)._replace(
        buffer= buffer
    )
    servers[server_name] = server

    run_user_login(server, "connect_server_cb", server.name)

    return weechat.WEECHAT_RC_OK

def disconnect_server_cb(server_name, command, rc, out, err):
    if rc != 0:
        weechat.prnt("", "An error occured when disconnecting")
        return weechat.WEECHAT_RC_ERROR

    unload_server(server_name)

    weechat.prnt("", "Disconnected")

    return weechat.WEECHAT_RC_OK

def disconnect_server(server_name):
    server = get_server(server_name)

    if not is_connected(server):
        weechat.prnt("", "Not connected")
        return weechat.WEECHAT_RC_ERROR

    run_user_logout(server, "disconnect_server_cb", server.name)

    return weechat.WEECHAT_RC_OK

def reconnect_server(server_name):
    server = get_server(server_name)

    if not is_connected(server):
        weechat.prnt("", "Not connected")
        return weechat.WEECHAT_RC_ERROR

    close_worker(server.worker)

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
