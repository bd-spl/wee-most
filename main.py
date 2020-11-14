import weechat

from wee_matter.room import (handle_multiline_message_cb, room_input_cb,
                             buffer_switch_cb, channel_completion_cb,
                             private_completion_cb, channel_switch_cb,
                             channel_click_cb)

from wee_matter.commands import (matter_command_cb, reply_command_cb,
                                 react_command_cb, unreact_command_cb,
                                 delete_post_command_cb)

from wee_matter.websocket import (receive_ws_callback, ws_ping_cb,
                                  reconnection_loop_cb)

from wee_matter.http import singularity_cb, buffered_response_cb
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
