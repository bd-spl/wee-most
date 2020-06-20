
import weechat
import json
from wee_matter.server import server_root_url

def write_post(buffer, post):
    weechat.prnt(buffer, post["user_id"] + "	" + post["message"])

def hidrate_room_cb(buffer, command, rc, out, err):
    if rc != 0:
        weechat.prnt("", "An error occured when hidrating room")

        return weechat.WEECHAT_RC_ERROR

    response = json.loads(out)

    for post_id in response["order"]:
        write_post(buffer, response["posts"][post_id])

    return weechat.WEECHAT_RC_OK

def create_room(data, server):
    buffer = weechat.buffer_new(data["display_name"], "", "", "", "")

    weechat.buffer_set(buffer, "server_name", server.name)
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

