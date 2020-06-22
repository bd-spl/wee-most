
import weechat
from wee_matter.server import (get_server, server_root_url,
                              create_team, create_user)
import json

def connect_server_teams_cb(server_name, command, rc, out, err):
    if rc != 0:
        weechat.prnt("", "An error occured when connecting teams")
        return weechat.WEECHAT_RC_ERROR

    server = get_server(server_name)

    response = json.loads(out)

    teams = {}
    for team in response:
        server.teams[team["id"]] = create_team(team, server)

    for team in response:
        url = server_root_url(server) + "/api/v4/users/" + server.user_id + "/teams/" + team["id"] + "/channels"
        weechat.hook_process_hashtable(
            "url:" + url,
            {
                "port": server.port,
                "failonerror": "1",
                "httpheader": "Authorization: Bearer " + server.user_token,
            },
            30 * 1000,
            "connect_server_team_channels_cb",
            server_name
        )

    return weechat.WEECHAT_RC_OK

def run_server_load_teams(server):
    url = server_root_url(server) + "/api/v4/users/" + server.user_id + "/teams"
    weechat.hook_process_hashtable(
        "url:" + url,
        {
            "port": server.port,
            "failonerror": "1",
            "httpheader": "Authorization: Bearer " + server.user_token,
        },
        30 * 1000,
        "connect_server_teams_cb",
        server.name
    )

def connect_server_users_cb(server_name, command, rc, out, err):
    if rc != 0:
        weechat.prnt("", "An error occured when connecting users")
        return weechat.WEECHAT_RC_ERROR

    server = get_server(server_name)

    response = json.loads(out)
    users = {}
    for user in response:
        server.users[user["id"]] = create_user(user, server)

    run_server_load_teams(server)

    return weechat.WEECHAT_RC_OK

def run_server_load_users(server):
    url = server_root_url(server) + "/api/v4/users"
    weechat.hook_process_hashtable(
        "url:" + url,
        {
            "port": server.port,
            "failonerror": "1",
            "httpheader": "Authorization: Bearer " + server.user_token,
        },
        30 * 1000,
        "connect_server_users_cb",
        server.name
    )
