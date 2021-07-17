
import weechat
import wee_matter
import json
import re
from wee_matter.globals import (config, servers)

class User:
    def __init__(self, **kwargs):
        self.id = kwargs["id"]
        self.username = kwargs["username"]
        self.deleted = kwargs["delete_at"] != 0
        self.color = weechat.info_get("nick_color_name", self.username)

class Server:
    def __init__(self, id):
        self.id = id

        if not config.is_server_valid(id):
            raise ValueError("Invalid server id " + id)

        self.url = config.get_server_config(id, "url").strip("/")
        self.username = config.get_server_config(id, "username")
        self.password = config.get_server_config(id, "password")

        if not self.url or not self.username or not self.password:
            raise ValueError("Server " + id + " is not fully configured")

        self.token = ""
        self.me = None
        self.users = {}
        self.teams = {}
        self.buffer = self._create_buffer()
        self.channels = []
        self.worker = None
        self.reconnection_loop_hook = ""

    def _create_buffer(self):
        buffer = weechat.buffer_new("weematter." + self.id, "", "", "", "")
        weechat.buffer_set(buffer, "short_name", self.id)
        weechat.buffer_set(buffer, "localvar_set_server_id", self.id)
        weechat.buffer_set(buffer, "localvar_set_type", "server")

        return buffer

    def is_connected(self):
        return self.worker

    def add_team(self, **kwargs):
        team = Team(self, **kwargs)
        self.teams[team.id] = team

    def unload(self):
        weechat.prnt("", "Unloading server")

        servers.pop(self.id)

        if self.worker:
            wee_matter.websocket.close_worker(self.worker)
        if self.reconnection_loop_hook:
            weechat.unhook(self.reconnection_loop_hook)

        for channel in self.channels:
            channel.unload()
        for team in self.teams.values():
            team.unload()

        weechat.buffer_close(self.buffer)

class Team:
    def __init__(self, server, **kwargs):
        self.server = server
        self.id = kwargs["id"]
        self.name = kwargs["name"]
        self.display_name = kwargs["display_name"]
        self.buffer = self._create_buffer()
        self.channels = []

    def _create_buffer(self):
        buffer = weechat.buffer_new("weematter." + self.display_name, "", "", "", "")

        weechat.buffer_set(buffer, "short_name", self.display_name)
        weechat.buffer_set(buffer, "localvar_set_server_id", self.server.id)
        weechat.buffer_set(buffer, "localvar_set_type", "server")

        return buffer

    def unload(self):
        for channel in self.channels:
            channel.unload()
        weechat.buffer_close(self.buffer)

def get_server_from_buffer(buffer):
    server_id = weechat.buffer_get_string(buffer, "localvar_server_id")
    return servers[server_id]

def server_completion_cb(data, completion_item, current_buffer, completion):
    for server_id in servers:
        weechat.hook_completion_list_add(completion, server_id, 0, weechat.WEECHAT_LIST_POS_SORT)
    return weechat.WEECHAT_RC_OK

def connect_server_team_channel(channel_id, server):
    wee_matter.channel.register_buffer_hydratating(channel_id)
    wee_matter.http.enqueue_request(
        "run_get_channel",
        channel_id, server, "connect_server_team_channel_cb", server.id
    )

def connect_server_team_channel_cb(server_id, command, rc, out, err):
    if rc != 0:
        weechat.prnt("", "An error occurred while connecting team channel")
        return weechat.WEECHAT_RC_ERROR

    server = servers[server_id]

    channel_data = json.loads(out)
    wee_matter.channel.create_channel_from_channel_data(channel_data, server)

    return weechat.WEECHAT_RC_OK

def connect_server_team_channels_cb(server_id, command, rc, out, err):
    if rc != 0:
        weechat.prnt("", "An error occurred while connecting team channels")
        return weechat.WEECHAT_RC_ERROR

    server = servers[server_id]

    response = json.loads(out)
    for channel_data in response:
        if wee_matter.channel.already_loaded_buffer(channel_data["id"]):
            continue
        wee_matter.channel.create_channel_from_channel_data(channel_data, server)

    return weechat.WEECHAT_RC_OK

def connect_server_users_cb(data, command, rc, out, err):
    if rc != 0:
        weechat.prnt("", "An error occurred while connecting users")
        return weechat.WEECHAT_RC_ERROR

    server_id, page = data.split("|")
    page = int(page)
    server = servers[server_id]

    response = json.loads(out)
    for user in response:
        if user["id"] == server.me.id:
            server.users[user["id"]] = server.me
        else:
            server.users[user["id"]] = User(**user)

    if len(response) == 60:
        wee_matter.http.enqueue_request(
            "run_get_users",
            server, page+1, "connect_server_users_cb", "{}|{}".format(server.id, page+1)
        )
    else:
        wee_matter.http.enqueue_request(
            "run_get_user_teams",
            server.me.id, server, "connect_server_teams_cb", server.id
        )

    return weechat.WEECHAT_RC_OK

def connect_server_teams_cb(server_id, command, rc, out, err):
    if rc != 0:
        weechat.prnt("", "An error occurred while connecting teams")
        return weechat.WEECHAT_RC_ERROR

    server = servers[server_id]

    response = json.loads(out)

    for team_data in response:
        server.add_team(**team_data)

        wee_matter.http.enqueue_request(
            "run_get_user_team_channels",
            server.me.id, team_data["id"], server, "connect_server_team_channels_cb", server.id
        )

    return weechat.WEECHAT_RC_OK

def connect_server_team_cb(server_id, command, rc, out, err):
    if rc != 0:
        weechat.prnt("", "An error occurred while connecting team")
        return weechat.WEECHAT_RC_ERROR

    server = servers[server_id]

    team_data = json.loads(out)

    server.add_team(**team_data)

    wee_matter.http.enqueue_request(
        "run_get_user_team_channels",
        server.me.id, team_data["id"], server, "connect_server_team_channels_cb", server.id
    )

    return weechat.WEECHAT_RC_OK

def new_user_cb(server_id, command, rc, out, err):
    if rc != 0:
        weechat.prnt("", "An error occurred while adding a new user")
        return weechat.WEECHAT_RC_ERROR

    server = servers[server_id]

    response = json.loads(out)
    server.users[response["id"]] = User(**response)

    return weechat.WEECHAT_RC_OK

def connect_server_cb(server_id, command, rc, out, err):
    if rc != 0:
        weechat.prnt("", "An error occurred while connecting")
        return weechat.WEECHAT_RC_ERROR

    token_search = re.search('[tT]oken: (\w*)', out)

    out = out.splitlines()[-1] # we remove the headers line
    response = json.loads(out)

    server = servers[server_id]

    me = User(**response)
    me.color = weechat.config_string(weechat.config_get("weechat.color.chat_nick_self"))

    server.token=token_search.group(1)
    server.me= me

    worker = wee_matter.websocket.create_worker(server)
    if not worker:
        weechat.prnt("", "An error occurred while creating the websocket worker")
        return weechat.WEECHAT_RC_ERROR
    reconnection_loop_hook = weechat.hook_timer(5 * 1000, 0, 0, "reconnection_loop_cb", server.id)

    server.worker= worker
    server.reconnection_loop_hook= reconnection_loop_hook

    weechat.prnt("", "Connected to " + server_id)

    wee_matter.http.enqueue_request(
        "run_get_users",
        server, 0, "connect_server_users_cb", "{}|0".format(server.id)
    )

    return weechat.WEECHAT_RC_OK

def connect_server(server_id):
    if server_id in servers:
        server = servers[server_id]

        if server != None and server.is_connected():
            weechat.prnt("", "Already connected")
            return weechat.WEECHAT_RC_ERROR

        if server != None:
            server.unload()

    try:
        server = Server(server_id)
    except ValueError as ve:
        weechat.prnt("", str(ve))
        return weechat.WEECHAT_RC_ERROR

    weechat.prnt("", "Connecting to " + server_id)

    servers[server_id] = server

    wee_matter.http.enqueue_request(
        "run_user_login",
        server, "connect_server_cb", server.id
    )

    return weechat.WEECHAT_RC_OK

def disconnect_server(server_id):
    server = servers[server_id]

    if not server.is_connected():
        weechat.prnt("", "Not connected")
        return weechat.WEECHAT_RC_ERROR

    rc = wee_matter.http.logout_user(server)

    if rc == weechat.WEECHAT_RC_OK:
        server.unload()

    return rc

def auto_connect():
    for server_id in config.get_auto_connect_servers():
        connect_server(server_id)

def disconnect_all():
    for server_id in servers.copy():
        disconnect_server(server_id)
