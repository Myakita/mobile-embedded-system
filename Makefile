.PHONY: build test devices guard fmt stand image check

BUILD_DIR := build

build:
	cmake -S emulator -B $(BUILD_DIR)
	cmake --build $(BUILD_DIR) -j

test: build
	ctest --test-dir $(BUILD_DIR) --output-on-failure

# Runs only the scenarios that need vcan/i2c-stub/gpio-sim kernel modules
# (ctest label "devices"). Requires root; see emulator/README.md.
devices: build
	ctest --test-dir $(BUILD_DIR) --output-on-failure -L devices

guard:
	python3 ci/guard.py

fmt:
	find emulator -name '*.cpp' -o -name '*.hpp' | xargs clang-format -i

# Test MQTT stand (mosquitto + emulator nodes); see emulator/stand/.
stand:
	docker compose -f emulator/stand/compose.yml up --abort-on-container-exit

# Yocto image build; heavy, not part of the fast local loop. See docs/CI.md.
image:
	bash yocto/build.sh

# What CI runs on every PR. Run this before pushing.
check: build test guard
