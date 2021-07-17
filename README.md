# Wee-Matter

Wee-Matter is a Mattermost backend to Weechat.

## Installation

Python dependencies from PyPi:

* [websocket_client](https://pypi.org/project/websocket_client/)

Set the WEECHAT_DATA_DIR Makefile variable to match your configuration.
- default is `~/.local/share/weechat` in newer versions (starting with 3.2)
- default is `~/.weechat` in older versions

```bash
$ make install # WEECHAT_DATA_DIR=~/.weechat
```

## Usage


## Connection

```
/script load wee_matter.py
/matter server add a_banal_server
```

You should then edit its configuration such as URL, username, password,...
To store the password safely, you can make use of weechat [secured data storage](https://weechat.org/files/doc/stable/weechat_user.en.html#secured_data)

```
/set plugins.var.python.wee-matter.a_banal_server.* 
```

Then you can connect/disconnect to servers

```
/matter connect a_banal_server
/matter disconnect a_banal_server
```

## Mattermost commands

You can send Mattermost commands using this prefix.

```
/matter command me Aya ! :3
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

## Buffers display

For a nice organization of buffers in the buflist, use a sorting by name
```
/set buflist.look.sort name
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
