.PHONY: build test devices guard fmt stand e2e fullstand image qemu check docker-check

BUILD_DIR := build

build:
	cmake -S . -B $(BUILD_DIR)
	cmake --build $(BUILD_DIR) -j

test: build
	ctest --test-dir $(BUILD_DIR) --output-on-failure -LE devices
	python3 -m unittest discover -s emulator/tests -p 'test_cli.py'

# Runs only the scenarios that need vcan/i2c-stub/gpio-sim kernel modules
# (ctest label "devices"). Requires root; see emulator/README.md.
devices: build
	ctest --test-dir $(BUILD_DIR) --output-on-failure -L devices

guard:
	python3 ci/guard.py

fmt:
	find emulator rpi-app -name '*.cpp' -o -name '*.hpp' | xargs clang-format -i

# MQTT stand smoke test (TLS + ACL); see emulator/stand/smoke.sh.
stand:
	bash emulator/stand/smoke.sh

# Integration scenarios (tests/e2e/*.json): edge on this machine against a throwaway TLS broker.
# SCENARIO=<file> runs one. Needs mosquitto + mosquitto-clients (Linux; use `make docker-check` on
# a Mac). Results: build/stand/junit.xml and build/stand/<scenario>/. See docs/TESTING.md.
e2e: build
	EDGE_BIN=$(BUILD_DIR)/rpi-app/edge python3 ci/stand.py run $(or $(SCENARIO),$(wildcard tests/e2e/*.json))

# The whole stand from CI artifacts (image in QEMU, broker, emulator CLI, and the app if an Android
# emulator is running); builds nothing. RUN=<stand.yml run id> picks a bundle. See docs/CI.md.
fullstand:
	bash ci/fullstand.sh

# Yocto image build; heavy, not part of the fast local loop. See docs/CI.md.
image:
	bash yocto/build.sh

# Boots the image from `make image`; Linux only, see yocto/run-qemu.sh.
qemu:
	bash yocto/run-qemu.sh

# What CI runs on every PR. Run this before pushing.
check: build test guard

# `make check` and `make e2e` inside ubuntu:24.04, for a Mac (periph needs Linux). Own build dir so the
# container's CMake cache never mixes with a host one; it stays under build/ because
# ci/guard.py skips only paths with a part named exactly "build". Does not cover `devices`
# (kernel modules).
docker-check:
	docker build -q -f ci/dev.Dockerfile -t mes-dev .
	docker run --rm -e CI=1 -v "$(CURDIR)":/repo mes-dev make check e2e BUILD_DIR=build/docker
