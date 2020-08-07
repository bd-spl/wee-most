
import weechat
import wee_matter.server
import wee_matter.post
import wee_matter.file
from typing import NamedTuple

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

Reaction = NamedTuple(
    "Reaction",
    [
        ("user", any),
        ("emoji_name", str),
        ("post_id", str),
    ]
)

post_buffers = {}

def get_buffer_from_post_id(post_id):
    return post_buffers[post_id]

def post_post_cb(buffer, command, rc, out, err):
    if rc != 0:
        weechat.prnt(buffer, "Can't send post")
        return weechat.WEECHAT_RC_ERROR

    return weechat.WEECHAT_RC_OK

def build_post_from_input_data(buffer, input_data):
    server = wee_matter.server.get_server_from_buffer(buffer)

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

def build_reaction_message(reaction):
    return "[:{}:]".format(wee_matter.room.colorize_sentence(reaction.emoji_name, reaction.user.color))

def build_reaction_line(post):
    reaction_line = ""
    for reaction in post.reactions:
        reaction_line += " " + build_reaction_message(reaction)

    return reaction_line.strip()

def build_quote_message(message):
    if 69 < len(message):
        message = "%s…" % message[:69].strip()
    return message

def write_deleted_message_lines(buffer, post):
    first_initial_line_data = find_buffer_first_post_line_data(buffer, post.id)

    initial_message_prefix = weechat.hdata_string(weechat.hdata_get("line_data"), first_initial_line_data, "prefix")
    initial_message = weechat.hdata_string(weechat.hdata_get("line_data"), first_initial_line_data, "message").rsplit(' | ', 1)[0]
    weechat.prnt_date_tags(
        buffer,
        post.date,
        "deleted_post",
        initial_message_prefix + "	" + wee_matter.room.colorize_sentence(build_quote_message(initial_message), "red")
    )

def write_edited_message_lines(buffer, post):
    tags = "post_id_%s" % post.id

    first_initial_line_data = find_buffer_first_post_line_data(buffer, post.id)
    last_initial_line_data = find_buffer_last_post_line_data(buffer, post.id)

    initial_message_date = weechat.hdata_time(weechat.hdata_get("line_data"), first_initial_line_data, "date")
    initial_message_prefix = weechat.hdata_string(weechat.hdata_get("line_data"), first_initial_line_data, "prefix")

    initial_message = weechat.hdata_string(weechat.hdata_get("line_data"), first_initial_line_data, "message").rsplit(' | ', 1)[0]
    _, _, initial_reactions = weechat.hdata_string(weechat.hdata_get("line_data"), last_initial_line_data, "message").partition(' | ')
    initial_message = weechat.string_remove_color(initial_message, "")

    weechat.prnt_date_tags(
        buffer,
        initial_message_date,
        "edited_post",
        initial_message_prefix + "	" + wee_matter.room.colorize_sentence(build_quote_message(initial_message), "yellow")
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
        wee_matter.room.colorize_sentence(post.user.username, post.user.color) + "	" + new_message
    )

def write_reply_message_lines(buffer, post):
    tags = "post_id_%s" % post.id

    parent_line_data = find_buffer_first_post_line_data(buffer, post.parent_id)
    if not parent_line_data:
        return # probably replying a out of range message

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
        parent_message_prefix + "	" + wee_matter.room.colorize_sentence(build_quote_message(parent_message), "lightgreen")
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
            wee_matter.room.colorize_sentence(post.user.username, post.user.color) + "	" + post.message + " | " + build_reaction_line(post)
        )
        return

    weechat.prnt_date_tags(
        buffer,
        post.date,
        tags,
        wee_matter.room.colorize_sentence(post.user.username, post.user.color) + "	" + post.message
    )

def write_message_lines(buffer, post):
    tags = "post_id_%s" % post.id
    if post.reactions:
        tags += ",reactions"
        weechat.prnt_date_tags(
            buffer,
            post.date,
            tags,
            wee_matter.room.colorize_sentence(post.user.username, post.user.color) + "	" + post.message + " | " + build_reaction_line(post)
        )
        return

    weechat.prnt_date_tags(
        buffer,
        post.date,
        tags,
        wee_matter.room.colorize_sentence(post.user.username, post.user.color) + "	" + post.message
    )

def write_post(post):
    buffer_name = wee_matter.room.build_buffer_channel_name(post.channel_id)
    buffer = weechat.buffer_search("", buffer_name)
    server = wee_matter.server.get_server_from_buffer(buffer)

    if post.deleted:
        write_deleted_message_lines(buffer, post)
    elif post.id in post_buffers:
        write_edited_message_lines(buffer, post)
    elif post.parent_id:
        write_reply_message_lines(buffer, post)
    else:
        write_message_lines(buffer, post)
    wee_matter.file.write_file_lines(buffer, post)

    weechat.buffer_set(buffer, "localvar_set_last_post_id", post.id)
    post_buffers[post.id] = buffer

def get_reaction_from_reaction_data(reaction_data, server):
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

def build_post_from_post_data(post_data):
    buffer_name = wee_matter.room.build_buffer_channel_name(post_data["channel_id"])
    buffer = weechat.buffer_search("", buffer_name)

    server = wee_matter.server.get_server_from_buffer(buffer)

    user = server.users[post_data["user_id"]]

    post = Post(
        id= post_data["id"],
        parent_id= post_data["parent_id"],
        channel_id= post_data["channel_id"],
        message= post_data["message"],
        date= int(post_data["update_at"]/1000),
        deleted= False,
        files= wee_matter.file.get_files_from_post_data(post_data, server),
        reactions= get_reactions_from_post_data(post_data, server),
        user= user,
    )

    return post

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

    tags = get_line_data_tags(line_data)

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
