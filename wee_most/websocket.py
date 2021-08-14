
import weechat
import time
import wee_most
import json
import socket
from websocket import (create_connection, WebSocketConnectionClosedException,
                       WebSocketTimeoutException, ABNF)
from typing import NamedTuple
from ssl import SSLWantReadError
from wee_most.globals import servers

Worker = NamedTuple(
    "Worker",
    [
        ("ws", any),
        ("hook_data_read", any),
        ("hook_ping", any),
        ("last_ping_time", int),
        ("last_pong_time", int),
    ]
)

def create_worker(server):
    url = server.url.replace('http', 'ws', 1) + "/api/v4/websocket"
    try:
        ws = create_connection(url)
        ws.sock.setblocking(0)
    except:
        return

    params = {
        "seq": 1,
        "action": "authentication_challenge",
        "data": {
            "token": server.token,
        }
    }

    hook_data_read = weechat.hook_fd(ws.sock.fileno(), 1, 0, 0, "receive_ws_callback", server.id)
    ws.send(json.dumps(params))

    hook_ping = weechat.hook_timer(5 * 1000, 0, 0, "ws_ping_cb", server.id)

    return Worker(
        ws= ws,
        hook_data_read= hook_data_read,
        hook_ping= hook_ping,
        last_ping_time= 0,
        last_pong_time= 0,
    )

def rehydrate_server_buffer(server, buffer):
    last_post_id = weechat.buffer_get_string(buffer, "localvar_last_post_id")
    channel_id = weechat.buffer_get_string(buffer, "localvar_channel_id")
    wee_most.channel.register_buffer_hydratating(channel_id)
    wee_most.http.enqueue_request(
        "run_get_channel_posts_after",
        last_post_id, channel_id, server, "hydrate_channel_posts_cb", buffer
    )

def rehydrate_server_buffers(server):
    weechat.prnt("", "Syncing...")
    for channel in server.channels.values():
        rehydrate_server_buffer(server, channel.buffer)
    for team in server.teams.values():
        for channel in team.channels.values():
            rehydrate_server_buffer(server, channel.buffer)

def reconnection_loop_cb(server_id, remaining_calls):
    server = servers[server_id]
    if server != None and server.is_connected():
        return weechat.WEECHAT_RC_OK

    weechat.prnt("", "Reconnecting...")

    new_worker = create_worker(server)
    if new_worker:
        server.worker = new_worker
        weechat.prnt("", "Reconnected.")
        rehydrate_server_buffers(server)
        return weechat.WEECHAT_RC_OK

    weechat.prnt("", "Reconnection issue. Trying again in a few seconds...")
    return weechat.WEECHAT_RC_ERROR

def close_worker(worker):
    weechat.unhook(worker.hook_data_read)
    weechat.unhook(worker.hook_ping)
    worker.ws.close()

def handle_lost_connection(server):
    weechat.prnt("", "Connection lost.")
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
        worker = worker._replace(last_ping_time=time.time())
        server.worker = worker
    except (WebSocketConnectionClosedException, socket.error) as e:
        handle_lost_connection(server)

    return weechat.WEECHAT_RC_OK

def handle_posted_message(server, message):
    data = message["data"]
    post = json.loads(data["post"])
    broadcast = message["broadcast"]

    if data["team_id"] and data["team_id"] not in server.teams:
        return

    if wee_most.channel.is_buffer_hydratating(broadcast["channel_id"]):
        return

    post = wee_most.post.Post(server, **post)
    wee_most.post.write_post(post)

    buffer = post.channel.buffer

    if buffer == weechat.current_buffer():
        wee_most.channel.mark_channel_as_read(buffer)

def handle_reaction_added_message(server, message):
    data = message["data"]

    reaction_data = json.loads(data["reaction"])

    reaction = wee_most.post.get_reaction_from_reaction_data(reaction_data, server)
    post = server.get_post(reaction_data["post_id"])
    buffer = post.channel.buffer

    wee_most.post.add_reaction_to_post(buffer, reaction)

def handle_reaction_removed_message(server, message):
    data = message["data"]

    reaction_data = json.loads(data["reaction"])

    reaction = wee_most.post.get_reaction_from_reaction_data(reaction_data, server)
    post = server.get_post(reaction_data["post_id"])
    buffer = post.channel.buffer

    wee_most.post.remove_reaction_from_post(buffer, reaction)

def handle_post_edited_message(server, message):
    data = message["data"]

    post_data = json.loads(data["post"])
    post = wee_most.post.Post(server, **post_data)
    wee_most.post.write_post_edited(post)

def handle_post_deleted_message(server, message):
    data = message["data"]

    post_data = json.loads(data["post"])
    post = wee_most.post.Post(server, **post_data)
    wee_most.post.write_post_deleted(post)

def handle_channel_created_message(server, message):
    data = message["data"]

    wee_most.server.connect_server_team_channel(data["channel_id"], server)

def handle_channel_updated_message(server, message):
    data = message["data"]

    channel_data = json.loads(data["channel"])
    wee_most.channel.set_channel_properties_from_channel_data(channel_data, server)

def handle_channel_viewed_message(server, message):
    data = message["data"]

    buffer = wee_most.channel.get_buffer_from_channel_id(data["channel_id"])
    if buffer:
        weechat.buffer_set(buffer, "unread", "-")
        weechat.buffer_set(buffer, "hotlist", "-1")

        last_post_id = weechat.buffer_get_string(buffer, "localvar_last_post_id")
        weechat.buffer_set(buffer, "localvar_set_last_read_post_id", last_post_id)

def handle_user_added_message(server, message):
    data = message["data"]
    broadcast = message["broadcast"]

    if data["user_id"] == server.me.id: # we are geing invited
        wee_most.server.connect_server_team_channel(broadcast["channel_id"], server)
    else:
        buffer = wee_most.channel.get_buffer_from_channel_id(broadcast["channel_id"])
        wee_most.channel.create_channel_user_from_user_data(data, buffer, server)

def handle_channel_added_message(server, message):
    broadcast = message["broadcast"]
    wee_most.server.connect_server_team_channel(broadcast["channel_id"], server)

def handle_direct_added_message(server, message):
    handle_channel_added_message(server, message)

def handle_group_added_message(server, message):
    handle_channel_added_message(server, message)

def handle_new_user_message(server, message):
    user_id = message["data"]["user_id"]
    wee_most.http.enqueue_request(
        "run_get_user",
        server, user_id, "new_user_cb", server.id
    )

def handle_user_removed_message(server, message):
    data = message["data"]
    broadcast = message["broadcast"]

    if broadcast["channel_id"]:
        user = server.users[data["user_id"]]
        buffer = wee_most.channel.get_buffer_from_channel_id(broadcast["channel_id"])
        wee_most.channel.remove_channel_user(buffer, user)

def handle_added_to_team_message(server, message):
    data = message["data"]

    user = server.users[data["user_id"]]

    server.teams[data["team_id"]] = None

    wee_most.http.enqueue_request(
        "run_get_team",
        data["team_id"], server, "connect_server_team_cb", server.id
    )

def handle_leave_team_message(server, message):
    data = message["data"]

    user = server.users[data["user_id"]]
    team = server.teams.pop(data["team_id"])
    team.unload()

def handle_ws_event_message(server, message):
    if "posted" == message["event"]:
        return handle_posted_message(server, message)
    if "reaction_added" == message["event"]:
        return handle_reaction_added_message(server, message)
    if "reaction_removed" == message["event"]:
        return handle_reaction_removed_message(server, message)
    if "post_edited" == message["event"]:
        return handle_post_edited_message(server, message)
    if "post_deleted" == message["event"]:
        return handle_post_deleted_message(server, message)
    if "channel_created" == message["event"]:
        return handle_channel_created_message(server, message)
    if "channel_updated" == message["event"]:
        return handle_channel_updated_message(server, message)
    if "channel_viewed" == message["event"]:
        return handle_channel_viewed_message(server, message)
    if "new_user" == message["event"]:
        return handle_new_user_message(server, message)
    if "direct_added" == message["event"]:
        return handle_direct_added_message(server, message)
    if "group_added" == message["event"]:
        return handle_direct_added_message(server, message)
    if "user_added" == message["event"]:
        return handle_user_added_message(server, message)
    if "user_removed" == message["event"]:
        return handle_user_removed_message(server, message)
    if "added_to_team" == message["event"]:
        return handle_added_to_team_message(server, message)
    if "leave_team" == message["event"]:
        return handle_leave_team_message(server, message)

def handle_ws_message(server, message):
    if "event" in message:
        handle_ws_event_message(server, message)

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
            worker = worker._replace(last_pong_time=time.time())
            server.worker = worker
            return weechat.WEECHAT_RC_OK

        if data:
            message = json.loads(data.decode('utf-8'))
            handle_ws_message(server, message)

    return weechat.WEECHAT_RC_OK

