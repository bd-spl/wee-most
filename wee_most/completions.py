
import weechat
import wee_most

from wee_most.globals import servers

def channel_completion_cb(data, completion_item, current_buffer, completion):
    for server in servers.values():
        weechat.hook_completion_list_add(completion, server.id, 0, weechat.WEECHAT_LIST_POS_SORT)
        for team in server.teams.values():
            for channel in team.channels.values():
                buffer_name = weechat.buffer_get_string(channel.buffer, "short_name")
                weechat.hook_completion_list_add(completion, buffer_name, 0, weechat.WEECHAT_LIST_POS_SORT)

    return weechat.WEECHAT_RC_OK

def private_completion_cb(data, completion_item, current_buffer, completion):
    for server in servers.values():
        for channel in server.channels.values():
            buffer_name = weechat.buffer_get_string(channel.buffer, "short_name")
            weechat.hook_completion_list_add(completion, buffer_name, 0, weechat.WEECHAT_LIST_POS_SORT)
    return weechat.WEECHAT_RC_OK


def server_completion_cb(data, completion_item, current_buffer, completion):
    for server_id in servers:
        weechat.hook_completion_list_add(completion, server_id, 0, weechat.WEECHAT_LIST_POS_SORT)
    return weechat.WEECHAT_RC_OK

def slash_command_completion_cb(data, completion_item, current_buffer, completion):
    slash_commands = ["away", "code", "collapse", "dnd", "echo", "expand", "groupmsg", "header", "help", "invite", "invite_people", "join", "kick", "leave", "logout", "me", "msg", "mute", "offline", "online", "purpose", "rename", "search", "settings", "shortcuts", "shrug", "status"]

    for slash_command in slash_commands:
        weechat.hook_completion_list_add(completion, slash_command, 0, weechat.WEECHAT_LIST_POS_SORT)
    return weechat.WEECHAT_RC_OK

def nick_completion_cb(data, completion_item, current_buffer, completion):
    server = wee_most.server.get_server_from_buffer(current_buffer)
    if not server:
        return weechat.WEECHAT_RC_OK

    channel = server.get_channel_from_buffer(current_buffer)
    if not channel:
        return weechat.WEECHAT_RC_OK

    for user in channel.users.values():
        weechat.completion_list_add(completion, user.username, 1, weechat.WEECHAT_LIST_POS_SORT)
        weechat.completion_list_add(completion, "@" + user.username, 1, weechat.WEECHAT_LIST_POS_SORT)

    return weechat.WEECHAT_RC_OK

def setup_completions():
    weechat.hook_completion("irc_channels", "complete channels for Mattermost", "channel_completion_cb", "")
    weechat.hook_completion("irc_privates", "complete dms/mpdms for Mattermost", "private_completion_cb", "")
    weechat.hook_completion("mattermost_server_commands", "complete server names for Mattermost", "server_completion_cb", "")
    weechat.hook_completion("mattermost_slash_commands", "complete Mattermost slash commands", "slash_command_completion_cb", "")
    weechat.hook_completion("nicks", "complete @-nicks for Mattermost", "nick_completion_cb", "")

