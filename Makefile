.PHONY: install requirements
DESTDIR ?= /usr/local
INSTALLED_DESTDIR ?= ${DESTDIR}

git-staredown.system.py: git-staredown.py
	sed -e 's#/usr/bin/env #${INSTALLED_DESTDIR}/bin/#' $< > $@

install: git-staredown.system.py
	mkdir -p ${DESTDIR}/bin
	install -m0755 git-staredown.system.py ${DESTDIR}/bin/git-staredown

requirements:
	python3 -m pip install --upgrade -r requirements.txt
