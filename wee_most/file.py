
import weechat
import wee_most
import os, platform
from wee_most.globals import config

class File:
    def __init__(self, server, **kwargs):
        self.id = kwargs["id"]
        self.name = kwargs["name"]
        self.url = wee_most.http.build_file_url(kwargs["id"], server)

def prepare_download_location():
    location = config.download_location

    if not os.path.exists(location):
        try:
            os.makedirs(location)
        except:
            weechat.prnt("", "ERROR: Failed to create directory at files_download_location: {}"
                    .format(location))

    return location

def open_file(file_path):
    if platform.system() == "Darwin":       # macOS
        weechat.hook_process('open "{}"'.format(file_path), 100, "", "")
    elif platform.system() == "Windows":    # Windows
        os.startfile(file_path)
        weechat.hook_process(file_path, 100, "", "")
    else:                                   # linux variants
        weechat.hook_process('xdg-open "{}"'.format(file_path), 100, "", "")

def file_get_cb(file_path, command, rc, out, err):
    if rc != 0:
        weechat.prnt("", "An error occurred while downloading file")
        return weechat.WEECHAT_RC_ERROR

    open_file(file_path)

    return weechat.WEECHAT_RC_OK

def handle_file_click(data, info):
    tags = info["_chat_line_tags"].split(",")

    file_id = find_file_id_in_tags(tags)

    server = wee_most.server.get_server_from_buffer(info["_buffer"])

    file_path = prepare_download_location() + "/" + file_id

    if os.path.isfile(file_path):
        open_file(file_path)
    else:
        wee_most.http.run_get_file(file_id, file_path, server, "file_get_cb", file_path)

def find_file_id_in_tags(tags):
    for tag in tags:
        if tag.startswith("file_id_"):
            return tag[8:]

def get_files_from_post_data(post_data, server):
    if "files" in post_data["metadata"]:
        files = []
        for file_data in post_data["metadata"]["files"]:
            files.append(File(server, **file_data))
        return files

    return []

