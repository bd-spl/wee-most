
import weechat
from wee_matter.server import Server, get_server
from websocket import create_connection, WebSocketConnectionClosedException
from wee_matter.room import Post, write_post, build_buffer_room_name
from typing import NamedTuple
import json
import socket
import ssl

Worker = NamedTuple(
    "Worker",
    [
        ("ws", any),
        ("hook", any),
    ]
)

def server_root_url(server: Server):
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

    buffer_name = build_buffer_room_name(post["channel_id"])
    buffer = weechat.buffer_search("", buffer_name)
    channel_id = weechat.buffer_get_string(buffer, "localvar_channel_id"),

    username = post["user_id"]
    if username in server.users:
        username = server.users[username].username

    post = Post(
        id= post["id"],
        user_name= username,
        channel_id= channel_id,
        message= post["message"],
        date= int(post["create_at"]/1000),
    )

    write_post(buffer, post)

def handle_ws_event_message(server, message):
    if "posted" == message["event"]:
        return handle_posted_message(server, message)

def handle_ws_message(server, message):
    if "event" in message:
        handle_ws_event_message(server, message)

def receive_ws_callback(server_name, data):
    server = get_server(server_name)
    ws = server.worker.ws

    while True:
        try:
            opcode, data = ws.recv_data(control_frame=True)
        except ssl.SSLWantReadError:
            return weechat.WEECHAT_RC_OK
        except (WebSocketConnectionClosedException, socket.error) as e:
            return weechat.WEECHAT_RC_OK

        if data:
            message = json.loads(data.decode('utf-8'))
            handle_ws_message(server, message)

    return weechat.WEECHAT_RC_OK
