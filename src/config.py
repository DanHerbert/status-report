"""Configuration loader"""

import logging
import os
from datetime import timedelta
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

import yaml

SCRIPT_PATH = os.path.dirname(os.path.abspath(__file__))
CONFIG_PATH = os.path.join(SCRIPT_PATH, "../config/", "config.yaml")

@dataclass
class StatusCheck:
    label: str
    machine: str
    is_user: bool = False
    unit: Optional[str] = None
    expected_interval_secs: int = None


@dataclass
class DiskCheck:
    label: str
    path: Path
    raid: Optional[Path] = None


@dataclass
class Config:
    log_level: str
    log_format: str
    log_datefmt: str
    json_reports_search_path: Path
    json_report_output_file: Path
    acceptable_disk_usage: int
    system_name: str
    status_checks: list[StatusCheck]
    disks: list[DiskCheck]
    html_report_output_file: Path = None
    web_output_dir: Path = None
    scp_command: str = None


def get_config() -> Config:
    """Gets the config object from disk."""
    with open(CONFIG_PATH, mode="rt", encoding="utf-8") as file_handle:
        conf_dict = yaml.safe_load(file_handle)
        conf = Config(**conf_dict)
        conf.log_level = logging.getLevelName(conf.log_level)
        conf.status_checks = []
        conf.disks = []
        for check in conf_dict["status_checks"]:
            conf.status_checks.append(StatusCheck(**check))
        for disk in conf_dict["disks"]:
            conf.disks.append(DiskCheck(**disk))
        return conf
