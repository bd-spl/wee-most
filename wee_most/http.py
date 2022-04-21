
import weechat
import wee_most
import json
import time
import re
import urllib.request

from wee_most.channel import (hydrate_channel_read_posts_cb, hydrate_channel_posts_cb,
                             hydrate_channel_users_cb)

from wee_most.post import post_post_cb

from wee_most.file import file_get_cb

from wee_most.server import (connect_server_cb, connect_server_teams_cb,
                               connect_server_team_channels_cb,
                               connect_server_users_cb, connect_server_preferences_cb,
                               connect_server_team_channel_cb, connect_server_team_cb,
                               new_user_cb)


def build_file_url(file_id, server):
    return server.url + "/api/v4/files/" + file_id

def singularity_cb(data, command, rc, out, err):
    if rc != 0:
        weechat.prnt("", "An error occurred while performing a request")
        return weechat.WEECHAT_RC_ERROR

    return weechat.WEECHAT_RC_OK

response_buffers = {}
def buffered_response_cb(data, command, rc, out, err):
    arg_search = re.search("([^\|]*)\|([^\|]*)\|(.*)", data)
    if not arg_search:
        weechat.prnt("", 'Bad usage of buffered response cb "{}"'.format(data))
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

enqueued_requests = []
def enqueue_request(method, *params):
    enqueued_requests.append([method, params])

def handle_queued_request_cb(data, remaining_calls):
    if not enqueued_requests:
        return weechat.WEECHAT_RC_OK

    request = enqueued_requests.pop(0)
    eval(request[0])(*request[1])
    return weechat.WEECHAT_RC_OK

def run_get_user_teams(server, cb, cb_data):
    url = server.url + "/api/v4/users/me/teams"
    weechat.hook_process_hashtable(
        "url:" + url,
        {
            "failonerror": "1",
            "httpheader": "Authorization: Bearer " + server.token,
        },
        30 * 1000,
        "buffered_response_cb",
        build_buffer_cb_data(url, cb, cb_data)
    )

def run_get_team(team_id, server, cb, cb_data):
    url = server.url + "/api/v4/teams/" + team_id
    weechat.hook_process_hashtable(
        "url:" + url,
        {
            "failonerror": "1",
            "httpheader": "Authorization: Bearer " + server.token,
        },
        30 * 1000,
        "buffered_response_cb",
        build_buffer_cb_data(url, cb, cb_data)
    )

def run_get_users(server, page, cb, cb_data):
    url = server.url + "/api/v4/users?page=" + str(page)
    weechat.hook_process_hashtable(
        "url:" + url,
        {
            "failonerror": "1",
            "httpheader": "Authorization: Bearer " + server.token,
        },
        30 * 1000,
        "buffered_response_cb",
        build_buffer_cb_data(url, cb, cb_data)
    )

def run_get_user(server, user_id, cb, cb_data):
    url = server.url + "/api/v4/users/" + user_id
    weechat.hook_process_hashtable(
        "url:" + url,
        {
            "failonerror": "1",
            "httpheader": "Authorization: Bearer " + server.token,
        },
        30 * 1000,
        "buffered_response_cb",
        build_buffer_cb_data(url, cb, cb_data)
    )

# Logging out synchronously for usage in shutdown function
def logout_user(server):
    url = server.url + "/api/v4/users/logout"
    req = urllib.request.Request(url)
    req.add_header("Authorization", "Bearer " + server.token)

    try:
        urllib.request.urlopen(req, b'', 10 * 1000)
    except:
        weechat.prnt("", "An error occurred while disconnecting")
        return weechat.WEECHAT_RC_ERROR

    weechat.prnt("", "Disconnected")
    return weechat.WEECHAT_RC_OK

def run_user_login(server, cb, cb_data):
    url = server.url + "/api/v4/users/login"
    params = {
        "login_id": server.username,
        "password": server.password,
    }

    if server.command_2fa:
        token = server.retrieve_2fa_token()
        if not token:
            return weechat.WEECHAT_RC_ERROR
        params["token"] = token

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
    url = server.url + "/api/v4/channels/" + channel_id
    weechat.hook_process_hashtable(
        "url:" + url,
        {
            "failonerror": "1",
            "httpheader": "Authorization: Bearer " + server.token,
        },
        30 * 1000,
        "buffered_response_cb",
        build_buffer_cb_data(url, cb, cb_data)
    )

def run_get_user_team_channels(team_id, server, cb, cb_data):
    url = server.url + "/api/v4/users/me/teams/" + team_id + "/channels"
    weechat.hook_process_hashtable(
        "url:" + url,
        {
            "failonerror": "1",
            "httpheader": "Authorization: Bearer " + server.token,
        },
        30 * 1000,
        "buffered_response_cb",
        build_buffer_cb_data(url, cb, cb_data)
    )

def run_post_post(post, server, cb, cb_data):
    url = server.url + "/api/v4/posts"
    params = {
        "channel_id": post["channel_id"],
        "message": post["message"],
    }

    if "root_id" in post:
        params["root_id"] = post["root_id"]

    weechat.hook_process_hashtable(
        "url:" + url,
        {
            "failonerror": "1",
            "httpheader": "Authorization: Bearer " + server.token,
            "postfields": json.dumps(params),
        },
        30 * 1000,
        "buffered_response_cb",
        build_buffer_cb_data(url, cb, cb_data)
    )

def run_post_command(channel_id, command, server, cb, cb_data):
    url = server.url + "/api/v4/commands/execute"
    params = {
        "channel_id": channel_id,
        "command": command,
    }

    weechat.hook_process_hashtable(
        "url:" + url,
        {
            "failonerror": "1",
            "httpheader": "Authorization: Bearer " + server.token,
            "postfields": json.dumps(params),
        },
        30 * 1000,
        "buffered_response_cb",
        build_buffer_cb_data(url, cb, cb_data)
    )

def run_get_read_channel_posts(channel_id, server, cb, cb_data):
    url = server.url + "/api/v4/users/me/channels/" + channel_id + "/posts/unread?limit_after=1"
    weechat.hook_process_hashtable(
        "url:" + url,
        {
            "failonerror": "1",
            "httpheader": "Authorization: Bearer " + server.token,
        },
        30 * 1000,
        "buffered_response_cb",
        build_buffer_cb_data(url, cb, cb_data)
    )

def run_get_channel_posts_after(post_id, channel_id, server, cb, cb_data):
    url = server.url + "/api/v4/channels/" + channel_id + "/posts?after=" + post_id
    weechat.hook_process_hashtable(
        "url:" + url,
        {
            "failonerror": "1",
            "httpheader": "Authorization: Bearer " + server.token,
        },
        30 * 1000,
        "buffered_response_cb",
        build_buffer_cb_data(url, cb, cb_data)
    )

def run_get_channel_members(channel_id, server, page, cb, cb_data):
    url = server.url + "/api/v4/channels/" + channel_id + "/members?page=" + str(page)
    weechat.hook_process_hashtable(
        "url:" + url,
        {
            "failonerror": "1",
            "httpheader": "Authorization: Bearer " + server.token,
        },
        30 * 1000,
        "buffered_response_cb",
        build_buffer_cb_data(url, cb, cb_data)
    )

def run_post_channel_view(channel_id, server, cb, cb_data):
    url = server.url + "/api/v4/channels/members/me/view"
    params = {
        "channel_id": channel_id,
    }

    weechat.hook_process_hashtable(
        "url:" + url,
        {
            "postfields": json.dumps(params),
            "failonerror": "1",
            "httpheader": "Authorization: Bearer " + server.token,
        },
        30 * 1000,
        "buffered_response_cb",
        build_buffer_cb_data(url, cb, cb_data)
    )

def run_post_reaction(emoji_name, post_id, server, cb, cb_data):
    url = server.url + "/api/v4/reactions"
    params = {
        "user_id": server.me.id,
        "post_id": post_id,
        "emoji_name": emoji_name,
        "create_at": int(time.time()),
    }

    weechat.hook_process_hashtable(
        "url:" + url,
        {
            "postfields": json.dumps(params),
            "failonerror": "1",
            "httpheader": "Authorization: Bearer " + server.token,
        },
        30 * 1000,
        "buffered_response_cb",
        build_buffer_cb_data(url, cb, cb_data)
    )

def run_delete_reaction(emoji_name, post_id, server, cb, cb_data):
    url = server.url + "/api/v4/users/me/posts/" + post_id + "/reactions/" + emoji_name

    weechat.hook_process_hashtable(
        "url:" + url,
        {
            "customrequest": "DELETE",
            "failonerror": "1",
            "httpheader": "Authorization: Bearer " + server.token,
        },
        30 * 1000,
        "buffered_response_cb",
        build_buffer_cb_data(url, cb, cb_data)
    )

def run_delete_post(post_id, server, cb, cb_data):
    url = server.url + "/api/v4/posts/" + post_id

    weechat.hook_process_hashtable(
        "url:" + url,
        {
            "customrequest": "DELETE",
            "failonerror": "1",
            "httpheader": "Authorization: Bearer " + server.token,
        },
        30 * 1000,
        "buffered_response_cb",
        build_buffer_cb_data(url, cb, cb_data)
    )

def run_get_file(file_id, file_out_path, server, cb, cb_data):
    url = server.url + "/api/v4/files/" + file_id

    weechat.hook_process_hashtable(
        "url:" + url,
        {
            "failonerror": "1",
            "file_out": file_out_path,
            "httpheader": "Authorization: Bearer " + server.token,
        },
        30 * 1000,
        "buffered_response_cb",
        build_buffer_cb_data(url, cb, cb_data)
    )

def run_get_preferences(server, cb, cb_data):
    url = server.url + "/api/v4/users/me/preferences"

    weechat.hook_process_hashtable(
        "url:" + url,
        {
            "failonerror": "1",
            "httpheader": "Authorization: Bearer " + server.token,
        },
        30 * 1000,
        "buffered_response_cb",
        build_buffer_cb_data(url, cb, cb_data)
    )
