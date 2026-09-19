################################################################################
#
# btkeyboard-receiver
#
################################################################################

BTKEYBOARD_RECEIVER_VERSION = 1.0
BTKEYBOARD_RECEIVER_SITE = $(BR2_EXTERNAL_BTKEYBOARD_PATH)/../receiver
BTKEYBOARD_RECEIVER_SITE_METHOD = local
BTKEYBOARD_RECEIVER_LICENSE = MIT
BTKEYBOARD_RECEIVER_DEPENDENCIES = python3 python-evdev

define BTKEYBOARD_RECEIVER_INSTALL_TARGET_CMDS
	$(INSTALL) -d -m 0755 $(TARGET_DIR)/opt/btkeyboard
	$(INSTALL) -m 0644 $(@D)/keymap.py $(TARGET_DIR)/opt/btkeyboard/keymap.py
	$(INSTALL) -m 0755 $(@D)/linux_receiver.py $(TARGET_DIR)/opt/btkeyboard/linux_receiver.py
	$(INSTALL) -D -m 0755 $(BTKEYBOARD_RECEIVER_PKGDIR)/S99btkeyboard \
		$(TARGET_DIR)/etc/init.d/S99btkeyboard
endef

$(eval $(generic-package))
