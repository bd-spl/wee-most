# wee-most

WeeChat plugin for Mattermost

Tested only on latest Mattermost and WeeChat stable versions on Linux

## History

This project was originally a fork of [wee-matter](https://sr.ht/~stacyharper/wee-matter/).
While fixing bugs and adding new features there, I had to refactor large parts of the code.
Those changes were not welcome in that project so I continued working on my own fork.
By now the projects have diverged considerably.

My wish would be to have a plugin for Mattermost as good as [wee-slack](https://github.com/wee-slack/wee-slack) is for Slack.
I was a very happy user of it in a previous job.
As such I have been drawing a lot of inspiration from its code and features.

## Installation

Python dependencies:

* [websocket_client](https://github.com/websocket-client/websocket-client)

```bash
$ make install
```

## Usage


## Connection

```
/script load wee_most.py
/mattermost server add a_banal_server
```

You should then edit its configuration such as URL, username, password, 2FA command,...
To store the password safely, you can make use of WeeChat [secured data storage](https://weechat.org/files/doc/stable/weechat_user.en.html#secured_data)

```
/set plugins.var.python.wee-most.a_banal_server.* 
```

Then you can connect/disconnect to servers

```
/mattermost connect a_banal_server
/mattermost disconnect a_banal_server
```
