
import weechat
import wee_most.server
import wee_most.post
import wee_most.file
from wee_most.globals import (config)

class Post:
    def __init__(self, server, **kwargs):
        self.id = kwargs["id"]
        self.parent_id = kwargs["parent_id"]
        self.channel = server.get_channel(kwargs["channel_id"])
        self.message = kwargs["message"]
        self.type = kwargs["type"]
        self.date = int(kwargs["create_at"]/1000)
        self.read = False

        self.channel.posts[kwargs["id"]] = self

        self.user = server.users[kwargs["user_id"]]
        self.files = wee_most.file.get_files_from_post_data(kwargs, server)

        self.reactions = []
        if "reactions" in kwargs["metadata"]:
            for reaction_data in kwargs["metadata"]["reactions"]:
                self.reactions.append(Reaction(server, **reaction_data))

        self.attachments = kwargs["props"].get("attachments", [])
        self.from_bot = kwargs["props"].get("from_bot", False) or kwargs["props"].get("from_webhook", False)
        self.username_override = kwargs["props"].get("override_username")

    @property
    def buffer(self):
        return self.channel.buffer

    @property
    def server(self):
        return self.channel.server

    def add_reaction(self, reaction):
        self.reactions.append(reaction)

    def remove_reaction(self, reaction):
        for i, r in enumerate(self.reactions):
            if r.user == reaction.user and r.emoji_name == reaction.emoji_name:
                del self.reactions[i]

    def get_reactions_line(self):
        if not self.reactions:
            return ""

        my_username = self.channel.server.me.username

        reactions_string = []

        if config.reaction_group:
            reactions_groups = {}
            for r in self.reactions:
                if r.emoji_name in reactions_groups:
                    reactions_groups[r.emoji_name].append(r.user)
                else:
                    reactions_groups[r.emoji_name] = [ r.user ]

            for name, users in reactions_groups.items():
                colorized_name = colorize_sentence(name, config.color_reaction)
                for u in users:
                    if u.username == my_username:
                        colorized_name = colorize_sentence(name, config.color_reaction_own)
                        break

                if config.reaction_nick_show:
                    users_string = []
                    for u in users:
                        user_string = u.nick
                        if config.reaction_nick_colorize:
                            user_string = colorize_sentence(user_string, u.color)
                        users_string.append(user_string)

                    reaction_string = ":{}:({})".format(colorized_name, ",".join(users_string))
                else:
                    reaction_string = ":{}:{}".format(colorized_name, len(users))

                reactions_string.append(reaction_string)

        else:
            for r in self.reactions:
                if r.user.username == my_username:
                    colorized_name = colorize_sentence(r.emoji_name, config.color_reaction_own)
                else:
                    colorized_name = colorize_sentence(r.emoji_name, config.color_reaction)

                if config.reaction_nick_show:
                    user_string = u.nick
                    if config.reaction_nick_colorize:
                        user_string = colorize_sentence(user_string, r.user.color)

                    reaction_string = ":{}:({})".format(colorized_name, user_string)
                else:
                    reaction_string = ":{}:".format(colorized_name)

                reactions_string.append(reaction_string)

        return " [{}]".format(" ".join(reactions_string))

class Reaction:
    def __init__(self, server, **kwargs):
        self.user = server.users[kwargs["user_id"]]
        self.post = server.get_post(kwargs["post_id"])
        self.emoji_name = kwargs["emoji_name"]

    @property
    def buffer(self):
        return self.post.buffer

def post_post_cb(buffer, command, rc, out, err):
    if rc != 0:
        weechat.prnt(buffer, "Cannot send post")
        return weechat.WEECHAT_RC_ERROR

    return weechat.WEECHAT_RC_OK

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
        nick = username_override
    else:
        nick = user.nick

    nick = colorize_sentence(nick, user.color)

    if from_bot:
        nick += colorize_sentence(config.bot_suffix, config.color_bot_suffix)

    return (
        colorize_sentence(nick_prefix, nick_prefix_color_name)
        + nick
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

def delete_message(post):
    lines = weechat.hdata_pointer(weechat.hdata_get("buffer"), post.buffer, "lines")
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
    lines[0] = colorize_sentence("(deleted)", config.color_deleted)

    for pointer, line in zip(pointers, lines):
        line_data = weechat.hdata_pointer(weechat.hdata_get("line"), pointer, "data")
        weechat.hdata_update(weechat.hdata_get("line_data"), line_data, {"message": line})


def write_edited_message_lines(post):
    tags = "post_id_%s" % post.id

    first_initial_line_data = find_buffer_first_post_line_data(post.buffer, post.id)

    initial_tags = get_line_data_tags(first_initial_line_data)
    initial_post_id = find_post_id_in_tags(initial_tags)
    initial_post = post.channel.posts[initial_post_id]

    initial_message = initial_post.message
    initial_message_date = weechat.hdata_time(weechat.hdata_get("line_data"), first_initial_line_data, "date")
    initial_message_prefix = weechat.hdata_string(weechat.hdata_get("line_data"), first_initial_line_data, "prefix")

    weechat.prnt_date_tags(
        post.buffer,
        initial_message_date,
        "notify_none",
        initial_message_prefix + "	" + colorize_sentence(build_quote_message(initial_message), config.color_quote)
    )

    if post.reactions:
        new_message = post.message + post.get_reactions_line()
    else:
        new_message = post.message

    if post.read:
        tags += ",notify_none"

    weechat.prnt_date_tags(
        post.buffer,
        post.date,
        tags,
        (
            build_nick(post.user, post.from_bot, post.username_override)
            + "	"
            + new_message
        )
    )

def write_reply_message_lines(post):
    tags = "post_id_%s" % post.id

    parent_line_data = find_buffer_first_post_line_data(post.buffer, post.parent_id)
    if not parent_line_data:
        return # probably replying a out of range message

    parent_tags = get_line_data_tags(parent_line_data)
    parent_post_id = find_post_id_in_tags(parent_tags)
    parent_post = post.channel.posts[parent_post_id]

    parent_message = parent_post.message
    parent_message_date = weechat.hdata_time(weechat.hdata_get("line_data"), parent_line_data, "date")
    parent_message_prefix = weechat.hdata_string(weechat.hdata_get("line_data"), parent_line_data, "prefix")

    weechat.prnt_date_tags(
        post.buffer,
        parent_message_date,
        "quote,notify_none",
        parent_message_prefix + "	" + colorize_sentence(build_quote_message(parent_message), config.color_parent_reply)
    )

    parent_message_prefix = weechat.string_remove_color(parent_message_prefix, "")
    own_prefix = weechat.buffer_get_string(post.buffer, "localvar_nick")

    parent_post_id = find_post_id_in_tags(parent_tags)
    tags += ",reply_to_{}".format(parent_post_id)

    channel_type = weechat.buffer_get_string(post.buffer, "localvar_type")
    if channel_type == "channel":
        tags += ",notify_message"
    else:
        tags += ",notify_private"

    if post.read:
        tags += ",notify_none"

    # if somebody (not us) reply to our post
    if parent_message_prefix == own_prefix and parent_message_prefix != post.user.nick:
        tags += ",notify_highlight"

    if post.reactions:
        weechat.prnt_date_tags(
            post.buffer,
            post.date,
            tags,
            (
                build_nick(post.user, post.from_bot, post.username_override)
                + "	"
                + post.message
                + post.get_reactions_line()
            )
        )
        return

    weechat.prnt_date_tags(
        post.buffer,
        post.date,
        tags,
        (
            build_nick(post.user, post.from_bot, post.username_override)
            + "	"
            + post.message
        )
    )

    weechat.buffer_set(post.buffer, "localvar_set_last_post_id", post.id)

def write_message_lines(post):
    tags = "post_id_%s" % post.id

    # remove tabs to prevent display issue on multiline messages
    # where the part before the tab would be interpreted as the prefix
    tab_width = weechat.config_integer(weechat.config_get("weechat.look.tab_width"))
    message = post.message.replace("\t", " " * tab_width)

    channel_type = weechat.buffer_get_string(post.buffer, "localvar_type")
    if channel_type == "channel":
        tags += ",notify_message"
    else:
        tags += ",notify_private"

    if post.read:
        tags += ",notify_none"

    if post.attachments:
        message = build_message_with_attachments(message, post.attachments)

    if post.type in [ "system_join_channel", "system_join_team" ]:
        prefix = weechat.config_string(weechat.config_get("weechat.look.prefix_join"))
        message = "{}{}".format(prefix, message)
    elif post.type in [ "system_leave_channel", "system_leave_team" ]:
        prefix = weechat.config_string(weechat.config_get("weechat.look.prefix_quit"))
        message = "{}{}".format(prefix, message)

    if post.reactions:
        weechat.prnt_date_tags(
            post.buffer,
            post.date,
            tags,
            (
                build_nick(post.user, post.from_bot, post.username_override)
                + "	"
                + message
                + post.get_reactions_line()
            )
        )
        return

    weechat.prnt_date_tags(
        post.buffer,
        post.date,
        tags,
        build_nick(post.user, post.from_bot, post.username_override) + "	" + message
    )

    weechat.buffer_set(post.buffer, "localvar_set_last_post_id", post.id)

def write_file_lines(post):
    for file in post.files:
        weechat.prnt_date_tags(
            post.buffer,
            post.date,
            "file_id_" + file.id,
            "	[{}]({})".format(file.name, file.url)
        )

def write_post_edited(post):
    if post.server.get_post(post.id) is not None:
        write_edited_message_lines(post)

def write_post_deleted(post):
    if post.server.get_post(post.id) is not None:
        delete_message(post)

def write_post(post):
    if post.parent_id:
        write_reply_message_lines(post)
    else:
        write_message_lines(post)

    write_file_lines(post)

def get_line_data_tags(line_data):
    tags = []

    tags_count = weechat.hdata_integer(weechat.hdata_get("line_data"), line_data, "tags_count")
    for i in range(tags_count):
        tag = weechat.hdata_string(weechat.hdata_get("line_data"), line_data, "{}|tags_array".format(i))
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

def add_reaction_to_post(reaction):
    post = reaction.post
    if post is None:
        return

    post.add_reaction(reaction)
    new_message = post.message + post.get_reactions_line()

    line_data = find_buffer_last_post_line_data(reaction.buffer, post.id)

    weechat.hdata_update(
        weechat.hdata_get("line_data"),
        line_data,
        {
            "message": new_message,
        }
    )

def remove_reaction_from_post(reaction):
    post = reaction.post
    if post is None:
        return

    post.remove_reaction(reaction)

    line_data = find_buffer_last_post_line_data(reaction.buffer, post.id)

    if not post.reactions:
        new_message = post.message
    else:
        new_message = post.message + post.get_reactions_line()

    weechat.hdata_update(
        weechat.hdata_get("line_data"),
        line_data,
        {
            "message": new_message,
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
