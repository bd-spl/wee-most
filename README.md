# Wee-Matter

Wee-Matter is a Mattermost backend to Weechat.

## Installation

Python dependencies from PyPi:

* [websocket_client](https://pypi.org/project/websocket_client/)

```bash
$ make install # WEECHAT_HOME=$HOME/.another-weechat
```

## Usage


## Connection

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

## Reply, React, Remove

Mouse click or select a line print the short post id in the input field.

Some command uses this id to interact with posts.

```
/reply abc Yeah you right !
/react abc rofl
/react abc 100
/delete abc
```

## Deal with files

Mouse click or select a file line download it and open it.
