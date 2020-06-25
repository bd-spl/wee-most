
import weechat
from wee_matter.server import get_server
from websocket import create_connection, WebSocketConnectionClosedException
from wee_matter.room import (write_post_from_post_data, build_buffer_room_name,
                             mark_channel_as_read, get_reaction_from_reaction_data,
                             add_reaction_to_post, remove_reaction_from_post,
                             get_buffer_from_post_id)
from typing import NamedTuple
import json
import socket
from ssl import SSLWantReadError

Worker = NamedTuple(
    "Worker",
    [
        ("ws", any),
        ("hook", any),
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
    ws = create_connection(url)
    ws.sock.setblocking(0)

    params = {
        "seq": 1,
        "action": "authentication_challenge",
        "data": {
            "token": server.user_token,
        }
    }

    hook = weechat.hook_fd(ws.sock.fileno(), 1, 0, 0, "receive_ws_callback", server.name)
    ws.send(json.dumps(params))

    return Worker(
        ws= ws,
        hook= hook,
    )

def close_worker(worker):
    weechat.unhook(worker.hook)
    worker.ws.close()

def handle_posted_message(server, message):
    data = message["data"]
    post = json.loads(data["post"])

    write_post_from_post_data(post)

    buffer_name = build_buffer_room_name(post["channel_id"])
    buffer = weechat.buffer_search("", buffer_name)
    if buffer == weechat.current_buffer():
        mark_channel_as_read(buffer)

def handle_reaction_added_message(server, message):
    data = message["data"]

    reaction_data = json.loads(data["reaction"])

    reaction = get_reaction_from_reaction_data(reaction_data, server)
    if not reaction:
        return
    buffer = get_buffer_from_post_id(reaction_data["post_id"])

    reaction = get_reaction_from_reaction_data(reaction_data, server)
    add_reaction_to_post(buffer, reaction)

def handle_reaction_removed_message(server, message):
    data = message["data"]

    reaction_data = json.loads(data["reaction"])

    reaction = get_reaction_from_reaction_data(reaction_data, server)
    if not reaction:
        return
    buffer = get_buffer_from_post_id(reaction_data["post_id"])

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
    ws = server.worker.ws

    while True:
        try:
            opcode, data = ws.recv_data(control_frame=True)
        except SSLWantReadError:
            return weechat.WEECHAT_RC_OK
        except (WebSocketConnectionClosedException, socket.error) as e:
            return weechat.WEECHAT_RC_OK

        if data:
            message = json.loads(data.decode('utf-8'))
            handle_ws_message(server, message)

    return weechat.WEECHAT_RC_OK
