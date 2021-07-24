.PHONY: install uninstall autoload

WEECHAT_DATA_DIR = $(HOME)/.local/share/weechat

SCRIPT_DIR = $(WEECHAT_DATA_DIR)/python

libs := $(patsubst wee_most/%.py, $(SCRIPT_DIR)/wee_most/%.py, \
	$(wildcard wee_most/*.py))

install: $(SCRIPT_DIR)/wee_most/ $(libs) $(SCRIPT_DIR)/wee_most.py

uninstall:
	rm $(SCRIPT_DIR)/wee_most/*
	rm $(SCRIPT_DIR)/wee_most.py
	rmdir $(SCRIPT_DIR)/wee_most

autoload:
	mkdir -p $(SCRIPT_DIR)/autoload
	ln -sf ../wee_most.py $(SCRIPT_DIR)/autoload/wee_most.py

$(SCRIPT_DIR)/wee_most/:
	install -d $(SCRIPT_DIR)/wee_most

$(SCRIPT_DIR)/wee_most.py: main.py
	install -m644 main.py $(SCRIPT_DIR)/wee_most.py

$(SCRIPT_DIR)/wee_most/%.py: wee_most/%.py
	install -m644 $< $@
