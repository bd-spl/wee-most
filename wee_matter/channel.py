
import weechat
import json
import wee_matter
import re
from wee_matter.globals import (config, servers, channel_buffers)

hydrating_buffers = []

CHANNEL_TYPES = {
    "D": "direct",
    "G": "group",
    "O": "public", # ordinary
    "P": "private",
}

class ChannelBase:
    def __init__(self, server, **kwargs):
        self.id = kwargs["id"]
        self.type = CHANNEL_TYPES.get(kwargs["type"])
        self.title = kwargs["header"]
        self.server = server
        self.name = self._format_name(kwargs["display_name"], kwargs["name"])
        self.buffer = self._create_buffer()

    def _create_buffer(self):
        buffer_name = self._format_buffer_name()
        buffer = weechat.buffer_new(buffer_name, "channel_input_cb", "", "", "")

        weechat.buffer_set(buffer, "short_name", self.name)
        weechat.buffer_set(buffer, "title", self.title)

        weechat.buffer_set(buffer, "localvar_set_server_id", self.server.id)
        weechat.buffer_set(buffer, "localvar_set_channel_id", self.id)
        weechat.buffer_set(buffer, "localvar_set_type", "channel")

        weechat.buffer_set(buffer, "nicklist", "1")

        weechat.buffer_set(buffer, "highlight_words", "@{0},{0},@here,@channel,@all".format(self.server.me.username))
        weechat.buffer_set(buffer, "localvar_set_nick", self.server.me.username)

        weechat.hook_command_run("/buffer %s" % self.name, 'channel_switch_cb', buffer)

        channel_buffers[self.id] = buffer

        return buffer

    def _format_buffer_name(self):
        parent_buffer_name = weechat.buffer_get_string(self.server.buffer, "name")
        # use "!" character so that the buffer gets sorted just after the server buffer and before all teams buffers
        return "{}.!.{}".format(parent_buffer_name, self.name)

    def _format_name(self, display_name, name):
        return config.get_value("channel_prefix_" + self.type) + display_name

    def unload(self):
        weechat.buffer_close(self.buffer)

class DirectMessagesChannel(ChannelBase):
    def __init__(self, server, **kwargs):
        super(DirectMessagesChannel, self).__init__(server, **kwargs)

    def _create_buffer(self):
        buffer = super()._create_buffer()

        weechat.buffer_set(buffer, "localvar_set_type", "private")

        return buffer

    def _format_name(self, display_name, name):
        match = re.match('(\w+)__(\w+)', name)
        username = self.server.users[match.group(1)].username
        if username == self.server.me.username:
            username = self.server.users[match.group(2)].username

        return username

class GroupChannel(ChannelBase):
    def __init__(self, server, **kwargs):
        super(GroupChannel, self).__init__(server, **kwargs)

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

def already_loaded_buffer(channel_id):
    return channel_id in channel_buffers

def is_buffer_hydratating(channel_id):
    return channel_id in hydrating_buffers

def register_buffer_hydratating(channel_id):
    if is_buffer_hydratating(channel_id):
        return
    hydrating_buffers.append(channel_id)

    buffer = get_buffer_from_channel_id(channel_id)
    old_name = weechat.buffer_get_string(buffer, "short_name")
    weechat.buffer_set(buffer, "short_name", "⚠️ {}".format(old_name))

def remove_buffer_hydratating(channel_id):
    buffer = get_buffer_from_channel_id(channel_id)
    old_name = weechat.buffer_get_string(buffer, "short_name")
    weechat.buffer_set(buffer, "short_name", re.sub("⚠️ ", "", old_name))

    hydrating_buffers.remove(channel_id)

def get_buffer_from_channel_id(channel_id):
    return channel_buffers[channel_id]

def channel_switch_cb(buffer, current_buffer, args):
    weechat.buffer_set(buffer, "display", "1")
    return weechat.WEECHAT_RC_OK_EAT

def private_completion_cb(data, completion_item, current_buffer, completion):
    for server in servers.values():
        for channel in server.channels:
            buffer_name = weechat.buffer_get_string(channel.buffer, "short_name")
            weechat.hook_completion_list_add(completion, buffer_name, 0, weechat.WEECHAT_LIST_POS_SORT)
    return weechat.WEECHAT_RC_OK

def channel_completion_cb(data, completion_item, current_buffer, completion):
    for server in servers.values():
        weechat.hook_completion_list_add(completion, server.id, 0, weechat.WEECHAT_LIST_POS_SORT)
        for team in server.teams.values():
            for channel in team.channels:
                buffer_name = weechat.buffer_get_string(channel.buffer, "short_name")
                weechat.hook_completion_list_add(completion, buffer_name, 0, weechat.WEECHAT_LIST_POS_SORT)

    return weechat.WEECHAT_RC_OK

def mark_channel_as_read(buffer):
    server = wee_matter.server.get_server_from_buffer(buffer)
    channel_id = weechat.buffer_get_string(buffer, "localvar_channel_id")

    last_post_id = weechat.buffer_get_string(buffer, "localvar_last_post_id")
    last_read_post_id = weechat.buffer_get_string(buffer, "localvar_last_read_post_id")
    if last_post_id and last_post_id == last_read_post_id: # prevent spamming on buffer switch
        return

    wee_matter.http.run_post_channel_view(server.me.id, channel_id, server, "singularity_cb", "")

    weechat.buffer_set(buffer, "localvar_set_last_read_post_id", last_post_id)

def channel_input_cb(data, buffer, input_data):
    server = wee_matter.server.get_server_from_buffer(buffer)

    builded_post = wee_matter.post.build_post_from_input_data(buffer, input_data)

    wee_matter.http.run_post_post(builded_post, server, "post_post_cb", buffer)

    return weechat.WEECHAT_RC_OK

def hydrate_channel_posts_cb(buffer, command, rc, out, err):
    if rc != 0:
        weechat.prnt("", "An error occurred while hydrating channel")
        return weechat.WEECHAT_RC_ERROR

    server = wee_matter.server.get_server_from_buffer(buffer)

    response = json.loads(out)

    response["order"].reverse()
    for post_id in response["order"]:
        builded_post = wee_matter.post.build_post_from_post_data(response["posts"][post_id])
        wee_matter.post.write_post(builded_post)

    if "" != response["next_post_id"]:
        wee_matter.http.enqueue_request(
            "run_get_channel_posts_after",
            builded_post.id, builded_post.channel_id, server, "hydrate_channel_posts_cb", buffer
        )
    else:
        channel_id = weechat.buffer_get_string(buffer, "localvar_channel_id")
        remove_buffer_hydratating(channel_id)

    return weechat.WEECHAT_RC_OK

def hydrate_channel_read_posts_cb(buffer, command, rc, out, err):
    if rc != 0:
        weechat.prnt("", "An error occurred while hydrating channel")
        return weechat.WEECHAT_RC_ERROR

    server = wee_matter.server.get_server_from_buffer(buffer)

    response = json.loads(out)

    if not response["order"]:
        return weechat.WEECHAT_RC_OK

    response["order"].reverse()
    for post_id in response["order"]:
        post = wee_matter.post.build_post_from_post_data(response["posts"][post_id], True)
        wee_matter.post.write_post(post)

    weechat.buffer_set(buffer, "localvar_set_last_read_post_id", post.id)
    weechat.buffer_set(buffer, "unread", "-")
    weechat.buffer_set(buffer, "hotlist", "-1")

    if "" != response["next_post_id"]:
        wee_matter.http.enqueue_request(
            "run_get_channel_posts_after",
            post.id, post.channel_id, server, "hydrate_channel_posts_cb", buffer
        )
    else:
        remove_buffer_hydratating(post.channel_id)

    return weechat.WEECHAT_RC_OK

def create_channel_user_from_user_data(user_data, buffer, server):
    user = server.users[user_data["user_id"]]

    if user.deleted:
        return

    weechat.nicklist_add_nick(buffer, "", user.username, user.color, "@", user.color, 1)

def hydrate_channel_users_cb(buffer, command, rc, out, err):
    if rc != 0:
        weechat.prnt("", "An error occurred while hydrating channel users")
        return weechat.WEECHAT_RC_ERROR

    response = json.loads(out)

    server = wee_matter.server.get_server_from_buffer(buffer)

    for user_data in response:
        create_channel_user_from_user_data(user_data, buffer, server)

    return weechat.WEECHAT_RC_OK

def hydrate_channel_user_cb(buffer, command, rc, out, err):
    if rc != 0:
        weechat.prnt("", "An error occurred while hydrating channel user")
        return weechat.WEECHAT_RC_ERROR

    user_data = json.loads(out)

    server = wee_matter.server.get_server_from_buffer(buffer)

    create_channel_user_from_user_data(user_data, buffer, server)

    return weechat.WEECHAT_RC_OK

def remove_channel_user(buffer, user):
    nick = weechat.nicklist_search_nick(buffer, "", user.username)
    weechat.nicklist_remove_nick(buffer, nick)

def build_channel_name_from_channel_data(channel_data, server):
    channel_name = channel_data["name"]
    if "" != channel_data["display_name"]:
        prefix = config.get_value("channel_prefix_" + CHANNEL_TYPES.get(channel_data["type"]))
        channel_name = prefix + channel_data["display_name"]
    else:
        match = re.match('(\w+)__(\w+)', channel_data["name"])
        if match:
            channel_name = server.users[match.group(1)].username
            if channel_name == server.me.username:
                channel_name = server.users[match.group(2)].username

    return channel_name

def create_channel_from_channel_data(channel_data, server):
    if channel_data["type"] == "D":
        channel = DirectMessagesChannel(server, **channel_data)
        server.channels.append(channel)
    elif channel_data["type"] == "G":
        channel = GroupChannel(server, **channel_data)
        server.channels.append(channel)
    else:
        team = server.teams[channel_data["team_id"]]

        if channel_data["type"] == "P":
            channel = PrivateChannel(team, **channel_data)
        elif channel_data["type"] == "O":
            channel = PublicChannel(team, **channel_data)
        else:
            weechat.prnt("", "Unknown channel type " + channel_data["type"])
            channel = PublicChannel(team, **channel_data)

        team.channels.append(channel)

    register_buffer_hydratating(channel_data["id"])
    wee_matter.http.enqueue_request(
        "run_get_read_channel_posts",
        server.me.id, channel_data["id"], server, "hydrate_channel_read_posts_cb", channel.buffer
    )
    wee_matter.http.enqueue_request(
        "run_get_channel_members",
        channel_data["id"], server, "hydrate_channel_users_cb", channel.buffer
    )

def set_channel_properties_from_channel_data(channel_data, server):
    buffer = channel_buffers[channel_data["id"]]

    channel_name = build_channel_name_from_channel_data(channel_data, server)
    weechat.buffer_set(buffer, "short_name", channel_name)
    weechat.buffer_set(buffer, "title", channel_data["header"])
    weechat.hook_command_run("/buffer %s" % channel_name, 'channel_switch_cb', buffer)


def buffer_switch_cb(data, signal, buffer):
    if buffer not in channel_buffers.values():
        return weechat.WEECHAT_RC_OK

    mark_channel_as_read(buffer)

    return weechat.WEECHAT_RC_OK

def channel_click_cb(data, info):
    if "wee-matter" != info.get("_buffer_localvar_script_name"):
        return info

    if info["_key"] != "button1":
        return

    if "post_id_" in info["_chat_line_tags"]:
        wee_matter.post.handle_post_click(data, info)
    elif "file_id_" in info["_chat_line_tags"]:
        wee_matter.file.handle_file_click(data, info)

def handle_multiline_message_cb(data, modifier, buffer, string):
    if buffer not in channel_buffers.values():
        return string

    if "\n" in string and not string[0] == "/":
        channel_input_cb(data, buffer, string)
        return ""

    return string
