
import weechat
import json
from wee_matter.server import server_root_url, get_server

def write_post(buffer, username, message):
    weechat.prnt(buffer, username + "	" + message)

def hidrate_room_cb(buffer, command, rc, out, err):
    if rc != 0:
        weechat.prnt("", "An error occured when hidrating room")

        return weechat.WEECHAT_RC_ERROR

    server_name = weechat.buffer_get_string(buffer, "localvar_server_name")
    server = get_server(server_name)

    response = json.loads(out)

    for post_id in response["order"]:
        message = response["posts"][post_id]["message"]
        username = response["posts"][post_id]["user_id"]
        if username in server.users:
            username = server.users[username].username
        write_post(buffer, username, message)

    return weechat.WEECHAT_RC_OK

def create_room(data, server):
    room_name = data["display_name"]
    if "" == room_name:
        return
    buffer = weechat.buffer_new(room_name, "", "", "", "")

    weechat.buffer_set(buffer, "localvar_set_server_name", server.name)
    weechat.buffer_set(buffer, "channel_id", data["id"])

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

