# Wee-Matter

Wee-Matter is a Mattermost backend to Weechat.

## Installation

```bash
$ make install # WEECHAT_HOME=$HOME/.another-weechat
```

## Usage

```
/script load wee_matter.py
/matter server add a_banal_server a.banal.server
```

You should then edit other related configs as autoconnect servers, procotol (http/https), username, password.

```
/set plugins.var.python.wee-matter.* 
```

Then you can connect/disconnect to servers

```
/matter connect a_banal_server
/matter disconnect a_banal_server
```
