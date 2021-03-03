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

## Mattermost commands

You can send Mattermost commands using this prefix.

```
/matter me Aya ! :3
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

## Send multiline messages

The multiline perl script is correctly handled by Wee-Matter :

https://weechat.org/scripts/source/multiline.pl.html/

You would still have issues with multiline pasted text. Add this :

```
/set plugins.var.perl.multiline.weechat_paste_fix "off"
/key bind ctrl-J /input insert \n
```
