.PHONY: install requirements
DESTDIR ?= /usr/local

install:
	mkdir -p ${DESTDIR}/bin
	install -m0755 git-staredown.py ${DESTDIR}/bin/git-staredown

requirements:
	python3 -m pip install --upgrade -r requirements.txt
