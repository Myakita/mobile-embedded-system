# vcan for the edge service. qemux86-64's kernel config has no CAN at all, and the stock
# features/can/can.scc pulls in a dozen hardware drivers as modules; this is just the three
# options edge needs, built in so there is no module to load.
# fw_cfg: how the stand hands edge its broker config and CA certificate to the guest
# (QEMU -fw_cfg, read from /sys/firmware/qemu_fw_cfg); qemux86-64 does not enable it.
FILESEXTRAPATHS:prepend := "${THISDIR}/files:"
SRC_URI += "file://vcan.cfg file://fw_cfg.cfg"
