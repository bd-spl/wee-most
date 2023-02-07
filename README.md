# wee-most

WeeChat script for Mattermost

## Past and Future

This project was originally a fork of [wee-matter](https://sr.ht/~stacyharper/wee-matter/)
with the intended goal to make it as good as [wee-slack](https://github.com/wee-slack/wee-slack) is for Slack.

## Requirements

The script is currently only tested on what I'm using daily, meaning:
- against server running latest Mattermost stable version
- on latest WeeChat stable version on Linux

## Installation

Python dependencies:

* [websocket-client](https://github.com/websocket-client/websocket-client)

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
