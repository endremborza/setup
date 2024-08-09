LOCAL_DOTFILES := local-dotfiles/host-$(shell hostname)
PUB_KEY_LOC := /tmp/gpg-pub.asc
PRI_KEY_LOC := /tmp/gpg-sc.asc
GPG_USER := endremborza

export GPG_KEY_ID

setup: init-local-dotfiles decrypt-secrets
	restow

build-secrets:
	# GPGME_PK_ECDH
	gpg --list-keys | grep -Fq $(GPG_USER) && gpgtar -r $(GPG_USER) -o secrets.gpg -e secrets
	@echo "secrets encrypted"

decrypt-secrets:
	export GPG_TTY=$(shell tty)
	gpg --list-keys | grep -Fq $(GPG_USER) && gpgtar -r $(GPG_USER) -C . -d secrets.gpg && echo "secrets decrypted" || (echo "failed decrypting" && mkdir -p secrets && touch secrets/.secret-vars)

init-local-dotfiles:
	if test -d $(LOCAL_DOTFILES); then echo "already copied"; else cp -r local-dotfiles/sample $(LOCAL_DOTFILES); fi;
	@echo "local dotfile directory built"

sync-local-dotfiles:
	echo 0 || echo 0 && echo 10
	@echo syncing

export-gpg-keys:
	export GPG_TTY=$(shell tty)
	gpg --export -a $(GPG_KEY_ID) > $(PUB_KEY_LOC)
	gpg --export-secret-keys -a $(GPG_KEY_ID) > $(PRI_KEY_LOC)

import-gpg-keys:
	gpg --import $(PUB_KEY_LOC)
	gpg --import $(PRI_KEY_LOC)
