
import weechat

def download_location():
    return weechat.config_get_plugin("download_location")

def setup_download_location():
    if not weechat.config_is_set_plugin("download_location"):
        cache_root = weechat.string_eval_expression("${env:XDG_CACHE_HOME}/wee-matter", {}, {}, {})
        if not cache_root:
            cache_root = weechat.string_eval_path_home("~/.cache/wee-matter", {}, {}, {})

        weechat.config_set_plugin("download_location", cache_root + "/downloads")

def setup():
    setup_download_location()
