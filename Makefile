.PHONY: install

WEECHAT_HOME ?= $(HOME)/.weechat

libs := $(patsubst wee_matter/%.py, $(WEECHAT_HOME)/python/wee_matter/%.py, \
	$(wildcard wee_matter/*.py))

install: $(WEECHAT_HOME)/python/wee_matter/ $(libs) $(WEECHAT_HOME)/python/wee_matter.py

uninstall:
	rm $(WEECHAT_HOME)/python/wee_matter/*
	rm $(WEECHAT_HOME)/python/wee_matter.py
	rmdir $(WEECHAT_HOME)/python/wee_matter

$(WEECHAT_HOME)/python/wee_matter/:
	install -d $(WEECHAT_HOME)/python/wee_matter

$(WEECHAT_HOME)/python/wee_matter.py: main.py
	install -m644 main.py $(WEECHAT_HOME)/python/wee_matter.py

$(WEECHAT_HOME)/python/wee_matter/%.py: wee_matter/%.py
	install -m644 $< $@
