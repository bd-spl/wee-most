import weechat

from wee_most.channel import (handle_multiline_message_cb, channel_input_cb,
                             buffer_switch_cb,
                             channel_click_cb)

from wee_most.server import (config_server_buffer_cb, get_buffer_user_status_cb)

from wee_most.commands import (mattermost_command_cb)

from wee_most.completions import (channel_completion_cb, private_completion_cb,
                                  server_completion_cb, slash_command_completion_cb,
                                  nick_completion_cb)

from wee_most.websocket import (receive_ws_callback, ws_ping_cb,
                                  reconnection_loop_cb)

from wee_most.http import (singularity_cb, buffered_response_cb,
                            handle_queued_request_cb)

from wee_most.globals import config

import wee_most

WEECHAT_SCRIPT_NAME = "wee-most"
WEECHAT_SCRIPT_DESCRIPTION = "Mattermost integration"
WEECHAT_SCRIPT_AUTHOR = "Damien Tardy-Panis <damien.dev@tardypad.me>"
WEECHAT_SCRIPT_VERSION = "0.1.0"
WEECHAT_SCRIPT_LICENSE = "GPL3"

weechat.register(
    WEECHAT_SCRIPT_NAME,
    WEECHAT_SCRIPT_AUTHOR,
    WEECHAT_SCRIPT_VERSION,
    WEECHAT_SCRIPT_LICENSE,
    WEECHAT_SCRIPT_DESCRIPTION,
    "shutdown_cb",
    ""
)

wee_most.commands.setup_commands()
wee_most.completions.setup_completions()
config.setup()

if weechat.info_get("auto_connect", "") == '1':
    wee_most.server.auto_connect()

weechat.hook_modifier("input_text_for_buffer", "handle_multiline_message_cb", "")
weechat.hook_signal("buffer_switch", "buffer_switch_cb", "")
weechat.hook_timer(int(0.2 * 1000), 0, 0, "handle_queued_request_cb", "")
weechat.hook_timer(60 * 1000, 0, 0, "get_buffer_user_status_cb", "")
weechat.hook_config("irc.look.server_buffer", "config_server_buffer_cb", "")
weechat.hook_focus("chat", "channel_click_cb", "")

def shutdown_cb():
    wee_most.server.disconnect_all()

    return weechat.WEECHAT_RC_OK
