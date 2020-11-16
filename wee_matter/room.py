
import weechat
import json
import wee_matter
import re

channel_buffers = {}

def get_buffer_from_channel_id(channel_id):
    return channel_buffers[channel_id]

def build_buffer_channel_name(channel_id):
    return "weematter." + channel_id

def colorize_sentence(sentence, color):
    return "{}{}{}".format(weechat.color(color), sentence, weechat.color("reset"))


def channel_switch_cb(buffer, current_buffer, args):
    weechat.buffer_set(buffer, "display", "1")
    return weechat.WEECHAT_RC_OK_EAT

def private_completion_cb(data, completion_item, current_buffer, completion):
    servers = wee_matter.server.get_servers()
    for server in servers.values():
        for buffer in server.buffers:
            buffer_name = weechat.buffer_get_string(buffer, "short_name")
            weechat.hook_completion_list_add(completion, buffer_name, 0, weechat.WEECHAT_LIST_POS_SORT)
    return weechat.WEECHAT_RC_OK

def channel_completion_cb(data, completion_item, current_buffer, completion):
    servers = wee_matter.server.get_servers()
    for server in servers.values():
        weechat.hook_completion_list_add(completion, server.name, 0, weechat.WEECHAT_LIST_POS_SORT)
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
    if last_post_id == last_read_post_id: # prevent spamming on buffer switch
        return

    wee_matter.http.run_post_channel_view(server.user.id, channel_id, server, "singularity_cb", "")

    weechat.buffer_set(buffer, "localvar_set_last_read_post_id", last_post_id)

def room_input_cb(data, buffer, input_data):
    server = wee_matter.server.get_server_from_buffer(buffer)

    builded_post = wee_matter.post.build_post_from_input_data(buffer, input_data)

    wee_matter.http.run_post_post(builded_post, server, "post_post_cb", buffer)

    return weechat.WEECHAT_RC_OK

def hydrate_room_posts_cb(buffer, command, rc, out, err):
    if rc != 0:
        weechat.prnt("", "An error occurred while hydrating room")
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
            builded_post.id, builded_post.channel_id, server, "hydrate_room_posts_cb", buffer
        )

    return weechat.WEECHAT_RC_OK

def hydrate_room_read_posts_cb(buffer, command, rc, out, err):
    if rc != 0:
        weechat.prnt("", "An error occurred while hydrating room")
        return weechat.WEECHAT_RC_ERROR

    server = wee_matter.server.get_server_from_buffer(buffer)

    response = json.loads(out)

    if not response["order"]:
        return weechat.WEECHAT_RC_OK

    response["order"].reverse()
    for post_id in response["order"]:
        post = wee_matter.post.build_post_from_post_data(response["posts"][post_id])
        wee_matter.post.write_post(post)

    weechat.buffer_set(buffer, "localvar_set_last_read_post_id", post.id)
    weechat.buffer_set(buffer, "unread", "-")
    weechat.buffer_set(buffer, "hotlist", "-1")

    if "" != response["next_post_id"]:
        wee_matter.http.enqueue_request(
            "run_get_channel_posts_after",
            post.id, post.channel_id, server, "hydrate_room_posts_cb", buffer
        )

    return weechat.WEECHAT_RC_OK

def create_room_group(group_name, buffer):
    group = weechat.nicklist_search_group(buffer, "", group_name)
    if not group:
        weechat.nicklist_add_group(buffer, "", group_name, "", 1)

    return group

def create_room_user_from_user_data(user_data, buffer, server):
    user = server.users[user_data["user_id"]]

    weechat.nicklist_add_nick(buffer, "", user.username, user.color, "@", user.color, 1)

def hydrate_room_users_cb(buffer, command, rc, out, err):
    if rc != 0:
        weechat.prnt("", "An error occurred while hydrating room users")
        return weechat.WEECHAT_RC_ERROR

    response = json.loads(out)

    server = wee_matter.server.get_server_from_buffer(buffer)

    for user_data in response:
        create_room_user_from_user_data(user_data, buffer, server)

    return weechat.WEECHAT_RC_OK

def hydrate_room_user_cb(buffer, command, rc, out, err):
    if rc != 0:
        weechat.prnt("", "An error occurred while hydrating room user")
        return weechat.WEECHAT_RC_ERROR

    user_data = json.loads(out)

    server = wee_matter.server.get_server_from_buffer(buffer)

    create_room_user_from_user_data(user_data, buffer, server)

    return weechat.WEECHAT_RC_OK

def remove_room_user(buffer, user):
    nick = weechat.nicklist_search_nick(buffer, "", user.username)
    weechat.nicklist_remove_nick(buffer, nick)

FORMATS = {
    "O": "~{}",
    "P": "(~{})",
}
def build_room_name_from_channel_data(channel_data, server):
    room_name = channel_data["name"]
    if "" != channel_data["display_name"]:
        formt = FORMATS.get(channel_data["type"], "{}")
        room_name = formt.format(channel_data["display_name"])
    else:
        match = re.match('(\w+)__(\w+)', channel_data["name"])
        if match:
            room_name = server.users[match.group(1)].username
            if room_name == server.user.username:
                room_name = server.users[match.group(2)].username

    return room_name

def create_room_from_channel_data(channel_data, server):
    buffer_name = build_buffer_channel_name(channel_data["id"])
    buffer = weechat.buffer_new(buffer_name, "room_input_cb", "", "", "")
    channel_buffers[channel_data["id"]] = buffer

    weechat.buffer_set(buffer, "localvar_set_server_name", server.name)
    weechat.buffer_set(buffer, "localvar_set_channel_id", channel_data["id"])

    weechat.buffer_set(buffer, "nicklist", "1")

    room_name = build_room_name_from_channel_data(channel_data, server)
    weechat.buffer_set(buffer, "short_name", room_name)
    weechat.hook_command_run("/buffer %s" % room_name, 'channel_switch_cb', buffer)

    weechat.buffer_set(buffer, "highlight_words", "@{},{},@here".format(server.user.username, server.user.username))
    weechat.buffer_set(buffer, "localvar_set_nick", server.user.username)

    if channel_data["team_id"]:
        team = server.teams[channel_data["team_id"]]

        weechat.buffer_set(buffer, "localvar_set_type", "channel")
        weechat.buffer_set(buffer, "localvar_set_server", team.display_name)

        parent_number = weechat.buffer_get_integer(team.buffer, "number")
        number = parent_number + 1 + len(team.buffers)

        team.buffers.append(buffer)
    else:
        weechat.buffer_set(buffer, "localvar_set_type", "private")
        weechat.buffer_set(buffer, "localvar_set_server", server.name)

        parent_number = weechat.buffer_get_integer(server.buffer, "number")
        number = parent_number + 1 + len(server.buffers)

        server.buffers.append(buffer)

    weechat.buffer_set(buffer, "number", str(number))

    wee_matter.http.enqueue_request(
        "run_get_read_channel_posts",
        server.user.id, channel_data["id"], server, "hydrate_room_read_posts_cb", buffer
    )
    wee_matter.http.enqueue_request(
        "run_get_channel_members",
        channel_data["id"], server, "hydrate_room_users_cb", buffer
    )

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
        room_input_cb(data, buffer, string)
        return ""

    return string
