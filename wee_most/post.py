
import weechat
import wee_most.server
import wee_most.post
import wee_most.file
from typing import NamedTuple
from wee_most.globals import (config, channel_buffers)

Post = NamedTuple(
    "Post",
    [
        ("id", str),
        ("parent_id", str),
        ("channel_id", str),
        ("message", str),
        ("date", int),
        ("deleted", bool),
        ("read", bool),
        ("attachments", list),
        ("files", list),
        ("reactions", list),
        ("user", any),
        ("from_bot", bool),
        ("username_override", str),
        ("type", str),
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
    server = wee_most.server.get_server_from_buffer(buffer)

    return Post(
        id= "",
        parent_id= "",
        channel_id= weechat.buffer_get_string(buffer, "localvar_channel_id"),
        message= input_data,
        date= 0,
        deleted= False,
        read= True,
        attachments= [],
        files= [],
        reactions= [],
        user= server.me,
        from_bot= False,
        username_override= None,
        type= None,
    )

def build_reaction_message(reaction):
    return "[:{}:]".format(colorize_sentence(reaction.emoji_name, reaction.user.color))

def build_reaction_line(post):
    reaction_line = ""
    for reaction in post.reactions:
        reaction_line += " " + build_reaction_message(reaction)

    return reaction_line.strip()

def build_quote_message(message):
    if 69 < len(message):
        message = "%s…" % message[:69].strip()
    return message

def colorize_sentence(sentence, color):
    return "{}{}{}".format(weechat.color(color), sentence, weechat.color("reset"))

def build_nick(user, from_bot, username_override):
    nick_prefix = weechat.config_string(weechat.config_get("weechat.look.nick_prefix"))
    nick_prefix_color_name = weechat.config_string(
        weechat.config_get("weechat.color.chat_nick_prefix")
    )

    nick_suffix = weechat.config_string(weechat.config_get("weechat.look.nick_suffix"))
    nick_suffix_color_name = weechat.config_string(
        weechat.config_get("weechat.color.chat_nick_suffix")
    )

    if username_override:
        username = colorize_sentence(username_override, user.color)
    else:
        username = colorize_sentence(user.username, user.color)

    if from_bot:
        username += " " + colorize_sentence("[BOT]", config.get_value("color_bot_suffix"))

    return (
        colorize_sentence(nick_prefix, nick_prefix_color_name)
        + username
        + colorize_sentence(nick_suffix, nick_suffix_color_name)
    )

def build_message_with_attachments(message, attachments):
    if message:
        msg_parts = [ message ]
    else:
        msg_parts = []

    for attachment in attachments:
        att = []

        if attachment["pretext"]:
            att.append(attachment["pretext"])

        if attachment["author_name"]:
            att.append(attachment["author_name"])

        if attachment["title"] and attachment["title_link"]:
            att.append(attachment["title"] + " (" + attachment["title_link"] + ")")
        elif attachment["title"]:
            att.append(attachment["title"])
        elif attachment["title_link"]:
            att.append(attachment["title_link"])

        if attachment["text"]:
            att.append(attachment["text"])

        if attachment["fields"]:
            for field in attachment["fields"]:
                if field["title"] and field["value"]:
                    att.append(field["title"] + ": " + field["value"])
                elif field["value"]:
                    att.append(field["value"])

        if attachment["footer"]:
            att.append(attachment["footer"])

        msg_parts.append("\n".join(att))

    return "\n\n".join(msg_parts)

def delete_message(buffer, post):
    lines = weechat.hdata_pointer(weechat.hdata_get("buffer"), buffer, "lines")
    line = weechat.hdata_pointer(weechat.hdata_get("lines"), lines, "last_line")
    line_data = weechat.hdata_pointer(weechat.hdata_get("line"), line, "data")

    # find last line of this post
    while line and not is_post_line_data(line_data, post.id):
        line = weechat.hdata_pointer(weechat.hdata_get("line"), line, "prev_line")
        line_data = weechat.hdata_pointer(weechat.hdata_get("line"), line, "data")

    # find all lines of this post
    pointers = []
    while line and is_post_line_data(line_data, post.id):
        pointers.append(line)
        line = weechat.hdata_pointer(weechat.hdata_get("line"), line, "prev_line")
        line_data = weechat.hdata_pointer(weechat.hdata_get("line"), line, "data")
    pointers.reverse()

    if not pointers:
        return

    lines = [""] * len(pointers)
    lines[0] = colorize_sentence("(deleted)", config.get_value("color_deleted"))

    for pointer, line in zip(pointers, lines):
        line_data = weechat.hdata_pointer(weechat.hdata_get("line"), pointer, "data")
        weechat.hdata_update(weechat.hdata_get("line_data"), line_data, {"message": line})


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
        "edited_post,notify_none",
        initial_message_prefix + "	" + colorize_sentence(build_quote_message(initial_message), config.get_value("color_quote"))
    )

    if initial_reactions:
        new_message = post.message + " | " + initial_reactions
        tags += ",reactions"
    else:
        new_message = post.message

    if post.read:
        tags += ",notify_none"

    weechat.prnt_date_tags(
        buffer,
        post.date,
        tags,
        (
            build_nick(post.user, post.from_bot, post.username_override)
            + "	"
            + new_message
        )
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
        "quote,notify_none",
        parent_message_prefix + "	" + colorize_sentence(build_quote_message(parent_message), config.get_value("color_parent_reply"))
    )

    parent_message_prefix = weechat.string_remove_color(parent_message_prefix, "")
    own_prefix = weechat.buffer_get_string(buffer, "localvar_nick")

    parent_post_id = find_post_id_in_tags(parent_tags)
    tags += ",reply_to_{}".format(parent_post_id)

    channel_type = weechat.buffer_get_string(buffer, "localvar_type")
    if channel_type == "channel":
        tags += ",notify_message"
    else:
        tags += ",notify_private"

    if post.read:
        tags += ",notify_none"

    # if somebody (not us) reply to our post
    if parent_message_prefix == own_prefix and parent_message_prefix != post.user.username:
        tags += ",notify_highlight"

    if post.reactions:
        tags += ",reactions"
        weechat.prnt_date_tags(
            buffer,
            post.date,
            tags,
            (
                build_nick(post.user, post.from_bot, post.username_override)
                + "	"
                + post.message
                + " | "
                + build_reaction_line(post)
            )
        )
        return

    weechat.prnt_date_tags(
        buffer,
        post.date,
        tags,
        (
            build_nick(post.user, post.from_bot, post.username_override)
            + "	"
            + post.message
        )
    )

def write_message_lines(buffer, post):
    tags = "post_id_%s" % post.id
    message = post.message

    channel_type = weechat.buffer_get_string(buffer, "localvar_type")
    if channel_type == "channel":
        tags += ",notify_message"
    else:
        tags += ",notify_private"

    if post.read:
        tags += ",notify_none"

    if post.attachments:
        tags += ",attachments"
        message = build_message_with_attachments(message, post.attachments)

    if post.type == "system_join_channel":
        prefix = weechat.config_string(weechat.config_get("weechat.look.prefix_join"))
        message = "{}{}".format(prefix, message)
    elif post.type == "system_leave_channel":
        prefix = weechat.config_string(weechat.config_get("weechat.look.prefix_quit"))
        message = "{}{}".format(prefix, message)

    if post.reactions:
        tags += ",reactions"
        weechat.prnt_date_tags(
            buffer,
            post.date,
            tags,
            (
                build_nick(post.user, post.from_bot, post.username_override)
                + "	"
                + message
                + " | "
                + build_reaction_line(post)
            )
        )
        return

    weechat.prnt_date_tags(
        buffer,
        post.date,
        tags,
        build_nick(post.user, post.from_bot, post.username_override) + "	" + message
    )

def write_post(post):
    buffer = channel_buffers[post.channel_id]

    if post.deleted:
        delete_message(buffer, post)
    elif post.id in post_buffers:
        write_edited_message_lines(buffer, post)
    elif post.parent_id:
        write_reply_message_lines(buffer, post)
    else:
        write_message_lines(buffer, post)
    wee_most.file.write_file_lines(buffer, post)

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

def build_post_from_post_data(post_data, is_read = False):
    buffer = channel_buffers[post_data["channel_id"]]

    server = wee_most.server.get_server_from_buffer(buffer)

    user = server.users[post_data["user_id"]]

    if 'attachments' in post_data["props"]:
        attachments = post_data["props"]["attachments"]
    else:
        attachments = []

    from_bot = post_data["props"].get("from_bot", False) or post_data["props"].get("from_webhook", False)

    username_override = post_data["props"].get("override_username")

    post = Post(
        id= post_data["id"],
        parent_id= post_data["parent_id"],
        channel_id= post_data["channel_id"],
        message= post_data["message"],
        date= int(post_data["create_at"]/1000),
        deleted= False,
        read= is_read,
        attachments= attachments,
        files= wee_most.file.get_files_from_post_data(post_data, server),
        reactions= get_reactions_from_post_data(post_data, server),
        user= user,
        from_bot= from_bot,
        username_override= username_override,
        type= post_data["type"],
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
