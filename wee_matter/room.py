
import weechat
import json
from wee_matter.server import get_server
from typing import NamedTuple
import re

room_buffers = []

Post = NamedTuple(
    "Post",
    [
        ("channel_id", str),
        ("message", str),
    ]
)

from wee_matter.http import (run_post_post, run_get_channel_posts,
                             run_get_read_channel_posts, run_get_channel_members,
                             run_get_channel_posts_after)

def color_for_username(username):
    nick_colors = weechat.config_string(
         weechat.config_get("weechat.color.chat_nick_colors")
    ).split(",")
    nick_color_count = len(nick_colors)
    color_id = hash(username) % nick_color_count

    color = nick_colors[color_id]

    return color

def colorize_sentence(sentence, color):
    return "{}{}{}".format(weechat.color(color), sentence, weechat.color("reset"))

def post_post_cb(buffer, command, rc, out, err):
    if rc != 0:
        weechat.prnt(buffer, "Can't send post")
        return weechat.WEECHAT_RC_ERROR

    return weechat.WEECHAT_RC_OK

def room_input_cb(data, buffer, input_data):
    server_name = weechat.buffer_get_string(buffer, "localvar_server_name")
    server = get_server(server_name)

    post = Post(
        channel_id= weechat.buffer_get_string(buffer, "localvar_channel_id"),
        message= input_data,
    )

    run_post_post(post, server, "post_post_cb", buffer)

    return weechat.WEECHAT_RC_OK

def handle_multiline_message_cb(data, modifier, buffer, string):
    if buffer not in room_buffers:
        return string

    if "\n" in string and not string[0] == "/":
        room_input_cb("EVENTROUTER", buffer, string)
        return ""
    return string

def write_post(buffer, username, message, date):
    server_name = weechat.buffer_get_string(buffer, "localvar_server_name")
    server = get_server(server_name)

    if username == server.user_name:
        username_color = weechat.config_string(
             weechat.config_get("weechat.color.chat_nick_self")
        )
    else:
        username_color = color_for_username(username)

    weechat.prnt_date_tags(buffer, date, "", colorize_sentence(username, username_color) + "	" + message)

def hidrate_room_posts_cb(buffer, command, rc, out, err):
    if rc != 0:
        weechat.prnt("", "An error occured when hidrating room")
        weechat.prnt("", err)

        return weechat.WEECHAT_RC_ERROR

    server_name = weechat.buffer_get_string(buffer, "localvar_server_name")
    server = get_server(server_name)

    response = json.loads(out)

    response["order"].reverse()
    for post_id in response["order"]:
        post = response["posts"][post_id]
        message = post["message"]
        username = post["user_id"]
        if username in server.users:
            username = server.users[username].username
        write_post(buffer, username, message, int(post["create_at"]/1000))

    if "" != response["next_post_id"]:
        channel_id = weechat.buffer_get_string(buffer, "localvar_channel_id"),
        run_get_channel_posts_after(response["next_post_id"], channel_id[0], server, "hidrate_room_posts_cb", buffer)

    return weechat.WEECHAT_RC_OK

def hidrate_room_read_posts_cb(buffer, command, rc, out, err):
    if rc != 0:
        weechat.prnt("", "An error occured when hidrating room")
        weechat.prnt("", err)

        return weechat.WEECHAT_RC_ERROR

    server_name = weechat.buffer_get_string(buffer, "localvar_server_name")
    server = get_server(server_name)

    response = json.loads(out)

    response["order"].reverse()
    for post_id in response["order"]:
        post = response["posts"][post_id]
        message = post["message"]
        username = post["user_id"]
        if username in server.users:
            username = server.users[username].username
        write_post(buffer, username, message, int(post["create_at"]/1000))

    weechat.buffer_set(buffer, "unread", "-")
    weechat.buffer_set(buffer, "hotlist", "-1")

    if "" != response["next_post_id"]:
        channel_id = weechat.buffer_get_string(buffer, "localvar_channel_id"),
        run_get_channel_posts_after(response["next_post_id"], channel_id[0], server, "hidrate_room_posts_cb", buffer)

    return weechat.WEECHAT_RC_OK

def create_room_group(group_name, buffer):
    group = weechat.nicklist_search_group(buffer, "", group_name)
    if not group:
        weechat.nicklist_add_group(buffer, "", group_name, "", 1)

    return group

def create_room_user(user_data, buffer, server):
    for role in user_data["roles"].split():
        group_name = role.replace("channel_", "")
        group = create_room_group(group_name, buffer)

        username = user_data["user_id"]
        if username in server.users:
            username = server.users[username].username

        prefix_color = weechat.config_string(
             weechat.config_get("weechat.color.chat_nick_prefix")
        )

        if username == server.user_name:
            username_color = weechat.config_string(
                 weechat.config_get("weechat.color.chat_nick_self")
            )
        else:
            username_color = color_for_username(username)

        weechat.nicklist_add_nick(buffer, group, username, username_color, "@", prefix_color, 1)

def hidrate_room_users_cb(buffer, command, rc, out, err):
    if rc != 0:
        weechat.prnt("", "An error occured when hidrating room users")
        return weechat.WEECHAT_RC_ERROR

    response = json.loads(out)

    server_name = weechat.buffer_get_string(buffer, "localvar_server_name")
    server = get_server(server_name)

    for user in response:
        create_room_user(user, buffer, server)

    return weechat.WEECHAT_RC_OK

def build_buffer_room_name(channel_id):
    return "weematter." + channel_id

def build_room_name(room_data, server):
    room_name = room_data["name"]
    if "" != room_data["display_name"]:
        room_name = room_data["display_name"]
    else:
        match = re.match('(\w+)__(\w+)', room_data["name"])
        if match:
            room_name = server.users[match.group(1)].username
            if room_name == server.user_name:
                room_name = server.users[match.group(2)].username

    return room_name

def create_room(room_data, server):
    buffer_name = build_buffer_room_name(room_data["id"])
    buffer = weechat.buffer_new(buffer_name, "room_input_cb", "", "", "")
    room_buffers.append(buffer)

    weechat.buffer_set(buffer, "localvar_set_server_name", server.name)
    weechat.buffer_set(buffer, "localvar_set_channel_id", room_data["id"])

    weechat.buffer_set(buffer, "nicklist", "1")

    weechat.buffer_set(buffer, "short_name", build_room_name(room_data, server))

    weechat.buffer_set(buffer, "highlight_words", "@{},{},@here".format(server.user_name, server.user_name))
    weechat.buffer_set(buffer, "localvar_set_nick", server.user_name)

    if room_data["team_id"]:
        team = server.teams[room_data["team_id"]]

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

    run_get_read_channel_posts(server.user_id, room_data["id"], server, "hidrate_room_read_posts_cb", buffer)
    run_get_channel_members(room_data["id"], server, "hidrate_room_users_cb", buffer)

