
import weechat
import wee_matter
import json
import re
from typing import NamedTuple
from wee_matter.globals import (config, servers)

class Server:
    def __init__(self, name):
        self.name = name
        self.url = config.get_server_config(name, "url").strip("/")
        self.username = config.get_server_config(name, "username")
        self.password = config.get_server_config(name, "password")
        self.user_token = ""
        self.users = {}
        self.teams = {}
        self.buffer = self._create_buffer()
        self.buffers = []
        self.worker = None
        self.reconnection_loop_hook = ""

        self.user = User(
            id = "",
            username = "",
            color = "",
            deleted = False,
        )

    def _create_buffer(self):
        buffer = weechat.buffer_new("weematter." + self.name, "", "", "", "")
        weechat.buffer_set(buffer, "short_name", self.name)
        weechat.buffer_set(buffer, "localvar_set_server_name", self.name)
        weechat.buffer_set(buffer, "localvar_set_type", "server")
        weechat.buffer_set(buffer, "localvar_set_server", self.name)

        return buffer

    def is_connected(self):
        return self.worker

User = NamedTuple(
    "User",
    [
        ("id", str),
        ("username", str),
        ("color", str),
        ("deleted", bool)
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

def get_server_from_buffer(buffer):
    server_name = weechat.buffer_get_string(buffer, "localvar_server_name")
    return servers[server_name]

def unload_team(team):
    for buffer in team.buffers:
        weechat.buffer_close(buffer)
    weechat.buffer_close(team.buffer)


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
    return weechat.info_get("nick_color_name", username)

def create_user_from_user_data(user_data, server):
    return User(
        id= user_data["id"],
        username= user_data["username"],
        color= color_for_username(user_data["username"]),
        deleted = (user_data["delete_at"] != 0),
    )

def server_completion_cb(data, completion_item, current_buffer, completion):
    for server_name in servers:
        weechat.hook_completion_list_add(completion, server_name, 0, weechat.WEECHAT_LIST_POS_SORT)
    return weechat.WEECHAT_RC_OK

def unload_server(server_name):
    if server_name not in servers:
        weechat.prnt("", "Server is not loaded")
        return

    weechat.prnt("", "Unloading server")
    server = servers.pop(server_name)

    if server.worker:
        wee_matter.websocket.close_worker(server.worker)
    if server.reconnection_loop_hook:
        weechat.unhook(server.reconnection_loop_hook)

    for buffer in server.buffers:
        weechat.buffer_close(buffer)
    for team in server.teams.values():
        unload_team(team)

    weechat.buffer_close(server.buffer)

def connect_server_team_channel(channel_id, server):
    wee_matter.room.register_buffer_hydratating(channel_id)
    wee_matter.http.enqueue_request(
        "run_get_channel",
        channel_id, server, "connect_server_team_channel_cb", server.name
    )

def connect_server_team_channel_cb(server_name, command, rc, out, err):
    if rc != 0:
        weechat.prnt("", "An error occurred while connecting team channel")
        return weechat.WEECHAT_RC_ERROR

    server = servers[server_name]

    channel_data = json.loads(out)
    wee_matter.room.create_room_from_channel_data(channel_data, server)

    return weechat.WEECHAT_RC_OK

def connect_server_team_channels_cb(server_name, command, rc, out, err):
    if rc != 0:
        weechat.prnt("", "An error occurred while connecting team channels")
        return weechat.WEECHAT_RC_ERROR

    server = servers[server_name]

    response = json.loads(out)
    for channel_data in response:
        if wee_matter.room.already_loaded_buffer(channel_data["id"]):
            continue
        wee_matter.room.create_room_from_channel_data(channel_data, server)

    return weechat.WEECHAT_RC_OK

def connect_server_users_cb(data, command, rc, out, err):
    if rc != 0:
        weechat.prnt("", "An error occurred while connecting users")
        return weechat.WEECHAT_RC_ERROR

    server_name, page = data.split("|")
    page = int(page)
    server = servers[server_name]

    response = json.loads(out)
    for user in response:
        if user["id"] == server.user.id:
            server.users[user["id"]] = server.user
        else:
            server.users[user["id"]] = create_user_from_user_data(user, server)

    if len(response) == 60:
        wee_matter.http.enqueue_request(
            "run_get_users",
            server, page+1, "connect_server_users_cb", "{}|{}".format(server.name, page+1)
        )
    else:
        wee_matter.http.enqueue_request(
            "run_get_user_teams",
            server.user.id, server, "connect_server_teams_cb", server.name
        )

    return weechat.WEECHAT_RC_OK

def connect_server_teams_cb(server_name, command, rc, out, err):
    if rc != 0:
        weechat.prnt("", "An error occurred while connecting teams")
        return weechat.WEECHAT_RC_ERROR

    server = servers[server_name]

    response = json.loads(out)

    for team_data in response:
        server.teams[team_data["id"]] = create_team_from_team_data(team_data, server)

    for team_data in response:
        wee_matter.http.enqueue_request(
            "run_get_user_team_channels",
            server.user.id, team_data["id"], server, "connect_server_team_channels_cb", server.name
        )

    return weechat.WEECHAT_RC_OK

def connect_server_team_cb(server_name, command, rc, out, err):
    if rc != 0:
        weechat.prnt("", "An error occurred while connecting team")
        return weechat.WEECHAT_RC_ERROR

    server = servers[server_name]

    team_data = json.loads(out)

    server.teams[team_data["id"]] = create_team_from_team_data(team_data, server)
    wee_matter.http.enqueue_request(
        "run_get_user_team_channels",
        server.user.id, team_data["id"], server, "connect_server_team_channels_cb", server.name
    )

    return weechat.WEECHAT_RC_OK

def new_user_cb(server_name, command, rc, out, err):
    if rc != 0:
        weechat.prnt("", "An error occurred while adding a new user")
        return weechat.WEECHAT_RC_ERROR

    server = servers[server_name]

    response = json.loads(out)
    server.users[response["id"]] = create_user_from_user_data(response, server)

    return weechat.WEECHAT_RC_OK

def connect_server_cb(server_name, command, rc, out, err):
    if rc != 0:
        weechat.prnt("", "An error occurred while connecting")
        return weechat.WEECHAT_RC_ERROR

    token_search = re.search('[tT]oken: (\w*)', out)

    out = out.splitlines()[-1] # we remove the headers line
    response = json.loads(out)

    server = servers[server_name]

    user = User(
        id= response["id"],
        username= response["username"],
        color= weechat.config_string(weechat.config_get("weechat.color.chat_nick_self")),
        deleted = False,
    )

    server.user_token=token_search.group(1)
    server.user= user

    worker = wee_matter.websocket.create_worker(server)
    if not worker:
        weechat.prnt("", "An error occurred while creating the websocket worker")
        return weechat.WEECHAT_RC_ERROR
    reconnection_loop_hook = weechat.hook_timer(5 * 1000, 0, 0, "reconnection_loop_cb", server.name)

    server.worker= worker
    server.reconnection_loop_hook= reconnection_loop_hook

    weechat.prnt("", "Connected to " + server_name)

    wee_matter.http.enqueue_request(
        "run_get_users",
        server, 0, "connect_server_users_cb", "{}|0".format(server.name)
    )

    return weechat.WEECHAT_RC_OK

def connect_server(server_name):
    if server_name in servers:
        server = servers[server_name]

        if server != None and server.is_connected():
            weechat.prnt("", "Already connected")
            return weechat.WEECHAT_RC_ERROR

        if server != None:
            unload_server(server_name)

    server = Server(server_name)

    weechat.prnt("", "Connecting to " + server_name)

    servers[server_name] = server

    wee_matter.http.enqueue_request(
        "run_user_login",
        server, "connect_server_cb", server.name
    )

    return weechat.WEECHAT_RC_OK

def disconnect_server(server_name):
    server = servers[server_name]

    if not server.is_connected():
        weechat.prnt("", "Not connected")
        return weechat.WEECHAT_RC_ERROR

    rc = wee_matter.http.logout_user(server)

    if rc == weechat.WEECHAT_RC_OK:
        unload_server(server_name)

    return rc

def reconnect_server(server_name):
    server = servers[server_name]

    if not server.is_connected():
        weechat.prnt("", "Not connected")
        return weechat.WEECHAT_RC_ERROR

    wee_matter.websocket.close_worker(server.worker)

    return weechat.WEECHAT_RC_OK

def auto_connect():
    for server_name in config.get_auto_connect_servers():
        connect_server(server_name)

def disconnect_all():
    for server_name in servers.copy():
        disconnect_server(server_name)
