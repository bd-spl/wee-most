
import weechat
import json
from wee_matter.server import server_root_url, get_server

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

    buffer = weechat.buffer_new(room_name, "", "", "", "")

    weechat.buffer_set(buffer, "localvar_set_server_name", server.name)
    weechat.buffer_set(buffer, "localvar_set_channel_id", data["id"])

    if data["team_id"]:
        weechat.buffer_set(buffer, "localvar_set_type", "channel")
        weechat.buffer_set(buffer, "localvar_set_server", server.teams[data["team_id"]].display_name)
    else:
        weechat.buffer_set(buffer, "localvar_set_type", "private")
        weechat.buffer_set(buffer, "localvar_set_server", server.name)

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

