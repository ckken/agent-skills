.PHONY: setup-hooks build-image-opt

setup-hooks:
	git config core.hooksPath .githooks

build-image-opt:
	$(MAKE) -C tools/agent-image-opt build
