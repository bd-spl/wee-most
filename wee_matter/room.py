
import weechat
import json
from wee_matter.server import get_servers, get_server_from_buffer
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
        ("parent_id", str),
        ("channel_id", str),
        ("message", str),
        ("date", int),
        ("deleted", bool),
        ("files", list),
        ("reactions", list),
        ("user", any),
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

def channel_completion_cb(data, completion_item, current_buffer, completion):
    servers = get_servers()
    for server in servers.values():
        weechat.hook_completion_list_add(completion, server.name, 0, weechat.WEECHAT_LIST_POS_SORT)
        for team in server.teams.values():
            for buffer in team.buffers:
                buffer_name = weechat.buffer_get_string(buffer, "short_name")
                weechat.hook_completion_list_add(completion, buffer_name, 0, weechat.WEECHAT_LIST_POS_SORT)

    return weechat.WEECHAT_RC_OK

def private_completion_cb(data, completion_item, current_buffer, completion):
    servers = get_servers()
    for server in servers.values():
        for buffer in server.buffers:
            buffer_name = weechat.buffer_get_string(buffer, "short_name")
            weechat.hook_completion_list_add(completion, buffer_name, 0, weechat.WEECHAT_LIST_POS_SORT)
    return weechat.WEECHAT_RC_OK

def channel_switch_cb(buffer, current_buffer, args):
    weechat.buffer_set(buffer, "display", "1")
    return weechat.WEECHAT_RC_OK_EAT

from wee_matter.http import (run_post_post, run_get_read_channel_posts,
                             run_get_channel_members, run_get_channel_posts_after,
                             run_post_user_post_unread, build_file_url)

def mark_channel_as_read(buffer):
    server = get_server_from_buffer(buffer)

    last_post_id = weechat.buffer_get_string(buffer, "localvar_last_post_id")
    last_read_post_id = weechat.buffer_get_string(buffer, "localvar_last_read_post_id")
    if last_post_id == last_read_post_id: # prevent spamming on buffer switch
        return

    run_post_user_post_unread(server.user.id, last_post_id, server, "singularity_cb", "")
    weechat.buffer_set(buffer, "localvar_set_last_read_post_id", last_post_id)

def colorize_sentence(sentence, color):
    return "{}{}{}".format(weechat.color(color), sentence, weechat.color("reset"))

def post_post_cb(buffer, command, rc, out, err):
    if rc != 0:
        weechat.prnt(buffer, "Can't send post")
        return weechat.WEECHAT_RC_ERROR

    return weechat.WEECHAT_RC_OK

def build_post_from_input_data(buffer, input_data):
    server = get_server_from_buffer(buffer)

    return Post(
        id= "",
        parent_id= "",
        channel_id= weechat.buffer_get_string(buffer, "localvar_channel_id"),
        message= input_data,
        date= 0,
        deleted= False,
        files= [],
        reactions= [],
        user= server.user,
    )

def room_input_cb(data, buffer, input_data):
    server = get_server_from_buffer(buffer)

    post = build_post_from_input_data(buffer, input_data)

    run_post_post(post, server, "post_post_cb", buffer)

    return weechat.WEECHAT_RC_OK

def handle_multiline_message_cb(data, modifier, buffer, string):
    if buffer not in channel_buffers.values():
        return string

    if "\n" in string and not string[0] == "/":
        room_input_cb(data, buffer, string)
        return ""

    return string

def build_reaction_message(reaction):
    return "[:{}:]".format(colorize_sentence(reaction.emoji_name, reaction.user.color))

def build_reaction_line(post):
    reaction_line = ""
    for reaction in post.reactions:
        reaction_line += " " + build_reaction_message(reaction)

    return reaction_line.strip()

def write_deleted_message_lines(buffer, post):
    first_initial_line_data = find_buffer_first_post_line_data(buffer, post.id)
    if not first_initial_line_data:
        return

    initial_message_prefix = weechat.hdata_string(weechat.hdata_get("line_data"), first_initial_line_data, "prefix")
    initial_message = weechat.hdata_string(weechat.hdata_get("line_data"), first_initial_line_data, "message").rsplit(' | ', 1)[0]
    weechat.prnt_date_tags(
        buffer,
        post.date,
        "deleted_post",
        initial_message_prefix + "	" + colorize_sentence(build_quote_message(initial_message), "red")
    )

def build_quote_message(message):
    if 69 < len(message):
        message = "%s…" % message[:69].strip()
    return "> %s" % message

def write_edited_message_lines(buffer, post):
    tags = "post_id_%s" % post.id

    first_initial_line_data = find_buffer_first_post_line_data(buffer, post.id)
    last_initial_line_data = find_buffer_last_post_line_data(buffer, post.id)
    if not first_initial_line_data or not last_initial_line_data:
        return

    initial_message_date = weechat.hdata_time(weechat.hdata_get("line_data"), first_initial_line_data, "date")
    initial_message_prefix = weechat.hdata_string(weechat.hdata_get("line_data"), first_initial_line_data, "prefix")

    initial_message = weechat.hdata_string(weechat.hdata_get("line_data"), first_initial_line_data, "message").rsplit(' | ', 1)[0]
    _, _, initial_reactions = weechat.hdata_string(weechat.hdata_get("line_data"), last_initial_line_data, "message").partition(' | ')
    initial_message = weechat.string_remove_color(initial_message, "")

    weechat.prnt_date_tags(
        buffer,
        initial_message_date,
        "edited_post",
        initial_message_prefix + "	" + colorize_sentence(build_quote_message(initial_message), "yellow")
    )

    if initial_reactions:
        new_message = post.message + " | " + initial_reactions
        tags += ",reactions"
    else:
        new_message = post.message

    weechat.prnt_date_tags(
        buffer,
        post.date,
        tags,
        colorize_sentence(post.user.username, post.user.color) + "	" + new_message
    )

def write_reply_message_lines(buffer, post):
    if not post.parent_id:
        return

    tags = "post_id_%s" % post.id

    parent_line_data = find_buffer_first_post_line_data(buffer, post.parent_id)
    if not parent_line_data:
        return

    parent_tags = get_line_data_tags(parent_line_data)
    parent_message_date = weechat.hdata_time(weechat.hdata_get("line_data"), parent_line_data, "date")
    parent_message_prefix = weechat.hdata_string(weechat.hdata_get("line_data"), parent_line_data, "prefix")
    if not "reactions" in parent_tags:
        parent_message = weechat.hdata_string(weechat.hdata_get("line_data"), parent_line_data, "message")
    else:
        parent_message = weechat.hdata_string(weechat.hdata_get("line_data"), parent_line_data, "message").rsplit(' | ', 1)[0]
    weechat.prnt_date_tags(
        buffer,
        parent_message_date,
        "quote",
        parent_message_prefix + "	" + colorize_sentence(build_quote_message(parent_message), "lightgreen")
    )

    parent_message_prefix = weechat.string_remove_color(parent_message_prefix, "")
    own_prefix = weechat.buffer_get_string(buffer, "localvar_nick")

    parent_post_id = find_post_id_in_tags(parent_tags)
    tags += ",reply_to_{}".format(parent_post_id)

    # if somebody (not us) reply to our post
    if parent_message_prefix == own_prefix and parent_message_prefix != post.user.username:
        tags += ",notify_highlight"

    if post.reactions:
        tags += ",reactions"
        weechat.prnt_date_tags(
            buffer,
            post.date,
            tags,
            colorize_sentence(post.user.username, post.user.color) + "	" + post.message + " | " + build_reaction_line(post)
        )
        return

    weechat.prnt_date_tags(
        buffer,
        post.date,
        tags,
        colorize_sentence(post.user.username, post.user.color) + "	" + post.message
    )

def write_message_lines(buffer, post):
    tags = "post_id_%s" % post.id
    if post.reactions:
        tags += ",reactions"
        weechat.prnt_date_tags(
            buffer,
            post.date,
            tags,
            colorize_sentence(post.user.username, post.user.color) + "	" + post.message + " | " + build_reaction_line(post)
        )
        return

    weechat.prnt_date_tags(
        buffer,
        post.date,
        tags,
        colorize_sentence(post.user.username, post.user.color) + "	" + post.message
    )

def write_file_lines(buffer, post):
    for file in post.files:
        weechat.prnt_date_tags(
            buffer,
            post.date,
            "file_line",
            "	[{}]({})".format(file.name, file.url)
        )

def write_post(post):
    buffer_name = build_buffer_channel_name(post.channel_id)
    buffer = weechat.buffer_search("", buffer_name)
    server = get_server_from_buffer(buffer)

    if post.deleted:
        write_deleted_message_lines(buffer, post)
    elif post.id in post_buffers:
        write_edited_message_lines(buffer, post)
    elif post.parent_id:
        write_reply_message_lines(buffer, post)
    else:
        write_message_lines(buffer, post)
    write_file_lines(buffer, post)

    weechat.buffer_set(buffer, "localvar_set_last_post_id", post.id)
    post_buffers[post.id] = buffer

def get_files_from_post_data(post_data, server):
    if "files" in post_data["metadata"]:
        files = []
        for file_data in post_data["metadata"]["files"]:
            files.append(
                File(
                    id= file_data["id"],
                    name= file_data["name"],
                    url= build_file_url(file_data["id"], server)
                )
            )
        return files

    return []

def get_reaction_from_reaction_data(reaction_data, server):
    if reaction_data["user_id"] not in server.users:
        weechat.prnt("", "User not found in server")
        return
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
            reaction = get_reaction_from_reaction_data(reaction_data, server)
            if not reaction:
                continue
            reactions.append(reaction)
        return reactions

    return []

def get_post_from_post_data(post_data):
    buffer_name = build_buffer_channel_name(post_data["channel_id"])
    buffer = weechat.buffer_search("", buffer_name)
    if not buffer:
        weechat.prnt("", "Channel not found in server")
        return

    server = get_server_from_buffer(buffer)

    if post_data["user_id"] not in server.users:
        weechat.prnt("", "User not found in server")
        return

    user = server.users[post_data["user_id"]]

    post = Post(
        id= post_data["id"],
        parent_id= post_data["parent_id"],
        channel_id= post_data["channel_id"],
        message= post_data["message"],
        date= int(post_data["update_at"]/1000),
        deleted= False,
        files= get_files_from_post_data(post_data, server),
        reactions= get_reactions_from_post_data(post_data, server),
        user= user,
    )

    return post

def hidrate_room_posts_cb(buffer, command, rc, out, err):
    if rc != 0:
        weechat.prnt("", "An error occured when hidrating room")
        return weechat.WEECHAT_RC_ERROR

    server = get_server_from_buffer(buffer)

    response = json.loads(out)

    response["order"].reverse()
    for post_id in response["order"]:
        post = get_post_from_post_data(response["posts"][post_id])
        write_post(post)

    if "" != response["next_post_id"]:
        run_get_channel_posts_after(post.id, post.channel_id, server, "hidrate_room_posts_cb", buffer)

    return weechat.WEECHAT_RC_OK

def hidrate_room_read_posts_cb(buffer, command, rc, out, err):
    if rc != 0:
        weechat.prnt("", "An error occured when hidrating room")
        return weechat.WEECHAT_RC_ERROR

    server = get_server_from_buffer(buffer)

    response = json.loads(out)

    response["order"].reverse()
    for post_id in response["order"]:
        post = get_post_from_post_data(response["posts"][post_id])
        write_post(post)

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

def create_room_user_from_user_data(user_data, buffer, server):
    if user_data["user_id"] not in server.users:
        weechat.prnt("", "User not found in server")
        return

    user = server.users[user_data["user_id"]]

    for role in user_data["roles"].split():
        group_name = role.replace("channel_", "")
        group = create_room_group(group_name, buffer)

        weechat.nicklist_add_nick(buffer, group, user.username, user.color, "@", user.color, 1)

def hidrate_room_users_cb(buffer, command, rc, out, err):
    if rc != 0:
        weechat.prnt("", "An error occured when hidrating room users")
        return weechat.WEECHAT_RC_ERROR

    response = json.loads(out)

    server = get_server_from_buffer(buffer)

    for user_data in response:
        create_room_user_from_user_data(user_data, buffer, server)

    return weechat.WEECHAT_RC_OK

def hidrate_room_user_cb(buffer, command, rc, out, err):
    if rc != 0:
        weechat.prnt("", "An error occured when hidrating room user")
        return weechat.WEECHAT_RC_ERROR

    user_data = json.loads(out)

    server = get_server_from_buffer(buffer)

    create_room_user_from_user_data(user_data, buffer, server)

    return weechat.WEECHAT_RC_OK

def build_buffer_channel_name(channel_id):
    return "weematter." + channel_id

def build_room_name_from_channel_data(channel_data, server):
    room_name = channel_data["name"]
    if "" != channel_data["display_name"]:
        room_name = channel_data["display_name"]
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

    run_get_read_channel_posts(server.user.id, channel_data["id"], server, "hidrate_room_read_posts_cb", buffer)
    run_get_channel_members(channel_data["id"], server, "hidrate_room_users_cb", buffer)

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

    for tag in tags:
        if tag.startswith(post_id_tag):
            return True

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

def find_buffer_first_post_line_data(buffer, post_id):
    lines = weechat.hdata_pointer(weechat.hdata_get("buffer"), buffer, "lines")
    line = weechat.hdata_pointer(weechat.hdata_get("lines"), lines, "first_line")

    line_data = weechat.hdata_pointer(weechat.hdata_get("line"), line, "data")
    while True:
        if is_post_line_data(line_data, post_id):
            return line_data
        line = weechat.hdata_pointer(weechat.hdata_get("line"), line, "next_line")
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
    else:
        new_message = old_message + " | " + build_reaction_message(reaction)
        tags.append("reactions")

    weechat.hdata_update(
        weechat.hdata_get("line_data"),
        line_data,
        {
            "message": new_message,
            "tags_array": ",".join(tags)
        }
    )

def remove_reaction_from_post(buffer, reaction):
    line_data = find_buffer_last_post_line_data(buffer, reaction.post_id)

    if None == line_data:
        return

    tags = get_line_data_tags(line_data)
    if not "reactions" in tags:
        return

    old_message, _, old_reactions = weechat.hdata_string(weechat.hdata_get("line_data"), line_data, "message").partition(' | ')


    reaction_message = build_reaction_message(reaction)
    new_reactions = old_reactions.replace(reaction_message, "", 1).replace("  ", " ").strip()

    if "" == new_reactions:
        tags.remove("reactions")
        new_message = old_message
    else:
        new_message = old_message + " | " + new_reactions

    weechat.hdata_update(
        weechat.hdata_get("line_data"),
        line_data,
        {
            "message": new_message,
            "tags_array": ",".join(tags),
        }
    )

def short_post_id(post_id):
    return post_id[:4]

def find_full_post_id(buffer, short_post_id):
    line_data = find_buffer_last_post_line_data(buffer, short_post_id)
    if None == line_data:
        return

    tags = get_line_data_tags(line_data)
    return find_post_id_in_tags(tags)

def find_post_id_in_tags(tags):
    for tag in tags:
        if tag.startswith("post_id_"):
            return tag[8:]

def find_reply_to_in_tags(tags):
    for tag in tags:
        if tag.startswith("reply_to_"):
            return tag[9:]

def handle_post_click(data, info):
    tags = info["_chat_line_tags"].split(",")

    post_id = find_post_id_in_tags(tags)
    if not post_id:
        return

    buffer = info["_buffer"]

    old_input = weechat.buffer_get_string(buffer, "input")
    old_position = weechat.buffer_get_integer(buffer, "input_pos")

    before_position_message = old_input[:old_position]
    after_position_message = old_input[old_position:]

    post_id = short_post_id(post_id)
    if len(old_input) == old_position: # add whitespace smartly
        post_id += " "
    new_input = before_position_message + post_id + after_position_message

    weechat.buffer_set(buffer, "input", new_input)

    new_position = old_position + len(post_id)
    weechat.buffer_set(buffer, "input_pos", str(new_position))

def channel_click_cb(data, info):
    if not "_buffer_localvar_script_name" in info or "wee-matter" != info["_buffer_localvar_script_name"]:
        return info

    handle_post_click(data, info)

