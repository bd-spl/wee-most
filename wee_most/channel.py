
import weechat
import json
import wee_most
import re
from wee_most.globals import (config, servers, DEFAULT_PAGE_COUNT)

hydrating_buffers = []

CHANNEL_TYPES = {
    "D": "direct",
    "G": "group",
    "O": "public", # ordinary
    "P": "private",
}

NICK_GROUPS = {
    "away": "1|Away",
    "dnd": "2|Do not disturb",
    "offline": "3|Offline",
    "online": "0|Online",
}

class ChannelBase:
    def __init__(self, server, **kwargs):
        self.id = kwargs["id"]
        self.type = CHANNEL_TYPES.get(kwargs["type"])
        self.title = kwargs["header"]
        self.server = server
        self.name = self._format_name(kwargs["display_name"], kwargs["name"])
        self.buffer = None
        self.posts = {}
        self.users = {}

        self._create_buffer()

    def _create_buffer(self):
        buffer_name = self._format_buffer_name()
        self.buffer = weechat.buffer_new(buffer_name, "channel_input_cb", "", "", "")

        weechat.buffer_set(self.buffer, "short_name", self.name)
        weechat.buffer_set(self.buffer, "title", self.title)

        weechat.buffer_set(self.buffer, "localvar_set_server_id", self.server.id)
        weechat.buffer_set(self.buffer, "localvar_set_channel_id", self.id)
        weechat.buffer_set(self.buffer, "localvar_set_type", "channel")

        weechat.buffer_set(self.buffer, "nicklist", "1")

        weechat.buffer_set(self.buffer, "highlight_words", ",".join(self.server.highlight_words))
        weechat.buffer_set(self.buffer, "localvar_set_nick", self.server.me.nick)

    def mark_as_read(self):
        last_post_id = weechat.buffer_get_string(self.buffer, "localvar_last_post_id")
        last_read_post_id = weechat.buffer_get_string(self.buffer, "localvar_last_read_post_id")
        if last_post_id and last_post_id == last_read_post_id: # prevent spamming on buffer switch
            return

        wee_most.http.run_post_channel_view(self.id, self.server, "singularity_cb", "")

        weechat.buffer_set(self.buffer, "localvar_set_last_read_post_id", last_post_id)

    def add_user(self, user_id):
        if user_id not in self.server.users:
            return

        user = self.server.users[user_id]

        if user.deleted:
            return

        self.users[user_id] = user

    def update_nicklist(self):
        user_without_status_ids = [u.id for i, u in self.users.items() if u.status is None]

        if user_without_status_ids:
            wee_most.http.enqueue_request(
                    "run_post_users_status_ids",
                    user_without_status_ids, self.server, "hydrate_channel_users_status_cb", "{}|{}".format(self.server.id, self.id)
                    )
            return

        for id, user in self.users.items():
            group = self._get_nick_group(user.status)
            weechat.nicklist_add_nick(self.buffer, group, user.nick, user.color, "", user.color, 1)

    def _get_nick_group(self, status):
        name = NICK_GROUPS.get(status)
        if not name:
            return ""

        group = weechat.nicklist_search_group(self.buffer, "", name)
        if not group:
            group = weechat.nicklist_add_group(self.buffer, "", name, "weechat.color.nicklist_group", 1)

        return group

    def _format_buffer_name(self):
        parent_buffer_name = weechat.buffer_get_string(self.server.buffer, "name")
        # use "!" character so that the buffer gets sorted just after the server buffer and before all teams buffers
        return "{}.!.{}".format(parent_buffer_name, self.name)

    def _format_name(self, display_name, name):
        final_name = display_name

        name_override = config.get_value("channel." + name);

        if name_override:
            final_name = name_override

        return config.get_value("channel_prefix_" + self.type) + final_name

    def unload(self):
        weechat.buffer_close(self.buffer)

class DirectMessagesChannel(ChannelBase):
    def __init__(self, server, **kwargs):
        super(DirectMessagesChannel, self).__init__(server, **kwargs)
        weechat.buffer_set(self.buffer, "localvar_set_type", "private")

    def _format_name(self, display_name, name):
        match = re.match("(\w+)__(\w+)", name)

        user = self.server.users[match.group(1)]
        if user.username == self.server.me.username:
            user = self.server.users[match.group(2)]

        return user.nick

class GroupChannel(ChannelBase):
    def __init__(self, server, **kwargs):
        super(GroupChannel, self).__init__(server, **kwargs)
        weechat.buffer_set(self.buffer, "localvar_set_type", "private")

class PrivateChannel(ChannelBase):
    def __init__(self, team, **kwargs):
        self.team = team
        super(PrivateChannel, self).__init__(team.server, **kwargs)

    def _format_buffer_name(self):
        parent_buffer_name = weechat.buffer_get_string(self.team.buffer, "name")
        return "{}.{}".format(parent_buffer_name, self.name)

class PublicChannel(ChannelBase):
    def __init__(self, team, **kwargs):
        self.team = team
        super(PublicChannel, self).__init__(team.server, **kwargs)

    def _format_buffer_name(self):
        parent_buffer_name = weechat.buffer_get_string(self.team.buffer, "name")
        return "{}.{}".format(parent_buffer_name, self.name)

def is_buffer_hydratating(channel_id):
    return channel_id in hydrating_buffers

def register_buffer_hydratating(server, channel_id):
    if is_buffer_hydratating(channel_id):
        return
    hydrating_buffers.append(channel_id)

    buffer = server.get_channel(channel_id).buffer
    old_name = weechat.buffer_get_string(buffer, "short_name")
    loading_indicator = config.channel_loading_indicator
    weechat.buffer_set(buffer, "short_name", "{}{}".format(loading_indicator, old_name))

def remove_buffer_hydratating(server, channel_id):
    buffer = server.get_channel(channel_id).buffer
    old_name = weechat.buffer_get_string(buffer, "short_name")
    loading_indicator = config.channel_loading_indicator
    weechat.buffer_set(buffer, "short_name", re.sub("^{}".format(loading_indicator), "", old_name))

    hydrating_buffers.remove(channel_id)

def channel_input_cb(data, buffer, input_data):
    server = wee_most.server.get_server_from_buffer(buffer)

    post = {
        "channel_id": weechat.buffer_get_string(buffer, "localvar_channel_id"),
        "message": input_data,
    }

    wee_most.http.run_post_post(post, server, "post_post_cb", buffer)

    return weechat.WEECHAT_RC_OK

def hydrate_channel_posts_cb(buffer, command, rc, out, err):
    if rc != 0:
        weechat.prnt("", "An error occurred while hydrating channel")
        return weechat.WEECHAT_RC_ERROR

    server = wee_most.server.get_server_from_buffer(buffer)

    response = json.loads(out)

    response["order"].reverse()
    for post_id in response["order"]:
        builded_post = wee_most.post.Post(server, **response["posts"][post_id])
        wee_most.post.write_post(builded_post)

    if "" != response["next_post_id"]:
        wee_most.http.enqueue_request(
            "run_get_channel_posts_after",
            builded_post.id, builded_post.channel.id, server, "hydrate_channel_posts_cb", buffer
        )
    else:
        channel_id = weechat.buffer_get_string(buffer, "localvar_channel_id")
        remove_buffer_hydratating(server, channel_id)

    return weechat.WEECHAT_RC_OK

def hydrate_channel_read_posts_cb(buffer, command, rc, out, err):
    if rc != 0:
        weechat.prnt("", "An error occurred while hydrating channel")
        return weechat.WEECHAT_RC_ERROR

    server = wee_most.server.get_server_from_buffer(buffer)

    response = json.loads(out)

    if not response["order"]:
        return weechat.WEECHAT_RC_OK

    response["order"].reverse()
    for post_id in response["order"]:
        post = wee_most.post.Post(server, **response["posts"][post_id])
        post.read = True
        wee_most.post.write_post(post)

    weechat.buffer_set(buffer, "localvar_set_last_read_post_id", post.id)
    weechat.buffer_set(buffer, "unread", "-")
    weechat.buffer_set(buffer, "hotlist", "-1")

    if "" != response["next_post_id"]:
        wee_most.http.enqueue_request(
            "run_get_channel_posts_after",
            post.id, post.channel.id, server, "hydrate_channel_posts_cb", buffer
        )
    else:
        remove_buffer_hydratating(server, post.channel.id)

    return weechat.WEECHAT_RC_OK

def hydrate_channel_users_cb(data, command, rc, out, err):
    if rc != 0:
        weechat.prnt("", "An error occurred while hydrating channel users")
        return weechat.WEECHAT_RC_ERROR

    server_id, channel_id, page = data.split("|")
    page = int(page)
    server = servers[server_id]
    channel = server.get_channel(channel_id)

    response = json.loads(out)

    if len(response) == DEFAULT_PAGE_COUNT:
        wee_most.http.enqueue_request(
            "run_get_channel_members",
            channel.id, server, page+1, "hydrate_channel_users_cb", "{}|{}|{}".format(server_id, channel_id, page+1)
        )

    for user_data in response:
        channel.add_user(user_data["user_id"])

    return weechat.WEECHAT_RC_OK

def hydrate_channel_users_status_cb(data, command, rc, out, err):
    if rc != 0:
        weechat.prnt("", "An error occurred while hydrating channel users status")
        return weechat.WEECHAT_RC_ERROR

    server_id, channel_id = data.split("|")
    server = servers[server_id]
    channel = server.get_channel(channel_id)

    response = json.loads(out)

    for user_data in response:
        user_id = user_data["user_id"]
        if user_id not in channel.users:
            continue
        user = channel.users[user_id]
        user.status = user_data["status"]

    channel.update_nicklist()

    return weechat.WEECHAT_RC_OK

def remove_channel_user(buffer, user):
    nick = weechat.nicklist_search_nick(buffer, "", user.nick)
    weechat.nicklist_remove_nick(buffer, nick)

def build_channel_name_from_channel_data(channel_data, server):
    channel_name = channel_data["name"]
    if "" != channel_data["display_name"]:
        prefix = config.get_value("channel_prefix_" + CHANNEL_TYPES.get(channel_data["type"]))
        channel_name = prefix + channel_data["display_name"]
    else:
        match = re.match("(\w+)__(\w+)", channel_data["name"])

        if match:
            user = server.users[match.group(1)]
            if user.username == server.me.username:
                user = server.users[match.group(2)]
            channel_name = user.nick

    return channel_name

def create_channel_from_channel_data(channel_data, server):
    if channel_data["type"] == "D":
        if channel_data["last_post_at"] == 0:
            return;

        match = re.match("(\w+)__(\w+)", channel_data["name"])
        if match.group(1) in server.closed_channels or match.group(2) in server.closed_channels:
            return;

        channel = DirectMessagesChannel(server, **channel_data)
        server.channels[channel.id] = channel
    elif channel_data["type"] == "G":
        if channel_data["id"] in server.closed_channels:
            return;

        channel = GroupChannel(server, **channel_data)
        server.channels[channel.id] = channel
    else:
        team = server.teams[channel_data["team_id"]]

        if channel_data["type"] == "P":
            channel = PrivateChannel(team, **channel_data)
        elif channel_data["type"] == "O":
            channel = PublicChannel(team, **channel_data)
        else:
            weechat.prnt("", "Unknown channel type " + channel_data["type"])
            channel = PublicChannel(team, **channel_data)

        team.channels[channel.id] = channel

    register_buffer_hydratating(server, channel_data["id"])
    wee_most.http.enqueue_request(
        "run_get_read_channel_posts",
        channel_data["id"], server, "hydrate_channel_read_posts_cb", channel.buffer
    )
    wee_most.http.enqueue_request(
        "run_get_channel_members",
        channel.id, server, 0, "hydrate_channel_users_cb", "{}|{}|0".format(server.id, channel.id)
    )

def set_channel_properties_from_channel_data(channel_data, server):
    buffer = server.get_channel(channel_data["id"]).buffer

    channel_name = build_channel_name_from_channel_data(channel_data, server)
    weechat.buffer_set(buffer, "short_name", channel_name)
    weechat.buffer_set(buffer, "title", channel_data["header"])

def buffer_switch_cb(data, signal, buffer):
    for server in servers.values():
        channel = server.get_channel_from_buffer(buffer)
        if channel:
            channel.mark_as_read()
            channel.update_nicklist()
            break

    return weechat.WEECHAT_RC_OK

def channel_click_cb(data, info):
    if "wee-most" != info.get("_buffer_localvar_script_name"):
        return info

    if info["_key"] != "button1":
        return

    if "post_id_" in info["_chat_line_tags"]:
        wee_most.post.handle_post_click(data, info)
    elif "file_id_" in info["_chat_line_tags"]:
        wee_most.file.handle_file_click(data, info)

def handle_multiline_message_cb(data, modifier, buffer, string):
    for server in servers.values():
        if server.get_channel_from_buffer(buffer):
            if "\n" in string and not string[0] == "/":
                channel_input_cb(data, buffer, string)
                return ""
            return string

    return string
