# wee-most

WeeChat plugin for Mattermost

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
/script load wee_most.py
/mattermost server add a_banal_server
```

You should then edit its configuration such as URL, username, password,...
To store the password safely, you can make use of WeeChat [secured data storage](https://weechat.org/files/doc/stable/weechat_user.en.html#secured_data)

```
/set plugins.var.python.wee-most.a_banal_server.* 
```

Then you can connect/disconnect to servers

```
/mattermost connect a_banal_server
/mattermost disconnect a_banal_server
```

## Mattermost commands

You can send Mattermost commands using this prefix.

```
/mattermost command me Aya ! :3
```

## Reply, React, Remove

Mouse click or select a line print the short post id in the input field.

Some command uses this id to interact with posts.

```
/mattermost reply abc Yeah you right !
/mattermost react abc rofl
/mattermost react abc 100
/mattermost delete abc
```

You can add aliases for some of these commands (if there's no conflict with other plugins)
```
alias add reply /mattermost reply
```

## Buffers display

For a nice organization of buffers in the buflist, use a sorting by name
```
/set buflist.look.sort name
```

## Deal with files

Mouse click or select a file line download it and open it.

## Send multiline messages

The multiline perl script is correctly handled by wee-most :

https://weechat.org/scripts/source/multiline.pl.html/

You would still have issues with multiline pasted text. Add this :

```
/set plugins.var.perl.multiline.weechat_paste_fix "off"
/key bind ctrl-J /input insert \n
```

## Acknowledgements

Wee-most is originally a fork of [wee-matter](https://sr.ht/~reedwade/wee-matter/)
and draws a lot of inspiration from [wee-slack](https://github.com/wee-slack/wee-slack)
