stage build clean clobber deploy:
	$(MAKE) -C upload-checksum-daemon $@
	$(MAKE) -C health-check-daemon $@
	$(MAKE) -C area-deletion-daemon $@
	$(MAKE) -C validation-scheduler-daemon $@
