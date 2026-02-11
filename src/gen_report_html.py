#!/usr/bin/env python3
"""Script to generate system status report html based on a json file"""

import json
import logging
import os
from pathlib import Path

import yaml
from jinja2 import Environment, FileSystemLoader, select_autoescape

from config import get_config, DiskCheck, StatusCheck


logger = logging.getLogger("gen_report_html")

SCRIPT_PATH = os.path.dirname(os.path.abspath(__file__))
CONFIG_PATH = os.path.join(SCRIPT_PATH, "config.yaml")


def main():
    conf = get_config()
    logging.basicConfig(
        format=conf.log_format,
        datefmt=conf.log_datefmt,
        level=conf.log_level,
    )

    reports_folder = Path(conf.json_reports_search_path)
    system_reports = []
    all_systems_ok = True
    for file_path in reports_folder.glob("*.json"):
        with file_path.open(encoding="utf-8") as f:
            data = json.load(f)
            logger.info(f"parsed json: {data}")
            data["this_system_ok"] = True
            system_reports.append(data)
            for item in data["status_checks"]:
                if item["state"] != "ok":
                    data["this_system_ok"] = False
                    all_systems_ok = False
            for disk in data["disks"]:
                if int(disk["usage"].strip("%")) > conf.acceptable_disk_usage:
                    data["this_system_ok"] = False
                    all_systems_ok = False
                if "failed_devices" in disk and disk["failed_devices"] > 0:
                    data["this_system_ok"] = False
                    all_systems_ok = False
            if (
                data["needrestart"]["outdated_kernel"]
                or data["needrestart"]["services_needing_restarts"] > 0
                or data["needrestart"]["users_with_outdated_binaries"]
            ):
                data["this_system_ok"] = False
                all_systems_ok = False

    env = Environment(
        loader=FileSystemLoader(os.path.dirname(os.path.abspath(__file__))),
        autoescape=select_autoescape(["html", "xml"]),
    )

    tmpl = env.get_template("status-page.jinja")

    out_html = tmpl.render(all_systems_ok=all_systems_ok, system_reports=system_reports)
    with open(conf.html_report_output_file, "w", encoding="utf-8") as f:
        f.write(out_html)


if __name__ == "__main__":
    main()
