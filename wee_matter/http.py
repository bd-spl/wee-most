
import weechat
import wee_matter
import json
import time
import re

from wee_matter.room import (hidrate_room_read_posts_cb, hidrate_room_posts_cb,
                             hidrate_room_users_cb, hidrate_room_user_cb)

from wee_matter.post import post_post_cb

from wee_matter.file import file_get_cb

from wee_matter.server import (connect_server_cb, connect_server_teams_cb,
                               connect_server_team_channels_cb, disconnect_server_cb,
                               connect_server_users_cb, server_completion_cb,
                               connect_server_team_channel_cb, connect_server_team_cb,
                               new_user_cb)


def build_file_url(file_id, server):
    return wee_matter.server.server_root_url(server) + "/api/v4/files/" + file_id

def singularity_cb(data, command, rc, out, err):
    if rc != 0:
        weechat.prnt("", "An error occured when performing a request")
        return weechat.WEECHAT_RC_ERROR

    return weechat.WEECHAT_RC_OK

response_buffers = {}
def buffered_response_cb(data, command, rc, out, err):
    arg_search = re.search('([^\|]*)\|([^\|]*)\|(.*)', data)
    if not arg_search:
        weechat.prnt("", "Bad usage of buffered response cb \"{}\"".format(data))
        return weechat.WEECHAT_RC_ERROR
    response_buffer_name = arg_search.group(1)
    real_cb = arg_search.group(2)
    real_data = arg_search.group(3)

    if not response_buffer_name in response_buffers:
        response_buffers[response_buffer_name] = ""

    if rc == weechat.WEECHAT_HOOK_PROCESS_RUNNING:
        response_buffers[response_buffer_name] += out
        return weechat.WEECHAT_RC_OK

    response = response_buffers[response_buffer_name] + out
    del response_buffers[response_buffer_name]

    return eval(real_cb)(real_data, command, rc, response, err)

def build_buffer_cb_data(url, cb, cb_data):
    return "{}|{}|{}".format(url, cb, cb_data)

def run_get_user_teams(user_id, server, cb, cb_data):
    url = wee_matter.server.server_root_url(server) + "/api/v4/users/" + user_id + "/teams"
    weechat.hook_process_hashtable(
        "url:" + url,
        {
            "failonerror": "1",
            "httpheader": "Authorization: Bearer " + server.user_token,
        },
        30 * 1000,
        "buffered_response_cb",
        build_buffer_cb_data(url, cb, cb_data)
    )

def run_get_team(team_id, server, cb, cb_data):
    url = wee_matter.server.server_root_url(server) + "/api/v4/teams/" + team_id
    weechat.hook_process_hashtable(
        "url:" + url,
        {
            "failonerror": "1",
            "httpheader": "Authorization: Bearer " + server.user_token,
        },
        30 * 1000,
        "buffered_response_cb",
        build_buffer_cb_data(url, cb, cb_data)
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
        "buffered_response_cb",
        build_buffer_cb_data(url, cb, cb_data)
    )

def run_get_user(server, user_id, cb, cb_data):
    url = wee_matter.server.server_root_url(server) + "/api/v4/users/" + user_id
    weechat.hook_process_hashtable(
        "url:" + url,
        {
            "failonerror": "1",
            "httpheader": "Authorization: Bearer " + server.user_token,
        },
        30 * 1000,
        "buffered_response_cb",
        build_buffer_cb_data(url, cb, cb_data)
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
        "buffered_response_cb",
        build_buffer_cb_data(url, cb, cb_data)
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
        "buffered_response_cb",
        build_buffer_cb_data(url, cb, cb_data)
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
        "buffered_response_cb",
        build_buffer_cb_data(url, cb, cb_data)
    )

def run_get_user_team_channels(user_id, team_id, server, cb, cb_data):
    url = wee_matter.server.server_root_url(server) + "/api/v4/users/" + user_id + "/teams/" + team_id + "/channels"
    weechat.hook_process_hashtable(
        "url:" + url,
        {
            "failonerror": "1",
            "httpheader": "Authorization: Bearer " + server.user_token,
        },
        30 * 1000,
        "buffered_response_cb",
        build_buffer_cb_data(url, cb, cb_data)
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
        "buffered_response_cb",
        build_buffer_cb_data(url, cb, cb_data)
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
        "buffered_response_cb",
        build_buffer_cb_data(url, cb, cb_data)
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
        "buffered_response_cb",
        build_buffer_cb_data(url, cb, cb_data)
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
        "buffered_response_cb",
        build_buffer_cb_data(url, cb, cb_data)
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
        "buffered_response_cb",
        build_buffer_cb_data(url, cb, cb_data)
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
        "buffered_response_cb",
        build_buffer_cb_data(url, cb, cb_data)
    )

def run_post_channel_view(user_id, channel_id, server, cb, cb_data):
    url = wee_matter.server.server_root_url(server) + "/api/v4/channels/members/" + user_id + "/view"
    params = {
        "channel_id": channel_id,
    }

    weechat.hook_process_hashtable(
        "url:" + url,
        {
            "postfields": json.dumps(params),
            "failonerror": "1",
            "httpheader": "Authorization: Bearer " + server.user_token,
        },
        30 * 1000,
        "buffered_response_cb",
        build_buffer_cb_data(url, cb, cb_data)
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
        "buffered_response_cb",
        build_buffer_cb_data(url, cb, cb_data)
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
        "buffered_response_cb",
        build_buffer_cb_data(url, cb, cb_data)
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
        "buffered_response_cb",
        build_buffer_cb_data(url, cb, cb_data)
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
        "buffered_response_cb",
        build_buffer_cb_data(url, cb, cb_data)
    )

