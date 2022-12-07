.PHONY: install uninstall autoload emojis

WEECHAT_DATA_DIR = $(HOME)/.local/share/weechat

SCRIPT_DIR = $(DESTDIR)$(WEECHAT_DATA_DIR)/python
DATA_DIR = $(DESTDIR)$(WEECHAT_DATA_DIR)

install: $(SCRIPT_DIR)/wee_most.py $(DATA_DIR)/wee_most_emojis

uninstall:
	rm $(SCRIPT_DIR)/wee_most.py $(DATA_DIR)/wee_most_emojis

autoload:
	mkdir -p $(SCRIPT_DIR)/autoload
	ln -sf ../wee_most.py $(SCRIPT_DIR)/autoload/wee_most.py

emojis:
	curl -sL "https://raw.githubusercontent.com/mattermost/mattermost-webapp/master/utils/emoji.json" \
		| jq -r '.[] | .short_names[]' \
		| sort \
		> wee_most_emojis

$(SCRIPT_DIR)/wee_most.py: wee_most.py
	install -D -m644 wee_most.py $(SCRIPT_DIR)/wee_most.py

$(DATA_DIR)/wee_most_emojis: wee_most_emojis
	install -D -m644 wee_most_emojis $(DATA_DIR)/wee_most_emojis
