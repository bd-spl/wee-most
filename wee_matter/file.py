
import weechat
import wee_matter
import os, platform
from typing import NamedTuple

File = NamedTuple(
    "File",
    [
        ("id", str),
        ("name", str),
        ("url", str),
    ]
)

def write_file_lines(buffer, post):
    for file in post.files:
        weechat.prnt_date_tags(
            buffer,
            post.date,
            "file_id_" + file.id,
            "	[{}]({})".format(file.name, file.url)
        )

def prepare_download_location():
    location = wee_matter.config.download_location()

    if not os.path.exists(location):
        try:
            os.makedirs(location)
        except:
            weechat.prnt('', 'ERROR: Failed to create directory at files_download_location: {}'
                    .format(location))

    return location

def open_file(file_path):
    if platform.system() == 'Darwin':       # macOS
        weechat.hook_process("open \"{}\"".format(file_path), 100, "", "")
    elif platform.system() == 'Windows':    # Windows
        os.startfile(file_path)
        weechat.hook_process(file_path, 100, "", "")
    else:                                   # linux variants
        weechat.hook_process("xdg-open \"{}\"".format(file_path), 100, "", "")

def file_get_cb(file_path, command, rc, out, err):
    if rc != 0:
        weechat.prnt("", "An error occurred while downloading file")
        return weechat.WEECHAT_RC_ERROR

    open_file(file_path)

    return weechat.WEECHAT_RC_OK

def handle_file_click(data, info):
    tags = info["_chat_line_tags"].split(",")

    file_id = find_file_id_in_tags(tags)

    server = wee_matter.server.get_server_from_buffer(info["_buffer"])

    file_path = prepare_download_location() + "/" + file_id

    if os.path.isfile(file_path):
        open_file(file_path)
    else:
        wee_matter.http.run_get_file(file_id, file_path, server, "file_get_cb", file_path)

def find_file_id_in_tags(tags):
    for tag in tags:
        if tag.startswith("file_id_"):
            return tag[8:]

def get_files_from_post_data(post_data, server):
    if "files" in post_data["metadata"]:
        files = []
        for file_data in post_data["metadata"]["files"]:
            files.append(
                File(
                    id= file_data["id"],
                    name= file_data["name"],
                    url= wee_matter.http.build_file_url(file_data["id"], server)
                )
            )
        return files

    return []

