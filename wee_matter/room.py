
import weechat
import json
from wee_matter.server import get_server
from typing import NamedTuple
import re

room_buffers = []

Post = NamedTuple(
    "Post",
    [
        ("id", str),
        ("user_name", str),
        ("channel_id", str),
        ("message", str),
        ("date", int)
    ]
)

from wee_matter.http import (run_post_post, run_get_channel_posts,
                             run_get_read_channel_posts, run_get_channel_members,
                             run_get_channel_posts_after, run_post_user_post_unread)

def mark_channel_as_read(buffer):
    server_name = weechat.buffer_get_string(buffer, "localvar_server_name")
    server = get_server(server_name)

    last_post_id = weechat.buffer_get_string(buffer, "localvar_last_post_id")
    last_read_post_id = weechat.buffer_get_string(buffer, "localvar_last_read_post_id")
    if last_post_id == last_read_post_id:
        return

    run_post_user_post_unread(server.user_id, last_post_id, server, "singularity_cb", "")
    weechat.buffer_set(buffer, "localvar_set_last_read_post_id", last_post_id)

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
        id= "",
        user_name= server.user_name,
        channel_id= weechat.buffer_get_string(buffer, "localvar_channel_id"),
        message= input_data,
        date= 0,
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

def write_post(buffer, post):
    server_name = weechat.buffer_get_string(buffer, "localvar_server_name")
    server = get_server(server_name)

    if post.user_name == server.user_name:
        username_color = weechat.config_string(
             weechat.config_get("weechat.color.chat_nick_self")
        )
    else:
        username_color = color_for_username(post.user_name)

    tags = "post_id_%s" % post.id

    weechat.prnt_date_tags(buffer, post.date, tags, colorize_sentence(post.user_name, username_color) + "	" + post.message)
    weechat.buffer_set(buffer, "localvar_set_last_post_id", post.id)

def hidrate_room_posts_cb(buffer, command, rc, out, err):
    if rc != 0:
        weechat.prnt("", "An error occured when hidrating room")
        weechat.prnt("", err)

        return weechat.WEECHAT_RC_ERROR

    server_name = weechat.buffer_get_string(buffer, "localvar_server_name")
    server = get_server(server_name)
    channel_id = weechat.buffer_get_string(buffer, "localvar_channel_id"),

    response = json.loads(out)

    response["order"].reverse()
    for post_id in response["order"]:
        post = response["posts"][post_id]

        username = post["user_id"]
        if username in server.users:
            username = server.users[username].username

        post = Post(
            id= post_id,
            user_name= username,
            channel_id= channel_id,
            message= post["message"],
            date= int(post["create_at"]/1000),
        )

        write_post(buffer, post)

    if "" != response["next_post_id"]:
        run_get_channel_posts_after(post.id, channel_id[0], server, "hidrate_room_posts_cb", buffer)

    return weechat.WEECHAT_RC_OK

def hidrate_room_read_posts_cb(buffer, command, rc, out, err):
    if rc != 0:
        weechat.prnt("", "An error occured when hidrating room")
        weechat.prnt("", err)

        return weechat.WEECHAT_RC_ERROR

    server_name = weechat.buffer_get_string(buffer, "localvar_server_name")
    server = get_server(server_name)
    channel_id = weechat.buffer_get_string(buffer, "localvar_channel_id"),

    response = json.loads(out)

    response["order"].reverse()
    for post_id in response["order"]:
        post = response["posts"][post_id]

        username = post["user_id"]
        if username in server.users:
            username = server.users[username].username

        post = Post(
            id= post_id,
            user_name= username,
            channel_id= channel_id,
            message= post["message"],
            date= int(post["create_at"]/1000),
        )

        write_post(buffer, post)

    weechat.buffer_set(buffer, "localvar_set_last_read_post_id", post.id)
    weechat.buffer_set(buffer, "unread", "-")
    weechat.buffer_set(buffer, "hotlist", "-1")

    if "" != response["next_post_id"]:
        run_get_channel_posts_after(post.id, channel_id[0], server, "hidrate_room_posts_cb", buffer)

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

def buffer_switch_cb(data, signal, buffer):
    if buffer not in room_buffers:
        return weechat.WEECHAT_RC_OK

    mark_channel_as_read(buffer)

    return weechat.WEECHAT_RC_OK

