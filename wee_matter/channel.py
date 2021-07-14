
import weechat
import json
import wee_matter
import re
from wee_matter.globals import (config, servers)

channel_buffers = {}
hydrating_buffers = []

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

def build_buffer_channel_name(channel_id):
    return "weematter." + channel_id

def channel_switch_cb(buffer, current_buffer, args):
    weechat.buffer_set(buffer, "display", "1")
    return weechat.WEECHAT_RC_OK_EAT

def private_completion_cb(data, completion_item, current_buffer, completion):
    for server in servers.values():
        for buffer in server.buffers:
            buffer_name = weechat.buffer_get_string(buffer, "short_name")
            weechat.hook_completion_list_add(completion, buffer_name, 0, weechat.WEECHAT_LIST_POS_SORT)
    return weechat.WEECHAT_RC_OK

def channel_completion_cb(data, completion_item, current_buffer, completion):
    for server in servers.values():
        weechat.hook_completion_list_add(completion, server.id, 0, weechat.WEECHAT_LIST_POS_SORT)
        for team in server.teams.values():
            for buffer in team.buffers:
                buffer_name = weechat.buffer_get_string(buffer, "short_name")
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

def create_channel_group(group_name, buffer):
    group = weechat.nicklist_search_group(buffer, "", group_name)
    if not group:
        weechat.nicklist_add_group(buffer, "", group_name, "", 1)

    return group

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

CHANNEL_TYPES = {
    "D": "direct",
    "G": "group",
    "O": "public", # ordinary
    "P": "private",
}

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
    buffer_name = build_buffer_channel_name(channel_data["id"])
    buffer = weechat.buffer_new(buffer_name, "channel_input_cb", "", "", "")
    channel_buffers[channel_data["id"]] = buffer

    weechat.buffer_set(buffer, "localvar_set_server_id", server.id)
    weechat.buffer_set(buffer, "localvar_set_channel_id", channel_data["id"])

    weechat.buffer_set(buffer, "nicklist", "1")

    set_channel_properties_from_channel_data(channel_data, server)

    weechat.buffer_set(buffer, "highlight_words", "@{0},{0},@here,@channel,@all".format(server.me.username))
    weechat.buffer_set(buffer, "localvar_set_nick", server.me.username)

    if channel_data["team_id"]:
        team = server.teams[channel_data["team_id"]]

        weechat.buffer_set(buffer, "localvar_set_type", "channel")

        team.buffers.append(buffer)
    else:
        weechat.buffer_set(buffer, "localvar_set_type", "private")

        server.buffers.append(buffer)

    register_buffer_hydratating(channel_data["id"])
    wee_matter.http.enqueue_request(
        "run_get_read_channel_posts",
        server.me.id, channel_data["id"], server, "hydrate_channel_read_posts_cb", buffer
    )
    wee_matter.http.enqueue_request(
        "run_get_channel_members",
        channel_data["id"], server, "hydrate_channel_users_cb", buffer
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
