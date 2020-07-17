
configs = {
    "basic": {
        "address": "foo.bar",
        "port": "443",
        "protocol": "https",
        "username": "sarah",
        "password": "connors",
    }
}

def get_server_config(server_name, key):
    return configs[server_name][key]
