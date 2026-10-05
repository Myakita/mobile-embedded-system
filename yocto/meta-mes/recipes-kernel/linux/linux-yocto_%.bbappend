# vcan for the edge service. qemux86-64's kernel config has no CAN at all, and the stock
# features/can/can.scc pulls in a dozen hardware drivers as modules; this is just the three
# options edge needs, built in so there is no module to load.
FILESEXTRAPATHS:prepend := "${THISDIR}/files:"
SRC_URI += "file://vcan.cfg"
