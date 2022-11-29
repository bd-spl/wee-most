.PHONY: install uninstall autoload

WEECHAT_DATA_DIR = $(HOME)/.local/share/weechat

SCRIPT_DIR = $(DESTDIR)$(WEECHAT_DATA_DIR)/python

install: $(SCRIPT_DIR)/wee_most.py

uninstall:
	rm $(SCRIPT_DIR)/wee_most.py

autoload:
	mkdir -p $(SCRIPT_DIR)/autoload
	ln -sf ../wee_most.py $(SCRIPT_DIR)/autoload/wee_most.py

$(SCRIPT_DIR)/wee_most.py: wee_most.py
	install -m644 wee_most.py $(SCRIPT_DIR)/wee_most.py
