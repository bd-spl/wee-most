.PHONY: install install-lib

WEECHAT_HOME ?= $(HOME)/.weechat

lib := $(patsubst wee_matter/%.py, $(WEECHAT_HOME)/python/wee_matter/%.py, \
	$(wildcard wee_matter/*.py))

install: install-dir install-lib
	install -m644 main.py $(WEECHAT_HOME)/python/wee_matter.py

uninstall:
	rm $(WEECHAT_HOME)/python/wee_matter/*
	rm $(WEECHAT_HOME)/python/wee_matter.py
	rmdir $(WEECHAT_HOME)/python/wee_matter

install-dir:
	install -d $(WEECHAT_HOME)/python/wee_matter

install-lib: $(lib)
$(WEECHAT_HOME)/python/wee_matter/%.py: wee_matter/%.py
	install -m644 $< $@
