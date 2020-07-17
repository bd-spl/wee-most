import weechat

from wee_matter.commands import (matter_command_cb, reply_command_cb,
                                 react_command_cb, unreact_command_cb,
                                 delete_post_command_cb)

from wee_matter.websocket import (receive_ws_callback, ws_ping_cb,
                                  reconnection_loop_cb)

from wee_matter.server import (connect_server_cb, connect_server_teams_cb,
                               connect_server_team_channels_cb, disconnect_server_cb,
                               connect_server_users_cb, server_completion_cb,
                               connect_server_team_channel_cb, connect_server_team_cb)

from wee_matter.room import (hidrate_room_read_posts_cb, hidrate_room_posts_cb,
                             hidrate_room_users_cb, room_input_cb,
                             buffer_switch_cb, channel_completion_cb, private_completion_cb,
                             channel_switch_cb, channel_click_cb, hidrate_room_user_cb, handle_multiline_message_cb)
from wee_matter.post import post_post_cb

from wee_matter.http import singularity_cb
from wee_matter.file import file_get_cb
import wee_matter

WEECHAT_SCRIPT_NAME = "wee-matter"
WEECHAT_SCRIPT_DESCRIPTION = "mattermost chat plugin"
WEECHAT_SCRIPT_AUTHOR = "Reed Wade <reedwade@misterbanal.net>"
WEECHAT_SCRIPT_VERSION = "pre-alpha"
WEECHAT_SCRIPT_LICENSE = "GPL-3"

weechat.register(
    WEECHAT_SCRIPT_NAME,
    WEECHAT_SCRIPT_AUTHOR,
    WEECHAT_SCRIPT_VERSION,
    WEECHAT_SCRIPT_LICENSE,
    WEECHAT_SCRIPT_DESCRIPTION,
    "shutdown_cb",
    ""
)

wee_matter.commands.setup_commands()
wee_matter.config.setup()
wee_matter.server.auto_connect()

weechat.hook_modifier("input_text_for_buffer", "handle_multiline_message_cb", "")
weechat.hook_signal("buffer_switch", "buffer_switch_cb", "")

def shutdown_cb():
    wee_matter.server.disconnect_all()

    return weechat.WEECHAT_RC_OK
