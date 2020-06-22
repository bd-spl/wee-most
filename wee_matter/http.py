
import weechat
from wee_matter.server import (get_server, server_root_url,
                              create_team, create_user)
import json

def run_server_load_teams(server, cb):
    url = server_root_url(server) + "/api/v4/users/" + server.user_id + "/teams"
    weechat.hook_process_hashtable(
        "url:" + url,
        {
            "port": server.port,
            "failonerror": "1",
            "httpheader": "Authorization: Bearer " + server.user_token,
        },
        30 * 1000,
        cb,
        server.name
    )

def run_server_load_users(server, cb):
    url = server_root_url(server) + "/api/v4/users"
    weechat.hook_process_hashtable(
        "url:" + url,
        {
            "port": server.port,
            "failonerror": "1",
            "httpheader": "Authorization: Bearer " + server.user_token,
        },
        30 * 1000,
        cb,
        server.name
    )
