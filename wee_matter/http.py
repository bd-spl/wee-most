
import weechat
from wee_matter.server import (get_server, server_root_url,
                              create_team, create_user)
import json

def run_get_user_teams(user_id, server, cb):
    url = server_root_url(server) + "/api/v4/users/" + user_id + "/teams"
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

def run_get_users(server, cb):
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

def run_user_logout(server, cb):
    url = server_root_url(server) + "/api/v4/users/logout"
    weechat.hook_process_hashtable(
        "url:" + url,
        {
            "port": server.port,
            "failonerror": "1",
            "post": "1",
            "httpheader": "\n".join([
                "Authorization: Bearer " + server.user_token,
                "Content-Type:",
            ]),
        },
        30 * 1000,
        cb,
        server.name
    )

def run_user_login(server, cb):
    url = server_root_url(server) + "/api/v4/users/login"
    params = {
        "login_id": server.username,
        "password": server.password,
    }

    weechat.hook_process_hashtable(
        "url:" + url,
        {
            "port": server.port,
            "failonerror": "1",
            "postfields": json.dumps(params),
            "header": "1",
        },
        30 * 1000,
        cb,
        server.name
    )

def run_get_user_team_channels(user_id, team_id, server, cb):
    url = server_root_url(server) + "/api/v4/users/" + user_id + "/teams/" + team_id + "/channels"
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

def run_post_post(post, server, cb, data):
    url = server_root_url(server) + "/api/v4/posts"
    params = {
        "channel_id": post.channel_id,
        "message": post.message,
    }

    weechat.hook_process_hashtable(
        "url:" + url,
        {
            "port": server.port,
            "failonerror": "1",
            "httpheader": "Authorization: Bearer " + server.user_token,
            "postfields": json.dumps(params),
        },
        30 * 1000,
        cb,
        data
    )
