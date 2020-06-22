
import weechat
from wee_matter.server import Server, get_server
from websocket import create_connection, WebSocketConnectionClosedException
from wee_matter.room import write_post, build_buffer_room_name
import json
import socket
import ssl

websockets = {}

def get_ws(server_name):
    if server_name not in websockets:
        weechat.prnt("", "Websocket is not loaded")
        return

    return websockets[server_name]

def server_root_url(server: Server):
    protocol = "ws"
    if "https" == server.protocol:
        protocol = "wss"

    root_url = "{}://{}:{}".format(protocol, server.host, server.port)
    if server.path:
        root_url += "/{}".format(server.port)

    return root_url

def create_ws(server):
    url = server_root_url(server) + "/api/v4/websocket"
    ws = create_connection(url)
    ws.sock.setblocking(0)
    websockets[server.name] = ws

    params = {
        "seq": 1,
        "action": "authentication_challenge",
        "data": {
            "token": server.user_token,
        }
    }

    weechat.hook_fd(ws.sock.fileno(), 1, 0, 0, "receive_ws_callback", server.name)
    ws.send(json.dumps(params))

    return ws

def handle_posted_message(server, message):
    data = message["data"]
    post = json.loads(data["post"])

    buffer_name = build_buffer_room_name(post["channel_id"])
    buffer = weechat.buffer_search("", buffer_name)

    username = post["user_id"]
    if username in server.users:
        username = server.users[username].username

    write_post(buffer, username, post["message"], int(post["create_at"]/1000))

def handle_ws_event_message(server, message):
    if "posted" == message["event"]:
        return handle_posted_message(server, message)

def handle_ws_message(server, message):
    if "event" in message:
        handle_ws_event_message(server, message)

def receive_ws_callback(server_name, data):
    ws = get_ws(server_name)
    server = get_server(server_name)

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
