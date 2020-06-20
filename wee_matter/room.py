
import weechat

def create_room(data, server):
    buffer = weechat.buffer_new(data["display_name"], "", "", "", "")

    weechat.buffer_set(buffer, "server_name", server.name)

