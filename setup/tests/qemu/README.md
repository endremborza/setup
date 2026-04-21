# QEMU Test Runner (outline)

Levels 3–4 require a real graphical session and cannot be tested inside Docker. The intended workflow uses a QEMU VM booted from an Ubuntu 24.04 cloud image.

## Intended workflow

1. **Provision**: download the Ubuntu 24.04 cloud image and boot it with QEMU. Use cloud-init to seed a user account and an authorized SSH key so the host can connect without a password.

2. **Run setup**: from the host, invoke setup over SSH:
   ```
   ssh qemu-target 'setup run --level 4'
   ```
   Capture the serial log for post-mortem inspection.

3. **Verify**: after the run completes, execute verify and collect results:
   ```
   ssh qemu-target 'setup verify --level 4'
   ```

4. **Cleanup**: shut down the VM and delete the ephemeral disk image.

## Makefile sketch

```makefile
CLOUD_IMG = ubuntu-24.04-server-cloudimg-amd64.img
VM_DISK   = /tmp/setup-test-vm.qcow2

vm-create:
	qemu-img create -f qcow2 -b $(CLOUD_IMG) -F qcow2 $(VM_DISK) 20G
	# boot with cloud-init seed ISO (user-data injects SSH key)

vm-run-level4:
	ssh qemu-target 'setup run --level 4' | tee /tmp/level4.log

vm-verify:
	ssh qemu-target 'setup verify --level 4'

vm-destroy:
	pkill -f $(VM_DISK) || true
	rm -f $(VM_DISK)
```

## Not implemented

Implementation is deferred until levels 3–4 steps are stable. The Docker tests (levels 0–1) are the primary gate for CI.
