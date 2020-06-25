
import weechat
import time
from wee_matter.server import get_server, update_server, is_connected
from websocket import (create_connection, WebSocketConnectionClosedException,
                       WebSocketTimeoutException, ABNF)
from wee_matter.room import (write_post_from_post_data, build_buffer_room_name,
                             mark_channel_as_read, get_reaction_from_reaction_data,
                             add_reaction_to_post, remove_reaction_from_post,
                             get_buffer_from_post_id, get_buffer_from_channel_id)
from typing import NamedTuple
import json
import socket
from ssl import SSLWantReadError

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

def server_root_url(server):
    protocol = "ws"
    if "https" == server.protocol:
        protocol = "wss"

    root_url = "{}://{}:{}".format(protocol, server.host, server.port)
    if server.path:
        root_url += "/{}".format(server.port)

    return root_url

def create_worker(server):
    url = server_root_url(server) + "/api/v4/websocket"
    try:
        ws = create_connection(url)
        ws.sock.setblocking(0)
    except:
        return

    params = {
        "seq": 1,
        "action": "authentication_challenge",
        "data": {
            "token": server.user_token,
        }
    }

    hook_data_read = weechat.hook_fd(ws.sock.fileno(), 1, 0, 0, "receive_ws_callback", server.name)
    ws.send(json.dumps(params))

    hook_ping = weechat.hook_timer(5 * 1000, 0, 0, "ws_ping_cb", server.name)

    return Worker(
        ws= ws,
        hook_data_read= hook_data_read,
        hook_ping= hook_ping,
        last_ping_time= 0,
        last_pong_time= 0,
    )

def reconnection_loop_cb(server_name, remaining_calls):
    server = get_server(server_name)
    if server != None and is_connected(server):
        return weechat.WEECHAT_RC_OK

    weechat.prnt("", "Reconnecting...")

    new_worker = create_worker(server)
    if new_worker:
        server = server._replace(worker=new_worker)
        update_server(server)
        weechat.prnt("", "Connected back.")
        return weechat.WEECHAT_RC_OK

    weechat.prnt("", "Reconnection issue. Trying again in some seconds...")
    return weechat.WEECHAT_RC_ERROR

def close_worker(worker):
    weechat.unhook(worker.hook_data_read)
    weechat.unhook(worker.hook_ping)
    worker.ws.close()

def ws_ping_cb(server_name, remaining_calls):
    server = get_server(server_name)
    worker = server.worker

    if worker.last_pong_time < worker.last_ping_time:
        weechat.prnt("", "Loosed connection.")
        close_worker(server.worker)
        server = server._replace(worker=None)
        update_server(server)
        return weechat.WEECHAT_RC_OK

    try:
        result = worker.ws.ping()
        worker = worker._replace(last_ping_time=time.time())
        server = server._replace(worker=worker)
        update_server(server)
    except (WebSocketConnectionClosedException, socket.error) as e:
        close_worker(server.worker)
        server = server._replace(worker=None)
        update_server(server)
        return weechat.WEECHAT_RC_OK

    return weechat.WEECHAT_RC_OK

def handle_posted_message(server, message):
    data = message["data"]
    post = json.loads(data["post"])

    write_post_from_post_data(post)

    buffer = get_buffer_from_channel_id(post["channel_id"])
    if not buffer:
        return

    if buffer == weechat.current_buffer():
        mark_channel_as_read(buffer)

def handle_reaction_added_message(server, message):
    data = message["data"]

    reaction_data = json.loads(data["reaction"])

    reaction = get_reaction_from_reaction_data(reaction_data, server)
    buffer = get_buffer_from_post_id(reaction_data["post_id"])

    if not buffer or not reaction:
        return

    reaction = get_reaction_from_reaction_data(reaction_data, server)
    add_reaction_to_post(buffer, reaction)

def handle_reaction_removed_message(server, message):
    data = message["data"]

    reaction_data = json.loads(data["reaction"])

    reaction = get_reaction_from_reaction_data(reaction_data, server)
    buffer = get_buffer_from_post_id(reaction_data["post_id"])

    if not buffer or not reaction:
        return

    remove_reaction_from_post(buffer, reaction)

def handle_ws_event_message(server, message):
    if "posted" == message["event"]:
        return handle_posted_message(server, message)
    if "reaction_added" == message["event"]:
        return handle_reaction_added_message(server, message)
    if "reaction_removed" == message["event"]:
        return handle_reaction_removed_message(server, message)

def handle_ws_message(server, message):
    if "event" in message:
        handle_ws_event_message(server, message)

def receive_ws_callback(server_name, data):
    server = get_server(server_name)
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
            server = server._replace(worker=worker)
            update_server(server)
            return weechat.WEECHAT_RC_OK

        if data:
            message = json.loads(data.decode('utf-8'))
            handle_ws_message(server, message)

    return weechat.WEECHAT_RC_OK

