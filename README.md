# wee-most

WeeChat script for Mattermost

## History

This project was originally a fork of [wee-matter](https://sr.ht/~stacyharper/wee-matter/).
While fixing bugs and adding new features there, I had to refactor large parts of the code.
Those changes were not welcome in that project so I continued working on my own fork.
By now the projects have diverged considerably.

My wish would be to have a script for Mattermost as good as [wee-slack](https://github.com/wee-slack/wee-slack) is for Slack.
I was a very happy user of it in a previous job.
As such I have been drawing a lot of inspiration from its code and features.

## Requirements

The script is currently only tested:
- against server running latest Mattermost stable version
- on latest WeeChat stable version on Linux

## Installation

Python dependencies:

* [websocket_client](https://github.com/websocket-client/websocket-client)

```bash
$ make install
```

## Server setup

Once the script is loaded, you can add a Mattermost server with the identifier of your choice.
```
/mattermost server add dunder_mifflin
```

You should then edit its configuration such as URL, username and password.
```
/set wee_most.server.dunder_mifflin.url "https://mattermost.dundermifflin.com"
/set wee_most.server.dunder_mifflin.username "m.scott"
/set wee_most.server.dunder_mifflin.password "twss"
```

To store the password safely, you can make use of WeeChat [secured data storage](https://weechat.org/files/doc/stable/weechat_user.en.html#secured_data)

You can then connect
```
/mattermost connect dunder_mifflin
```
