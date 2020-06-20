import weechat

from wee_matter.commands import (setup_commands, matter_command_cb)

from wee_matter.server import (connect_server_cb, connect_server_teams_cb,
                               connect_server_team_channels_cb, disconnect_server_cb,
                               auto_connect, disconnect_all)

from wee_matter.room import (hidrate_room_cb)

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

setup_commands()
auto_connect()

def shutdown_cb():
    disconnect_all()

    return weechat.WEECHAT_RC_OK
