
import weechat
import json
from wee_matter.server import get_server
from typing import NamedTuple
import re

channel_buffers = {}

def get_buffer_from_channel_id(channel_id):
    if channel_id not in channel_buffers:
        return

    return channel_buffers[channel_id]

post_buffers = {}

def get_buffer_from_post_id(post_id):
    if post_id not in post_buffers:
        return

    return post_buffers[post_id]


Post = NamedTuple(
    "Post",
    [
        ("id", str),
        ("user_name", str),
        ("channel_id", str),
        ("message", str),
        ("date", int),
        ("files", list),
        ("reactions", list),
    ]
)

File = NamedTuple(
    "File",
    [
        ("id", str),
        ("name", str),
        ("url", str),
    ]
)

Reaction = NamedTuple(
    "Reaction",
    [
        ("user", any),
        ("emoji_name", str),
        ("post_id", str),
    ]
)

from wee_matter.http import (run_post_post, run_get_read_channel_posts,
                             run_get_channel_members, run_get_channel_posts_after,
                             run_post_user_post_unread, run_get_file_public_link,
                             build_file_url)

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
        files= [],
        reactions= [],
    )

    run_post_post(post, server, "post_post_cb", buffer)

    return weechat.WEECHAT_RC_OK

def handle_multiline_message_cb(data, modifier, buffer, string):
    if buffer not in channel_buffers.values():
        return string

    if "\n" in string and not string[0] == "/":
        room_input_cb("EVENTROUTER", buffer, string)
        return ""
    return string

def append_file_public_link_to_post_cb(data, command, rc, out, err):
    if rc != 0:
        weechat.prnt("", "An error occured when appending file to post")
        return weechat.WEECHAT_RC_ERROR

    response = json.loads(out)

    buffer = data.split("|")[0]
    post_id = data.split("|")[1]

    line_data = find_buffer_last_post_line_data(buffer, post_id)

    old_message = weechat.hdata_string(weechat.hdata_get("line_data"), line_data, "message")
    new_message = old_message + "[{}]".format(response["link"])

    weechat.hdata_update(
        weechat.hdata_get("line_data"),
        line_data,
        {
            "message": new_message
        }
    )

    return weechat.WEECHAT_RC_OK

def build_reaction_message(reaction):
    return "[:{}:]".format(reaction.emoji_name)

def build_reaction_line(post):
    reaction_line = ""
    for reaction in post.reactions:
        reaction_line += " " + build_reaction_message(reaction)

    return reaction_line.strip()

def write_message_lines(buffer, post, username_color):
    if not post.reactions:
        weechat.prnt_date_tags(
            buffer,
            post.date,
            "post_id_%s" % post.id,
            colorize_sentence(post.user_name, username_color) + "	" + post.message
        )
        return

    weechat.prnt_date_tags(
        buffer,
        post.date,
        "post_id_%s,reactions" % post.id,
        colorize_sentence(post.user_name, username_color) + "	" + post.message + " | " + build_reaction_line(post)
    )

def write_file_lines(buffer, post):
    for file in post.files:
        weechat.prnt_date_tags(
            buffer,
            post.date,
            "file_line",
            "	[{}]({})".format(file.name, file.url)
        )

def write_post(buffer, post):
    server_name = weechat.buffer_get_string(buffer, "localvar_server_name")
    server = get_server(server_name)

    if post.user_name == server.user_name:
        username_color = weechat.config_string(
             weechat.config_get("weechat.color.chat_nick_self")
        )
    else:
        username_color = color_for_username(post.user_name)

    write_message_lines(buffer, post, username_color)
    write_file_lines(buffer, post)

    weechat.buffer_set(buffer, "localvar_set_last_post_id", post.id)
    post_buffers[post.id] = buffer

def get_files_from_post_data(post_data, server):
    if "files" in post_data["metadata"]:
        files = []
        for file_data in post_data["metadata"]["files"]:
            files.append(File(
                id= file_data["id"],
                name= file_data["name"],
                url= build_file_url(file_data["id"], server)
            ))
        return files

    return []

def get_reaction_from_reaction_data(reaction_data, server):
    user = None
    if reaction_data["user_id"] in server.users:
        user = server.users[reaction_data["user_id"]]

    return Reaction(
        user= user,
        emoji_name= reaction_data["emoji_name"],
        post_id= reaction_data["post_id"],
    )

def get_reactions_from_post_data(post_data, server):
    if "reactions" in post_data["metadata"]:
        reactions = []
        for reaction_data in post_data["metadata"]["reactions"]:
            reactions.append(get_reaction_from_reaction_data(reaction_data, server))
        return reactions

    return []

def write_post_from_post_data(post_data):
    buffer_name = build_buffer_room_name(post_data["channel_id"])
    buffer = weechat.buffer_search("", buffer_name)

    server_name = weechat.buffer_get_string(buffer, "localvar_server_name")
    server = get_server(server_name)

    username = post_data["user_id"]
    if username in server.users:
        username = server.users[username].username

    post = Post(
        id= post_data["id"],
        user_name= username,
        channel_id= post_data["channel_id"],
        message= post_data["message"],
        date= int(post_data["create_at"]/1000),
        files= get_files_from_post_data(post_data, server),
        reactions= get_reactions_from_post_data(post_data, server),
    )

    write_post(buffer, post)

    return post

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
        post = write_post_from_post_data(response["posts"][post_id])

    if "" != response["next_post_id"]:
        run_get_channel_posts_after(post.id, post.channel_id, server, "hidrate_room_posts_cb", buffer)

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
        post = write_post_from_post_data(response["posts"][post_id])

    weechat.buffer_set(buffer, "localvar_set_last_read_post_id", post.id)
    weechat.buffer_set(buffer, "unread", "-")
    weechat.buffer_set(buffer, "hotlist", "-1")

    if "" != response["next_post_id"]:
        run_get_channel_posts_after(post.id, post.channel_id, server, "hidrate_room_posts_cb", buffer)

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
    channel_buffers[room_data["id"]] = buffer

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
    if buffer not in channel_buffers.values():
        return weechat.WEECHAT_RC_OK

    mark_channel_as_read(buffer)

    return weechat.WEECHAT_RC_OK

def get_line_data_tags(line_data):
    tags = []

    tags_count = weechat.hdata_integer(weechat.hdata_get("line_data"), line_data, "tags_count")
    for i in range(tags_count):
        tag = weechat.hdata_string(weechat.hdata_get("line_data"), line_data, '{}|tags_array'.format(i))
        tags.append(tag)

    return tags

def is_post_line_data(line_data, post_id):
    post_id_tag = "post_id_{}".format(post_id)
    tags = get_line_data_tags(line_data)

    return post_id_tag in tags

def find_buffer_last_post_line_data(buffer, post_id):
    lines = weechat.hdata_pointer(weechat.hdata_get("buffer"), buffer, "lines")
    line = weechat.hdata_pointer(weechat.hdata_get("lines"), lines, "last_line")

    line_data = weechat.hdata_pointer(weechat.hdata_get("line"), line, "data")
    while True:
        if is_post_line_data(line_data, post_id):
            return line_data
        line = weechat.hdata_pointer(weechat.hdata_get("line"), line, "prev_line")
        if "" == line:
            break
        line_data = weechat.hdata_pointer(weechat.hdata_get("line"), line, "data")

def add_reaction_to_post(buffer, reaction):
    line_data = find_buffer_last_post_line_data(buffer, reaction.post_id)

    if None == line_data:
        return

    tags = get_line_data_tags(line_data)
    old_message = weechat.hdata_string(weechat.hdata_get("line_data"), line_data, "message")

    if "reactions" in tags:
        new_message = old_message + " " + build_reaction_message(reaction)
        weechat.hdata_update(
            weechat.hdata_get("line_data"),
            line_data,
            {
                "message": new_message.strip(),
            }
        )
        return

    tags.append("reactions")

    new_message = old_message + " | " + build_reaction_message(reaction)
    weechat.hdata_update(
        weechat.hdata_get("line_data"),
        line_data,
        {
            "message": new_message.strip(),
            "tags_array": ",".join(tags)
        }
    )

def remove_reaction_from_post(buffer, reaction):
    line_data = find_buffer_last_post_line_data(buffer, reaction.post_id)

    if None == line_data:
        return

    tags = get_line_data_tags(line_data)
    weechat.prnt("", str(tags))
    if not "reactions" in tags:
        return

    old_message, old_reactions = weechat.hdata_string(weechat.hdata_get("line_data"), line_data, "message").rsplit(' | ', 1)

    reaction_message = build_reaction_message(reaction)

    new_reactions = old_reactions.replace(reaction_message, "").replace("  ", " ").strip()

    if "" == new_reactions:
        tags.remove("reactions")
        weechat.hdata_update(
            weechat.hdata_get("line_data"),
            line_data,
            {
                "message": old_message,
                "tags_array": ",".join(tags),
            }
        )
    else:
        weechat.hdata_update(
            weechat.hdata_get("line_data"),
            line_data,
            {
                "message": old_message + " | " + new_reactions,
            }
        )
