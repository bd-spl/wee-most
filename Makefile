.PHONY: install run-dev

WEECHAT_DATA_DIR = $(HOME)/.local/share/weechat

SCRIPT_DIR = $(WEECHAT_DATA_DIR)/python

libs := $(patsubst wee_matter/%.py, $(SCRIPT_DIR)/wee_matter/%.py, \
	$(wildcard wee_matter/*.py))

install: $(SCRIPT_DIR)/wee_matter/ $(libs) $(SCRIPT_DIR)/wee_matter.py

uninstall:
	rm $(SCRIPT_DIR)/wee_matter/*
	rm $(SCRIPT_DIR)/wee_matter.py
	rmdir $(SCRIPT_DIR)/wee_matter

.weechat:
	mkdir -p $(SCRIPT_DIR)/autoload
	ln -s ../wee_matter.py $(SCRIPT_DIR)/autoload/wee_matter.py

run-dev: .weechat
	make install WEECHAT_DATA_DIR=.weechat
	weechat -d .weechat

$(SCRIPT_DIR)/wee_matter/:
	install -d $(SCRIPT_DIR)/wee_matter

$(SCRIPT_DIR)/wee_matter.py: main.py
	install -m644 main.py $(SCRIPT_DIR)/wee_matter.py

$(SCRIPT_DIR)/wee_matter/%.py: wee_matter/%.py
	install -m644 $< $@
