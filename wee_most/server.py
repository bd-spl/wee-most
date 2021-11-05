
import weechat
import wee_most
import json
import re
from wee_most.globals import (config, servers)

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
        self.buffer = None
        self.channels = {}
        self.worker = None
        self.reconnection_loop_hook = ""

        self._create_buffer()

    def _create_buffer(self):
        buffer_name = "wee-most.{}".format(self.id)
        self.buffer = weechat.buffer_new(buffer_name, "", "", "", "")
        weechat.buffer_set(self.buffer, "short_name", self.id)
        weechat.buffer_set(self.buffer, "localvar_set_server_id", self.id)
        weechat.buffer_set(self.buffer, "localvar_set_type", "server")

        buffer_merge(self.buffer)

    def get_channel(self, channel_id):
        if channel_id in self.channels:
            return self.channels[channel_id]

        for team in self.teams.values():
            if channel_id in team.channels:
                return team.channels[channel_id]

        return None

    def get_channel_from_buffer(self, buffer):
        for channel in self.channels.values():
            if channel.buffer == buffer:
                return channel

        for team in self.teams.values():
            for channel in team.channels.values():
                if channel.buffer == buffer:
                    return channel

        return None

    def get_post(self, post_id):
        for channel in self.channels.values():
            if post_id in channel.posts:
                return channel.posts[post_id]

        for team in self.teams.values():
            for channel in team.channels.values():
                if post_id in channel.posts:
                    return channel.posts[post_id]

        return None

    def is_connected(self):
        return self.worker

    def add_team(self, **kwargs):
        team = Team(self, **kwargs)
        self.teams[team.id] = team

    def unload(self):
        weechat.prnt("", "Unloading server")

        servers.pop(self.id)

        if self.worker:
            wee_most.websocket.close_worker(self.worker)
        if self.reconnection_loop_hook:
            weechat.unhook(self.reconnection_loop_hook)

        for channel in self.channels.values():
            channel.unload()
        for team in self.teams.values():
            team.unload()

        weechat.buffer_close(self.buffer)

class Team:
    def __init__(self, server, **kwargs):
        self.server = server
        self.id = kwargs["id"]
        self.name = kwargs["display_name"]
        self.buffer = None
        self.channels = {}

        self._create_buffer()

    def _create_buffer(self):
        parent_buffer_name = weechat.buffer_get_string(self.server.buffer, "name")
        buffer_name = "{}.{}".format(parent_buffer_name, self.name)
        self.buffer = weechat.buffer_new(buffer_name, "", "", "", "")

        weechat.buffer_set(self.buffer, "short_name", self.name)
        weechat.buffer_set(self.buffer, "localvar_set_server_id", self.server.id)
        weechat.buffer_set(self.buffer, "localvar_set_type", "server")

        buffer_merge(self.buffer)

    def unload(self):
        for channel in self.channels.values():
            channel.unload()
        weechat.buffer_close(self.buffer)

def buffer_merge(buffer):
    if weechat.config_string(weechat.config_get("irc.look.server_buffer")) == "merge_with_core":
        weechat.buffer_merge(buffer, weechat.buffer_search_main())
    else:
        weechat.buffer_unmerge(buffer, 0)

def config_server_buffer_cb(data, key, value):
    for server in servers.values():
        buffer_merge(server.buffer)
        for team in server.teams.values():
            buffer_merge(team.buffer)
    return weechat.WEECHAT_RC_OK

def get_server_from_buffer(buffer):
    server_id = weechat.buffer_get_string(buffer, "localvar_server_id")
    return servers[server_id]

def connect_server_team_channel(channel_id, server):
    wee_most.channel.register_buffer_hydratating(channel_id)
    wee_most.http.enqueue_request(
        "run_get_channel",
        channel_id, server, "connect_server_team_channel_cb", server.id
    )

def connect_server_team_channel_cb(server_id, command, rc, out, err):
    if rc != 0:
        weechat.prnt("", "An error occurred while connecting team channel")
        return weechat.WEECHAT_RC_ERROR

    server = servers[server_id]

    channel_data = json.loads(out)
    wee_most.channel.create_channel_from_channel_data(channel_data, server)

    return weechat.WEECHAT_RC_OK

def connect_server_team_channels_cb(server_id, command, rc, out, err):
    if rc != 0:
        weechat.prnt("", "An error occurred while connecting team channels")
        return weechat.WEECHAT_RC_ERROR

    server = servers[server_id]

    response = json.loads(out)
    for channel_data in response:
        if server.get_channel(channel_data["id"]):
            continue
        wee_most.channel.create_channel_from_channel_data(channel_data, server)

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
        wee_most.http.enqueue_request(
            "run_get_users",
            server, page+1, "connect_server_users_cb", "{}|{}".format(server.id, page+1)
        )
    else:
        wee_most.http.enqueue_request(
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

        wee_most.http.enqueue_request(
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

    wee_most.http.enqueue_request(
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

    server.token = token_search.group(1)
    server.me = me

    try:
        worker = wee_most.websocket.Worker(server)
    except:
        weechat.prnt("", "An error occurred while creating the websocket worker")
        return weechat.WEECHAT_RC_ERROR

    reconnection_loop_hook = weechat.hook_timer(5 * 1000, 0, 0, "reconnection_loop_cb", server.id)

    server.worker = worker
    server.reconnection_loop_hook = reconnection_loop_hook

    weechat.prnt("", "Connected to " + server_id)

    wee_most.http.enqueue_request(
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

    wee_most.http.enqueue_request(
        "run_user_login",
        server, "connect_server_cb", server.id
    )

    return weechat.WEECHAT_RC_OK

def disconnect_server(server_id):
    server = servers[server_id]

    if not server.is_connected():
        weechat.prnt("", "Not connected")
        return weechat.WEECHAT_RC_ERROR

    rc = wee_most.http.logout_user(server)

    if rc == weechat.WEECHAT_RC_OK:
        server.unload()

    return rc

def auto_connect():
    for server_id in config.autoconnect:
        connect_server(server_id)

def disconnect_all():
    for server_id in servers.copy():
        disconnect_server(server_id)
