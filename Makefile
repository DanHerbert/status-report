ifeq ($(OS),Windows_NT)
    ARCH := $(PROCESSOR_ARCHITECTURE)
else
    ARCH := $(shell uname -m)
endif
ifeq ($(ARCH),x86_64)
    ARCH := amd64
endif
ifeq ($(ARCH),aarch64)
    ARCH := arm64
endif
PLATFORM := linux
YQ_VERSION := v4.52.2

YAML_CONFIG := ./src/config.yaml

JSON_SERVICE_NAME := status-report-json
JSON_SERVICE_FILE := $(JSON_SERVICE_NAME).service
JSON_TIMER_FILE   := $(JSON_SERVICE_NAME).timer
JSON_CONF_FILE    := $(JSON_SERVICE_NAME).service.conf

HTML_SERVICE_NAME := status-report-html
HTML_SERVICE_FILE := $(HTML_SERVICE_NAME).service
HTML_TIMER_FILE   := $(HTML_SERVICE_NAME).timer
HTML_CONF_FILE    := $(HTML_SERVICE_NAME).service.conf

VENV_PATH := ./venv
PYBIN_PATH := ./venv/bin

# Destination Paths
# Use /etc/systemd/system for system-wide, or $(HOME)/.config/systemd/user for user
SYSTEMD_DIR := /etc/systemd/system

# Destination for the config file.
# If this is an EnvironmentFile, use /etc/default.
# If this is a Drop-in, use $(SYSTEMD_DIR)/$(JSON_SERVICE_NAME).service.d
JSON_CONF_DEST_DIR := /etc/systemd/system/$(JSON_SERVICE_FILE).d

HTML_CONF_DEST_DIR := /etc/systemd/system/$(HTML_SERVICE_FILE).d

.PHONY: install-report-json install-report-html uninstall-report-json uninstall-report-html enable-report-json enable-report-html web watch-web

configure:
	python3 -m venv "$(VENV_PATH)"
	VIRTUAL_ENV="$(VENV_PATH)"; PATH="$(PYBIN_PATH):$$PATH"; pip install .
	pnpm install

install-report-json:
	@echo "Checking for configuration file..."
	@if [ ! -f "./systemd/$(JSON_CONF_FILE)" ]; then \
		echo "Error: Configuration file './systemd/$(JSON_CONF_FILE)' does not exist."; \
		echo "Please create it before installing."; \
		exit 1; \
	fi

	@echo "Installing systemd units..."

	# Create symlink for the Service file
	# We use realpath to ensure the link works regardless of where make is called
	sudo ln -sf "$(realpath ./systemd/$(JSON_SERVICE_FILE))" "$(SYSTEMD_DIR)/$(JSON_SERVICE_FILE)"

	# Create symlink for the Timer file
	sudo ln -sf "$(realpath ./systemd/$(JSON_TIMER_FILE))" "$(SYSTEMD_DIR)/$(JSON_TIMER_FILE)"

	# Create symlink for the Config file
	# We assume the destination directory exists; if not, you may need 'mkdir -p'
	sudo mkdir -p "$(JSON_CONF_DEST_DIR)"
	sudo ln -sf "$(realpath ./systemd/$(JSON_CONF_FILE))" "$(JSON_CONF_DEST_DIR)/$(JSON_CONF_FILE)"

	@echo "Reloading systemd daemon..."
	sudo systemctl daemon-reload

	@echo "Installation successful."

install-report-html:
	@echo "Checking for configuration file..."
	@if [ ! -f "./systemd/$(HTML_CONF_FILE)" ]; then \
		echo "Error: Configuration file './systemd/$(HTML_CONF_FILE)' does not exist."; \
		echo "Please create it before installing."; \
		exit 1; \
	fi

	@echo "Installing systemd units..."

	# Create symlink for the Service file
	# We use realpath to ensure the link works regardless of where make is called
	sudo ln -sf "$(realpath ./systemd/$(HTML_SERVICE_FILE))" "$(SYSTEMD_DIR)/$(HTML_SERVICE_FILE)"

	# Create symlink for the Timer file
	sudo ln -sf "$(realpath ./systemd/$(HTML_TIMER_FILE))" "$(SYSTEMD_DIR)/$(HTML_TIMER_FILE)"

	# Create symlink for the Config file
	# We assume the destination directory exists; if not, you may need 'mkdir -p'
	sudo mkdir -p "$(HTML_CONF_DEST_DIR)"
	sudo ln -sf "$(realpath ./systemd/$(HTML_CONF_FILE))" "$(HTML_CONF_DEST_DIR)/$(HTML_CONF_FILE)"

	@echo "Reloading systemd daemon..."
	sudo systemctl daemon-reload

	@echo "Installation successful."

uninstall-report-json:
	@echo "Removing symlinks..."
	sudo rm -f "$(SYSTEMD_DIR)/$(JSON_SERVICE_FILE)"
	sudo rm -f "$(SYSTEMD_DIR)/$(JSON_TIMER_FILE)"
	sudo rm -f "$(JSON_CONF_DEST_DIR)/$(JSON_CONF_FILE)"
	sudo rmdir "$(JSON_CONF_DEST_DIR)"
	sudo systemctl daemon-reload
	@echo "Uninstallation successful."

uninstall-report-html:
	@echo "Removing symlinks..."
	sudo rm -f "$(SYSTEMD_DIR)/$(HTML_SERVICE_FILE)"
	sudo rm -f "$(SYSTEMD_DIR)/$(HTML_TIMER_FILE)"
	sudo rm -f "$(HTML_CONF_DEST_DIR)/$(HTML_CONF_FILE)"
	sudo rmdir "$(HTML_CONF_DEST_DIR)"
	sudo systemctl daemon-reload
	@echo "Uninstallation successful."

enable-report-json:
	sudo systemctl enable --now $(JSON_TIMER_FILE)

enable-report-html:
	sudo systemctl enable --now $(HTML_TIMER_FILE)

web:
	if [ ! -f "./bin/yq" ]; then \
		mkdir -p ./bin/; \
		wget "https://github.com/mikefarah/yq/releases/download/$(YQ_VERSION)/yq_$(PLATFORM)_$(ARCH)" -O ./bin/yq && chmod +x ./bin/yq; \
	fi
	pnpm install
	WEB_OUTDIR=$(shell ./bin/yq '.web_output_dir' $(YAML_CONFIG)); \
	pnpm exec stylus --out $$WEB_OUTDIR ./src/main.styl; \
	pnpm exec tsc --outDir $$WEB_OUTDIR

watch-web:
	if [ ! -f "./bin/yq" ]; then \
		mkdir -p ./bin/; \
		wget "https://github.com/mikefarah/yq/releases/download/$(YQ_VERSION)/yq_$(PLATFORM)_$(ARCH)" -O ./bin/yq && chmod +x ./bin/yq; \
	fi
	pnpm install
	WEB_OUTDIR=$(shell ./bin/yq '.web_output_dir' $(YAML_CONFIG)); \
	pnpm exec stylus --watch --out "$$WEB_OUTDIR" ./src/main.styl & \
	pnpm exec tsc --watch --outDir "$$WEB_OUTDIR"
