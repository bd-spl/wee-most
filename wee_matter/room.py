
import weechat
import json
from wee_matter.server import server_root_url, get_server

def post_post_cb(buffer, command, rc, out, err):
    if rc != 0:
        weechat.prnt(buffer, "Can't send post")
        return weechat.WEECHAT_RC_ERROR

    return weechat.WEECHAT_RC_OK

def room_input_cb(data, buffer, input_data):
    server_name = weechat.buffer_get_string(buffer, "localvar_server_name")
    server = get_server(server_name)

    url = server_root_url(server) + "/api/v4/posts"
    params = {
        "channel_id": weechat.buffer_get_string(buffer, "localvar_channel_id"),
        "message": input_data,
    }

    weechat.hook_process_hashtable(
        "url:" + url,
        {
            "failonerror": "1",
            "httpheader": "Authorization: Bearer " + server.user_token,
            "postfields": json.dumps(params),
        },
        30 * 1000,
        "post_post_cb",
        buffer
    )
    return weechat.WEECHAT_RC_OK


def write_post(buffer, username, message, date):
    weechat.prnt_date_tags(buffer, date, "", username + "	" + message)

def hidrate_room_cb(buffer, command, rc, out, err):
    if rc != 0:
        weechat.prnt("", "An error occured when hidrating room")

        return weechat.WEECHAT_RC_ERROR

    server_name = weechat.buffer_get_string(buffer, "localvar_server_name")
    server = get_server(server_name)

    response = json.loads(out)

    response["order"].reverse()
    for post_id in response["order"]:
        post = response["posts"][post_id]
        message = post["message"]
        username = post["user_id"]
        if username in server.users:
            username = server.users[username].username
        write_post(buffer, username, message, int(post["create_at"]/1000))

    return weechat.WEECHAT_RC_OK

def hidrate_room_users_cb(buffer, command, rc, out, err):
    if rc != 0:
        weechat.prnt("", "An error occured when hidrating room users")
        return weechat.WEECHAT_RC_ERROR

    response = json.loads(out)

    server_name = weechat.buffer_get_string(buffer, "localvar_server_name")
    server = get_server(server_name)

    for user in response:
        for role in user["roles"].split():
            group_name = role.replace("channel_", "")
            group = weechat.nicklist_search_group(buffer, "", group_name)
            if not group:
                weechat.nicklist_add_group(buffer, "", group_name, "", 1)

            username = user["user_id"]
            if username in server.users:
                username = server.users[username].username

            weechat.nicklist_add_nick(buffer, group, "@" + username, "", "", "", 1)

    return weechat.WEECHAT_RC_OK

def create_room(data, server):
    room_name = data["display_name"]
    if "" == room_name:
        return

    buffer = weechat.buffer_new(room_name, "room_input_cb", "", "", "")

    weechat.buffer_set(buffer, "localvar_set_server_name", server.name)
    weechat.buffer_set(buffer, "localvar_set_channel_id", data["id"])

    weechat.buffer_set(buffer, "nicklist", "1")

    if data["team_id"]:
        weechat.buffer_set(buffer, "localvar_set_type", "channel")
        team = server.teams[data["team_id"]]
        weechat.buffer_set(buffer, "localvar_set_server", team.display_name)
        parent_number = weechat.buffer_get_integer(team.buffer, "number")
        number = parent_number + 1 + len(team.buffers)
        team.buffers.append(buffer)
    else:
        weechat.buffer_set(buffer, "localvar_set_type", "private")
        weechat.buffer_set(buffer, "localvar_set_server", server.name)
        parent_number = weechat.buffer_get_integer(server.buffer, "number")
        number = parent_number + 1 + len(server.buffers)
        server.buffers.append(buffer)

    weechat.buffer_set(buffer, "number", str(number))

    url = server_root_url(server) + "/api/v4/channels/" + data["id"] + "/posts"
    weechat.hook_process_hashtable(
        "url:" + url,
        {
            "httpheader": "Authorization: Bearer " + server.user_token,
        },
        30 * 1000,
        "hidrate_room_cb",
        buffer
    )

    url = server_root_url(server) + "/api/v4/channels/" + data["id"] + "/members"
    weechat.hook_process_hashtable(
        "url:" + url,
        {
            "httpheader": "Authorization: Bearer " + server.user_token,
        },
        30 * 1000,
        "hidrate_room_users_cb",
        buffer
    )

