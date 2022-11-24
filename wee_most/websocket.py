
import weechat
import time
import wee_most
import json
import socket
from websocket import (create_connection, WebSocketConnectionClosedException,
                       WebSocketTimeoutException, ABNF)
from ssl import SSLWantReadError
from wee_most.globals import servers

class Worker:
    def __init__(self, server):
        self.last_ping_time = 0
        self.last_pong_time = 0

        url = server.url.replace("http", "ws", 1) + "/api/v4/websocket"
        self.ws = create_connection(url)
        self.ws.sock.setblocking(0)

        params = {
            "seq": 1,
            "action": "authentication_challenge",
            "data": {
                "token": server.token,
            }
        }

        self.hook_data_read = weechat.hook_fd(self.ws.sock.fileno(), 1, 0, 0, "receive_ws_callback", server.id)
        self.ws.send(json.dumps(params))

        self.hook_ping = weechat.hook_timer(5 * 1000, 0, 0, "ws_ping_cb", server.id)

def rehydrate_server_buffer(server, buffer):
    last_post_id = weechat.buffer_get_string(buffer, "localvar_last_post_id")
    channel_id = weechat.buffer_get_string(buffer, "localvar_channel_id")

    channel = server.get_channel(channel_id)
    if not channel:
        return
    channel.set_loading(True)

    wee_most.http.enqueue_request(
        "run_get_channel_posts_after",
        last_post_id, channel_id, server, "hydrate_channel_posts_cb", buffer
    )

def rehydrate_server_buffers(server):
    server.print("Syncing...")
    for channel in server.channels.values():
        rehydrate_server_buffer(server, channel.buffer)
    for team in server.teams.values():
        for channel in team.channels.values():
            rehydrate_server_buffer(server, channel.buffer)

def reconnection_loop_cb(server_id, remaining_calls):
    server = servers[server_id]
    if server != None and server.is_connected():
        return weechat.WEECHAT_RC_OK

    server.print("Reconnecting...")

    try:
        new_worker = Worker(server)
    except:
        server.print_error("Reconnection issue. Trying again in a few seconds...")
        return weechat.WEECHAT_RC_ERROR

    server.worker = new_worker
    server.print("Reconnected.")
    rehydrate_server_buffers(server)
    return weechat.WEECHAT_RC_OK

def close_worker(worker):
    weechat.unhook(worker.hook_data_read)
    weechat.unhook(worker.hook_ping)
    worker.ws.close()

def handle_lost_connection(server):
    server.print("Connection lost.")
    close_worker(server.worker)
    server.worker = None

def ws_ping_cb(server_id, remaining_calls):
    server = servers[server_id]
    worker = server.worker

    if worker.last_pong_time < worker.last_ping_time:
        handle_lost_connection(server)
        return weechat.WEECHAT_RC_OK

    try:
        worker.ws.ping()
        worker.last_ping_time = time.time()
        server.worker = worker
    except (WebSocketConnectionClosedException, socket.error) as e:
        handle_lost_connection(server)

    return weechat.WEECHAT_RC_OK

def handle_posted_message(server, data, broadcast):
    post = json.loads(data["post"])

    if data["team_id"] and data["team_id"] not in server.teams:
        return

    channel = server.get_channel(broadcast["channel_id"])
    if not channel or channel.is_loading():
        return

    post = wee_most.post.Post(server, **post)
    wee_most.post.write_post(post)

    if post.buffer == weechat.current_buffer():
        post.channel.mark_as_read()

def handle_reaction_added_message(server, data, broadcast):
    reaction_data = json.loads(data["reaction"])

    reaction = wee_most.post.Reaction(server, **reaction_data)

    wee_most.post.add_reaction_to_post(reaction)

def handle_reaction_removed_message(server, data, broadcast):
    reaction_data = json.loads(data["reaction"])

    reaction = wee_most.post.Reaction(server, **reaction_data)

    wee_most.post.remove_reaction_from_post(reaction)

def handle_post_edited_message(server, data, broadcast):
    post_data = json.loads(data["post"])
    post = wee_most.post.Post(server, **post_data)
    wee_most.post.write_post_edited(post)

def handle_post_deleted_message(server, data, broadcast):
    post_data = json.loads(data["post"])
    post = wee_most.post.Post(server, **post_data)
    wee_most.post.write_post_deleted(post)

def handle_channel_created_message(server, data, broadcast):
    wee_most.server.connect_server_team_channel(data["channel_id"], server)

def handle_channel_member_updated_message(server, data, broadcast):
    channel_member_data = json.loads(data["channelMember"])
    if channel_member_data["user_id"] == server.me.id:
        channel = server.get_channel(channel_member_data["channel_id"])
        if channel:
            if channel_member_data["notify_props"]["mark_unread"] == "all":
                channel.unmute()
            else:
                channel.mute()

def handle_channel_updated_message(server, data, broadcast):
    channel_data = json.loads(data["channel"])
    wee_most.channel.set_channel_properties_from_channel_data(channel_data, server)

def handle_channel_viewed_message(server, data, broadcast):
    channel = server.get_channel(data["channel_id"])

    if channel:
        weechat.buffer_set(channel.buffer, "unread", "-")
        weechat.buffer_set(channel.buffer, "hotlist", "-1")

        last_post_id = weechat.buffer_get_string(channel.buffer, "localvar_last_post_id")
        weechat.buffer_set(channel.buffer, "localvar_set_last_read_post_id", last_post_id)

def handle_user_added_message(server, data, broadcast):
    if data["user_id"] == server.me.id: # we are geing invited
        wee_most.server.connect_server_team_channel(broadcast["channel_id"], server)
    else:
        channel = server.get_channel(broadcast["channel_id"])
        channel.add_user(data["user_id"])

def handle_group_added_message(server, data, broadcast):
    wee_most.server.connect_server_team_channel(broadcast["channel_id"], server)

def handle_direct_added_message(server, data, broadcast):
    wee_most.server.connect_server_team_channel(broadcast["channel_id"], server)

def handle_group_added_message(server, data, broadcast):
    wee_most.server.connect_server_team_channel(broadcast["channel_id"], server)

def handle_new_user_message(server, data, broadcast):
    user_id = data["user_id"]
    wee_most.http.enqueue_request(
        "run_get_user",
        server, user_id, "new_user_cb", server.id
    )

def handle_user_removed_message(server, data, broadcast):
    if broadcast["channel_id"]:
        user = server.users[data["user_id"]]
        buffer = server.get_channel(broadcast["channel_id"]).buffer
        wee_most.channel.remove_channel_user(buffer, user)

def handle_added_to_team_message(server, data, broadcast):
    user = server.users[data["user_id"]]

    server.teams[data["team_id"]] = None

    wee_most.http.enqueue_request(
        "run_get_team",
        data["team_id"], server, "connect_server_team_cb", server.id
    )

def handle_leave_team_message(server, data, broadcast):
    user = server.users[data["user_id"]]
    team = server.teams.pop(data["team_id"])
    team.unload()

def handle_status_change_message(server, data, broadcast):
    # this event seems only to be triggered on own user
    user_id = data["user_id"]

    if user_id not in server.users:
        return

    user = server.users[user_id]
    user.status = data["status"]

    buffer = weechat.current_buffer()
    channel = server.get_channel_from_buffer(buffer)
    if channel and user_id in channel.users:
        channel.update_nicklist_user(user)
        channel.remove_empty_nick_groups()

    user_dm_channel = server.get_direct_messages_channel(user.id)
    if user_dm_channel:
        user_dm_channel.set_status(user.status)

def receive_ws_callback(server_id, data):
    server = servers[server_id]
    worker = server.worker

    while True:
        try:
            opcode, data = worker.ws.recv_data(control_frame=True)
        except SSLWantReadError:
            return weechat.WEECHAT_RC_OK
        except (WebSocketConnectionClosedException, socket.error) as e:
            return weechat.WEECHAT_RC_OK

        if opcode == ABNF.OPCODE_PONG:
            worker.last_pong_time = time.time()
            server.worker = worker
            return weechat.WEECHAT_RC_OK

        if data:
            message = json.loads(data.decode("utf-8"))
            if "event" in message:
                handler_function_name = "handle_" + message["event"] + "_message"
                if handler_function_name not in globals():
                    return weechat.WEECHAT_RC_OK
                globals()[handler_function_name](server, message["data"], message["broadcast"])

    return weechat.WEECHAT_RC_OK

