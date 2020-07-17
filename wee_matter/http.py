
import weechat
import wee_matter
import json
import time

def build_file_url(file_id, server):
    return wee_matter.server.server_root_url(server) + "/api/v4/files/" + file_id

def singularity_cb(data, command, rc, out, err):
    if rc != 0:
        weechat.prnt("", "An error occured when performing a request")
        return weechat.WEECHAT_RC_ERROR

    return weechat.WEECHAT_RC_OK

def run_get_user_teams(user_id, server, cb, cb_data):
    url = wee_matter.server.server_root_url(server) + "/api/v4/users/" + user_id + "/teams"
    weechat.hook_process_hashtable(
        "url:" + url,
        {
            "failonerror": "1",
            "httpheader": "Authorization: Bearer " + server.user_token,
        },
        30 * 1000,
        cb,
        cb_data
    )

def run_get_team(team_id, server, cb, cb_data):
    url = server_root_url(server) + "/api/v4/teams/" + team_id
    weechat.hook_process_hashtable(
        "url:" + url,
        {
            "failonerror": "1",
            "httpheader": "Authorization: Bearer " + server.user_token,
        },
        30 * 1000,
        cb,
        cb_data
    )

def run_get_users(server, page, cb, cb_data):
    url = wee_matter.server.server_root_url(server) + "/api/v4/users?page=" + str(page)
    weechat.hook_process_hashtable(
        "url:" + url,
        {
            "failonerror": "1",
            "httpheader": "Authorization: Bearer " + server.user_token,
        },
        30 * 1000,
        cb,
        cb_data
    )

def run_user_logout(server, cb, cb_data):
    url = wee_matter.server.server_root_url(server) + "/api/v4/users/logout"
    weechat.hook_process_hashtable(
        "url:" + url,
        {
            "failonerror": "1",
            "post": "1",
            "httpheader": "\n".join([
                "Authorization: Bearer " + server.user_token,
                "Content-Type:",
            ]),
        },
        30 * 1000,
        cb,
        cb_data
    )

def run_user_login(server, cb, cb_data):
    url = wee_matter.server.server_root_url(server) + "/api/v4/users/login"
    params = {
        "login_id": server.username,
        "password": server.password,
    }

    weechat.hook_process_hashtable(
        "url:" + url,
        {
            "failonerror": "1",
            "postfields": json.dumps(params),
            "header": "1",
        },
        30 * 1000,
        cb,
        cb_data
    )

def run_get_channel(channel_id, server, cb, cb_data):
    url = wee_matter.server.server_root_url(server) + "/api/v4/channels/" + channel_id
    weechat.hook_process_hashtable(
        "url:" + url,
        {
            "failonerror": "1",
            "httpheader": "Authorization: Bearer " + server.user_token,
        },
        30 * 1000,
        cb,
        cb_data
    )

def run_get_user_team_channels(user_id, team_id, server, cb, cb_data):
    url = wee_matter.server.server_root_url(server) + "/api/v4/users/" + user_id + "/teams/" + team_id + "/channels?page=0&per_page=5"
    weechat.hook_process_hashtable(
        "url:" + url,
        {
            "failonerror": "1",
            "httpheader": "Authorization: Bearer " + server.user_token,
        },
        30 * 1000,
        cb,
        cb_data
    )

def run_post_post(post, server, cb, cb_data):
    url = wee_matter.server.server_root_url(server) + "/api/v4/posts"
    params = {
        "channel_id": post.channel_id,
        "message": post.message,
    }

    if post.parent_id:
        params["root_id"] = post.parent_id

    weechat.hook_process_hashtable(
        "url:" + url,
        {
            "failonerror": "1",
            "httpheader": "Authorization: Bearer " + server.user_token,
            "postfields": json.dumps(params),
        },
        30 * 1000,
        cb,
        cb_data
    )

def run_get_channel_posts(channel_id, server, cb, cb_data):
    url = wee_matter.server.server_root_url(server) + "/api/v4/channels/" + channel_id + "/posts"
    weechat.hook_process_hashtable(
        "url:" + url,
        {
            "failonerror": "1",
            "httpheader": "Authorization: Bearer " + server.user_token,
        },
        30 * 1000,
        cb,
        cb_data
    )

def run_get_read_channel_posts(user_id, channel_id, server, cb, cb_data):
    url = wee_matter.server.server_root_url(server) + "/api/v4/users/" + user_id + "/channels/" + channel_id + "/posts/unread?limit_after=1"
    weechat.hook_process_hashtable(
        "url:" + url,
        {
            "failonerror": "1",
            "httpheader": "Authorization: Bearer " + server.user_token,
        },
        30 * 1000,
        cb,
        cb_data
    )

def run_get_channel_posts_after(post_id, channel_id, server, cb, cb_data):
    url = wee_matter.server.server_root_url(server) + "/api/v4/channels/" + channel_id + "/posts?after=" + post_id
    weechat.hook_process_hashtable(
        "url:" + url,
        {
            "failonerror": "1",
            "httpheader": "Authorization: Bearer " + server.user_token,
        },
        30 * 1000,
        cb,
        cb_data
    )

def run_get_channel_members(channel_id, server, cb, cb_data):
    url = wee_matter.server.server_root_url(server) + "/api/v4/channels/" + channel_id + "/members"
    weechat.hook_process_hashtable(
        "url:" + url,
        {
            "failonerror": "1",
            "httpheader": "Authorization: Bearer " + server.user_token,
        },
        30 * 1000,
        cb,
        cb_data
    )

def run_get_channel_member(channel_id, member_id, server, cb, cb_data):
    url = wee_matter.server.server_root_url(server) + "/api/v4/channels/" + channel_id + "/members/" + member_id
    weechat.hook_process_hashtable(
        "url:" + url,
        {
            "failonerror": "1",
            "httpheader": "Authorization: Bearer " + server.user_token,
        },
        30 * 1000,
        cb,
        cb_data
    )

def run_post_user_post_unread(user_id, post_id, server, cb, cb_data):
    url = wee_matter.server.server_root_url(server) + "/api/v4/users/" + user_id + "/posts/" + post_id + "/set_unread"
    weechat.hook_process_hashtable(
        "url:" + url,
        {
            "post": "1",
            "failonerror": "1",
            "httpheader": "Authorization: Bearer " + server.user_token,
        },
        30 * 1000,
        cb,
        cb_data
    )

def run_post_reaction(emoji_name, post_id, server, cb, cb_data):
    url = wee_matter.server.server_root_url(server) + "/api/v4/reactions"
    params = {
        "user_id": server.user.id,
        "post_id": post_id,
        "emoji_name": emoji_name,
        "create_at": int(time.time()),
    }

    weechat.hook_process_hashtable(
        "url:" + url,
        {
            "postfields": json.dumps(params),
            "failonerror": "1",
            "httpheader": "Authorization: Bearer " + server.user_token,
        },
        30 * 1000,
        cb,
        cb_data
    )

def run_delete_reaction(emoji_name, post_id, server, cb, cb_data):
    url = wee_matter.server.server_root_url(server) + "/api/v4/users/" + server.user.id + "/posts/" + post_id + "/reactions/" + emoji_name

    weechat.hook_process_hashtable(
        "url:" + url,
        {
            "customrequest": "DELETE",
            "failonerror": "1",
            "httpheader": "Authorization: Bearer " + server.user_token,
        },
        30 * 1000,
        cb,
        cb_data
    )

def run_delete_post(post_id, server, cb, cb_data):
    url = wee_matter.server.server_root_url(server) + "/api/v4/posts/" + post_id

    weechat.hook_process_hashtable(
        "url:" + url,
        {
            "customrequest": "DELETE",
            "failonerror": "1",
            "httpheader": "Authorization: Bearer " + server.user_token,
        },
        30 * 1000,
        cb,
        cb_data
    )

def run_get_file(file_id, file_out_path, server, cb, cb_data):
    url = wee_matter.server.server_root_url(server) + "/api/v4/files/" + file_id

    weechat.hook_process_hashtable(
        "url:" + url,
        {
            "failonerror": "1",
            "file_out": file_out_path,
            "httpheader": "Authorization: Bearer " + server.user_token,
        },
        30 * 1000,
        cb,
        cb_data
    )

