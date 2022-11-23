
import weechat
import wee_most
import json
import re
import subprocess
from wee_most.globals import (config, servers, DEFAULT_PAGE_COUNT)

class User:
    def __init__(self, **kwargs):
        self.id = kwargs["id"]
        self.username = kwargs["username"]
        self.first_name = kwargs["first_name"]
        self.last_name = kwargs["last_name"]
        self.status = None
        self.deleted = kwargs["delete_at"] != 0
        self.color = weechat.info_get("nick_color_name", self.username)

    @property
    def nick(self):
        nick = self.username

        if config.nick_full_name and self.first_name and self.last_name:
            nick = "{} {}".format(self.first_name, self.last_name)

        return nick

class Server:
    def __init__(self, id):
        self.id = id

        if not config.is_server_valid(id):
            raise ValueError("Invalid server id " + id)

        self.url = config.get_server_config(id, "url").strip("/")
        self.username = config.get_server_config(id, "username")
        self.password = config.get_server_config(id, "password")
        self.command_2fa = config.get_server_config(id, "command_2fa")

        if not self.url or not self.username or not self.password:
            raise ValueError("Server " + id + " is not fully configured")

        self.token = ""
        self.me = None
        self.highlight_words = []
        self.users = {}
        self.teams = {}
        self.buffer = None
        self.channels = {}
        self.worker = None
        self.reconnection_loop_hook = ""
        self.closed_channels = []

        self._create_buffer()

    def _create_buffer(self):
        # use "*" character so that the buffer is unique and gets sorted before all server buffers
        buffer_name = "wee-most.{}*".format(self.id)
        self.buffer = weechat.buffer_new(buffer_name, "", "", "", "")
        weechat.buffer_set(self.buffer, "short_name", self.id)
        weechat.buffer_set(self.buffer, "localvar_set_server_id", self.id)
        weechat.buffer_set(self.buffer, "localvar_set_type", "server")

        buffer_merge(self.buffer)

    def init_me(self, **kwargs):
        self.me = User(**kwargs)
        self.me.color = weechat.config_string(weechat.config_get("weechat.color.chat_nick_self"))

        if kwargs["notify_props"]["first_name"] == "true":
            self.highlight_words.append(kwargs["first_name"])

        if kwargs["notify_props"]["channel"] == "true":
            self.highlight_words.extend(["@here", "@channel", "@all"])

        if kwargs["notify_props"]["mention_keys"]:
            self.highlight_words.extend(kwargs["notify_props"]["mention_keys"].split(","))

    def print(self, message):
        weechat.prnt(self.buffer, message)

    def print_error(self, message):
        weechat.prnt(self.buffer, weechat.prefix("error") + message)

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

    def get_direct_messages_channels(self):
        channels = []

        for channel in self.channels.values():
            if isinstance(channel, wee_most.channel.DirectMessagesChannel):
                channels.append(channel)

        return channels

    def get_direct_messages_channel(self, user_id):
        for channel in self.channels.values():
            if isinstance(channel, wee_most.channel.DirectMessagesChannel) and channel.user.id == user_id:
                return channel

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

    def retrieve_2fa_token(self):
        try:
            out = subprocess.check_output(self.command_2fa, shell=True)
        except (subprocess.CalledProcessError):
            self.print_error("Failed to retrieve 2FA token")
            return ""

        return out.decode("utf-8")

    def unload(self):
        self.print("Unloading server")

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
        parent_buffer_name = weechat.buffer_get_string(self.server.buffer, "name")[:-1]
        # use "*" character so that the buffer is unique and gets sorted before all team buffers
        buffer_name = "{}.{}*".format(parent_buffer_name, self.name)
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

    if not server_id:
        return None

    return servers[server_id]

def get_buffer_user_status_cb(data, remaining_calls):
    buffer = weechat.current_buffer()

    for server in servers.values():
        channel = server.get_channel_from_buffer(buffer)
        if channel:
            wee_most.http.enqueue_request(
                    "run_post_users_status_ids",
                    list(channel.users.keys()), server, "hydrate_channel_users_status_cb", "{}|{}".format(server.id, channel.id)
                    )
            break

    return weechat.WEECHAT_RC_OK

def get_direct_message_channels_user_status_cb(data, remaining_calls):
    for server in servers.values():
        user_ids = []

        for channel in server.get_direct_messages_channels():
            user_ids.append(channel.user.id)

        wee_most.http.enqueue_request(
                "run_post_users_status_ids",
                user_ids, server, "update_direct_message_channels_name", server.id
                )

    return weechat.WEECHAT_RC_OK

def connect_server_team_channel(channel_id, server):
    wee_most.channel.register_buffer_hydratating(server, channel_id)
    wee_most.http.enqueue_request(
        "run_get_channel",
        channel_id, server, "connect_server_team_channel_cb", server.id
    )

def connect_server_team_channel_cb(server_id, command, rc, out, err):
    server = servers[server_id]

    if rc != 0:
        server.print_error("An error occurred while connecting team channel")
        return weechat.WEECHAT_RC_ERROR

    channel_data = json.loads(out)
    wee_most.channel.create_channel_from_channel_data(channel_data, server)

    return weechat.WEECHAT_RC_OK

def connect_server_team_channels_cb(server_id, command, rc, out, err):
    server = servers[server_id]

    if rc != 0:
        server.print_error("An error occurred while connecting team channels")
        return weechat.WEECHAT_RC_ERROR

    response = json.loads(out)
    for channel_data in response:
        if server.get_channel(channel_data["id"]):
            continue
        wee_most.channel.create_channel_from_channel_data(channel_data, server)

    wee_most.http.enqueue_request(
        "run_get_user_channel_members",
        server, 0, "update_channel_mute_status_cb", "{}|0".format(server.id)
    )

    return weechat.WEECHAT_RC_OK

def connect_server_users_cb(data, command, rc, out, err):
    server_id, page = data.split("|")
    page = int(page)
    server = servers[server_id]

    if rc != 0:
        server.print_error("An error occurred while connecting users")
        return weechat.WEECHAT_RC_ERROR

    response = json.loads(out)
    for user in response:
        if user["id"] == server.me.id:
            server.users[user["id"]] = server.me
        else:
            server.users[user["id"]] = User(**user)

    if len(response) == DEFAULT_PAGE_COUNT:
        wee_most.http.enqueue_request(
            "run_get_users",
            server, page+1, "connect_server_users_cb", "{}|{}".format(server.id, page+1)
        )
    else:
        wee_most.http.enqueue_request(
            "run_get_user_teams",
            server, "connect_server_teams_cb", server.id
        )

    return weechat.WEECHAT_RC_OK

def connect_server_preferences_cb(server_id, command, rc, out, err):
    server = servers[server_id]

    if rc != 0:
        server.print_error("An error occurred while connecting preferences")
        return weechat.WEECHAT_RC_ERROR

    response = json.loads(out)

    for pref in response:
        if pref["category"] in ["direct_channel_show", "group_channel_show"] and pref["value"] == "false":
            server.closed_channels.append(pref["name"])

    return weechat.WEECHAT_RC_OK

def connect_server_teams_cb(server_id, command, rc, out, err):
    server = servers[server_id]

    if rc != 0:
        server.print_error("An error occurred while connecting teams")
        return weechat.WEECHAT_RC_ERROR

    response = json.loads(out)

    for team_data in response:
        server.add_team(**team_data)

        wee_most.http.enqueue_request(
            "run_get_user_team_channels",
            team_data["id"], server, "connect_server_team_channels_cb", server.id
        )

    return weechat.WEECHAT_RC_OK

def connect_server_team_cb(server_id, command, rc, out, err):
    server = servers[server_id]

    if rc != 0:
        server.print_error("An error occurred while connecting team")
        return weechat.WEECHAT_RC_ERROR

    team_data = json.loads(out)

    server.add_team(**team_data)

    wee_most.http.enqueue_request(
        "run_get_user_team_channels",
        team_data["id"], server, "connect_server_team_channels_cb", server.id
    )

    return weechat.WEECHAT_RC_OK

def new_user_cb(server_id, command, rc, out, err):
    server = servers[server_id]

    if rc != 0:
        server.print_error("An error occurred while adding a new user")
        return weechat.WEECHAT_RC_ERROR

    response = json.loads(out)
    server.users[response["id"]] = User(**response)

    return weechat.WEECHAT_RC_OK

def connect_server_cb(server_id, command, rc, out, err):
    server = servers[server_id]

    if rc != 0:
        server.print_error("An error occurred while connecting")
        return weechat.WEECHAT_RC_ERROR

    token_search = re.search("[tT]oken: (\w*)", out)

    out = out.splitlines()[-1] # we remove the headers line
    response = json.loads(out)

    server.token = token_search.group(1)
    server.init_me(**response)

    try:
        worker = wee_most.websocket.Worker(server)
    except:
        server.print_error("An error occurred while creating the websocket worker")
        return weechat.WEECHAT_RC_ERROR

    reconnection_loop_hook = weechat.hook_timer(5 * 1000, 0, 0, "reconnection_loop_cb", server.id)

    server.worker = worker
    server.reconnection_loop_hook = reconnection_loop_hook

    server.print("Connected to " + server_id)

    wee_most.http.enqueue_request(
        "run_get_users",
        server, 0, "connect_server_users_cb", "{}|0".format(server.id)
    )

    wee_most.http.enqueue_request(
        "run_get_preferences",
        server, "connect_server_preferences_cb", server.id
    )

    return weechat.WEECHAT_RC_OK

def connect_server(server_id):
    if server_id in servers:
        server = servers[server_id]

        if server != None and server.is_connected():
            server.print_error("Already connected")
            return weechat.WEECHAT_RC_ERROR

        if server != None:
            server.unload()

    try:
        server = Server(server_id)
    except ValueError as ve:
        server.print_error(str(ve))
        return weechat.WEECHAT_RC_ERROR

    server.print("Connecting to " + server_id)

    servers[server_id] = server

    wee_most.http.enqueue_request(
        "run_user_login",
        server, "connect_server_cb", server.id
    )

    return weechat.WEECHAT_RC_OK

def disconnect_server(server_id):
    server = servers[server_id]

    if not server.is_connected():
        server.print_error("Not connected")
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
