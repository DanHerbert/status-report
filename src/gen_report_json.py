#!/usr/bin/env python3
"""Script to generate a system status report based on a config file"""

import json
import logging
import os
import shlex
import subprocess
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

import psutil
from dateutil import parser

from config import get_config, DiskCheck, StatusCheck


@dataclass
class ServiceUnit:
    """Information about a Systemd service unit"""
    service_type: str
    result: str
    triggered_by: str
    load_state: str
    active_state: str
    inactive_enter: datetime | None


@dataclass
class TimerUnit:
    """Information about a Systemd timer unit."""
    unit: str
    last_trigger: datetime
    load_state: str
    active_state: str
    active_enter: datetime


# pylint: disable=too-many-instance-attributes
@dataclass
class PathUnit:
    """Information about a Systemd path unit."""
    load_state: str
    active_state: str
    active_enter: datetime
    unit: str
    binds_to: str
    bind_load_state: str = None
    bind_active_state: str = None
    bind_inactive_enter: datetime = None
    unit_load_state: str = None
    unit_result: str = None
    unit_inactive_enter: datetime = None


logger = logging.getLogger("gen_report_json")

SCRIPT_PATH = os.path.dirname(os.path.abspath(__file__))
CONFIG_PATH = os.path.join(SCRIPT_PATH, "config.yaml")

SCTL = "systemctl"


def get_disk_usage(disk: DiskCheck):
    """Get disk usage (as a percent) for the given disk."""
    cmd_args = shlex.split(f"df --output=pcent {disk.path}")
    result = subprocess.run(
        cmd_args,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        timeout=5,
        check=False,
    )
    if result.returncode != 0:
        logger.error("Command failed with output:\n%s", result.stdout)
    results = result.stdout.strip().split("\n")
    pcent = results[1].strip()
    return pcent


def build_sctl_command(check: StatusCheck, unit: str | None = None) -> list[str]:
    """Build `systemctl show` command args to be passed into subprocess.run()"""
    cmd_args = [SCTL]
    if check.is_user:
        cmd_args.append("--user")
    cmd_args.append(f"--machine={check.machine}")
    cmd_args.append("show")
    if unit is None:
        cmd_args.append("--property=SystemState")
    else:
        [_, unit_type] = unit.split(".")
        match unit_type:
            case "service":
                cmd_args.append(
                    "--property=Type,Result,TriggeredBy,LoadState,"
                    "ActiveState,InactiveEnterTimestamp"
                )
            case "timer":
                cmd_args.append(
                    "--property=Unit,LastTriggerUSec,LoadState,ActiveState,"
                    "ActiveEnterTimestamp"
                )
            case "path":
                cmd_args.append(
                    "--property=Unit,BindsTo,LoadState,ActiveState,ActiveEnterTimestamp"
                )
        cmd_args.append(unit)
    return cmd_args


def run_system_check(check: StatusCheck, output):
    """Get the system state for a given machine."""
    result = run_sctl_command(check)
    if result is None:
        output["status_checks"].append({"label": check.label, "state": "Unknown"})
    else:
        sys_state = result["SystemState"]
        output["status_checks"].append(
            {
                "label": check.label,
                "state": "ok" if sys_state == "running" else sys_state,
            }
        )


def run_sctl_command(check: StatusCheck, unit: str | None = None):
    """Run a `systemctl show` command and parse the results as a dictionary."""
    cmd_args = build_sctl_command(check, unit)
    result = subprocess.run(
        cmd_args,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        timeout=5,
        check=False,
    )
    if result.returncode != 0:
        logger.error(
            "Command [%s] failed for [%s] with output:\n%s",
            ' '.join(cmd_args),
            unit,
            result.stdout
        )
        return None
    results = result.stdout.split("\n")
    result_dict = {}
    for result in results:
        if len(result) > 0:
            [key, val] = result.split("=", maxsplit=1)
            result_dict[key.strip()] = val.strip()
    return result_dict


def to_timestamp_if_exists(timestamp: str) -> datetime | None:
    """Parse a systemd timestamp only if a value exists."""
    return (
        parser.parse(timestamp)
        if timestamp is not None and len(timestamp.strip()) > 0
        else None
    )


def run_unit_query(
    check: StatusCheck, unit: str
) -> ServiceUnit | TimerUnit | PathUnit | None:
    """Query a systemd unit for details about it."""
    result = run_sctl_command(check, unit)
    [_, unit_type] = unit.split(".")
    match unit_type:
        case "service":
            return ServiceUnit(
                service_type=result["Type"],
                result=result["Result"],
                triggered_by=result["TriggeredBy"],
                load_state=result["LoadState"],
                active_state=result["ActiveState"],
                inactive_enter=to_timestamp_if_exists(result["InactiveEnterTimestamp"]),
            )
        case "timer":
            return TimerUnit(
                unit=result["Unit"],
                last_trigger=to_timestamp_if_exists(result["LastTriggerUSec"]),
                load_state=result["LoadState"],
                active_state=result["ActiveState"],
                active_enter=to_timestamp_if_exists(result["ActiveEnterTimestamp"]),
            )
        case "path":
            path_unit = PathUnit(
                unit=result["Unit"],
                binds_to=result["BindsTo"],
                load_state=result["LoadState"],
                active_state=result["ActiveState"],
                active_enter=to_timestamp_if_exists(result["ActiveEnterTimestamp"]),
            )
            result = run_sctl_command(check, path_unit.binds_to)
            path_unit.bind_load_state = result["LoadState"]
            path_unit.bind_active_state = result["ActiveState"]
            path_unit.bind_inactive_enter = to_timestamp_if_exists(
                result["InactiveEnterTimestamp"]
            )
            result = run_sctl_command(check, path_unit.unit)
            path_unit.unit_result = result["Result"]
            path_unit.unit_load_state = result["LoadState"]
            path_unit.unit_inactive_enter = to_timestamp_if_exists(
                result["InactiveEnterTimestamp"]
            )
            return path_unit


def do_timer_unit_check_logic(check: StatusCheck) -> dict[str,str|None]:
    """Perform logic checks for a Systemd timer unit."""
    boot_time = datetime.fromtimestamp(psutil.boot_time(), timezone.utc)
    boot_timedelta = datetime.now(timezone.utc) - boot_time
    unit_name = check.unit
    timer = run_unit_query(check, unit_name)
    service = run_unit_query(check, timer.unit)
    if timer.last_trigger is None:
        last_trigger_delta = timedelta(seconds=99999999)
    else:
        last_trigger_delta = datetime.now(timezone.utc) - timer.last_trigger
    expected_trigger_delta = timedelta(seconds=check.expected_interval_secs)
    timer_state = (
        "ok"
        if timer.active_state == "active"
        and (
            last_trigger_delta < expected_trigger_delta
            or (
                timer.active_enter is not None
                and boot_timedelta < expected_trigger_delta
                # After a reboot, last_trigger is empty, so if there has been a
                # recent reboot, assume timer is ok if it is active.
                and (timer.active_enter - boot_time).total_seconds() < 120
            )
        )
        else timer.active_state
    )
    service_state = "ok" if service.result == "success" else service.result
    service_last_trigger = service.inactive_enter
    if service.inactive_enter is None:
        service_last_trigger = timer.last_trigger
    overall_state = (
        "ok"
        if timer_state == "ok" and service_state == "ok"
        else service.result
    )
    return {
        "label": check.label,
        "state": overall_state,
        "timer_last_trigger": (
            timer.last_trigger.isoformat()
            if timer.last_trigger is not None
            else None
        ),
        "timer_active_state": timer.active_state,
        "service_result": service_state,
        "service_last_trigger": (
            service_last_trigger.isoformat()
            if service_last_trigger is not None
            else None
        ),
    }


def do_service_unit_check_logic(check: StatusCheck) -> dict[str,str|None]:
    """Perform logic checks for a Systemd service unit."""
    service = run_unit_query(check, check.unit)
    return {
        "label": check.label,
        "state": (
            "ok"
            if service.load_state == "loaded"
            and service.active_state == "active"
            else service.active_state
        ),
        "load_state": service.load_state,
        "active_state": service.active_state,
    }


def do_path_unit_check_logic(check: StatusCheck) -> dict[str,str|None]:
    """Perform logic checks for a Systemd path unit."""
    path_unit = run_unit_query(check, check.unit)
    overall_state = (
        "ok"
        if path_unit.load_state == "loaded"
        and path_unit.active_state == "active"
        and path_unit.bind_load_state == "loaded"
        and path_unit.bind_active_state == "active"
        and path_unit.unit_load_state == "loaded"
        and path_unit.unit_result == "success"
        else path_unit.active_state
    )
    return {
        "label": check.label,
        "state": overall_state,
        "load_state": path_unit.load_state,
        "active_state": path_unit.active_state,
        "bind_state": (
            "ok"
            if path_unit.bind_load_state == "loaded"
            and path_unit.bind_active_state == "active"
            else path_unit.bind_active_state
        ),
        "bind_load_state": path_unit.bind_load_state,
        "bind_active_state": path_unit.bind_active_state,
        "bind_inactive_enter": (
            path_unit.bind_inactive_enter.isoformat()
            if path_unit.bind_inactive_enter is not None
            else None
        ),
        "unit_state": (
            "ok"
            if path_unit.unit_load_state == "loaded"
            and path_unit.unit_result == "success"
            else path_unit.unit_result
        ),
        "unit_load_state": path_unit.unit_load_state,
        "unit_result": path_unit.unit_result,
        "unit_inactive_enter": (
            path_unit.unit_inactive_enter.isoformat()
            if path_unit.unit_inactive_enter is not None
            else None
        ),
    }


def do_unit_check_logic(check: StatusCheck, output: list[dict[str,str|None]]):
    """Query a systemd unit and append the results to output"""
    [_, unit_type] = check.unit.split(".")
    match unit_type:
        case "timer":
            output["status_checks"].append(do_timer_unit_check_logic(check))
        case "service":
            output["status_checks"].append(do_service_unit_check_logic(check))
        case "path":
            output["status_checks"].append(do_path_unit_check_logic(check))


def get_disk_status(disk: DiskCheck) -> dict[str, str]:
    """Get status for a given disk check."""
    disk_info = {
        "label": disk.label,
        "path": disk.path,
        "usage": get_disk_usage(disk),
    }
    if disk.raid is not None:
        cmd_args = shlex.split(f"mdadm --detail {disk.raid}")
        result = subprocess.run(
            cmd_args,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            timeout=5,
            check=False,
        )
        if result.returncode != 0:
            logger.error("Command failed with output:\n%s", result.stdout)
        failed_devices = -1
        for line in result.stdout.split("\n"):
            if line.strip().startswith("Failed Devices"):
                failed_devices = int(line.split(":")[1].strip())
        disk_info["failed_devices"] = failed_devices
    return disk_info


def check_needrestart():
    """Check the `needrestart` command for anything needing a restart."""
    cmd_args = shlex.split("needrestart -b")
    result = subprocess.run(
        cmd_args,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        timeout=5,
        check=False,
    )
    services_needing_restarts = 0
    users_with_outdated_binaries = 0
    for line in result.stdout.split("\n"):
        current_kernel = '1'
        expected_kernel = '2'
        current_kernel_status = 1
        if line.startswith("NEEDRESTART-KCUR:"):
            [_, current_kernel] = line.split(": ")
        elif line.startswith("NEEDRESTART-KEXP:"):
            [_, expected_kernel] = line.split(": ")
        elif line.startswith("NEEDRESTART-KSTA"):
            [_, current_kernel_status] = line.split(": ")
            current_kernel_status = int(current_kernel_status)
        elif line.startswith("NEEDRESTART-SVC"):
            services_needing_restarts += 1
        elif line.startswith("NEEDRESTART-SESS"):
            users_with_outdated_binaries += 1
    return {
        "outdated_kernel": (
            current_kernel_status != 1 or current_kernel != expected_kernel
        ),
        "services_needing_restarts": services_needing_restarts,
        "users_with_outdated_binaries": users_with_outdated_binaries,
    }


def main():
    """Main app execution code."""
    conf = get_config()
    logging.basicConfig(
        format=conf.log_format,
        datefmt=conf.log_datefmt,
        level=conf.log_level,
    )

    output = {
        "status_checks": [],
        "disks": [],
        "generated_datetime": datetime.now(timezone.utc).isoformat(),
        "boot_datetime": datetime.fromtimestamp(
            psutil.boot_time(), timezone.utc
        ).isoformat(),
        "system_name": conf.system_name,
    }

    for check in conf.status_checks:
        if check.unit is None:
            run_system_check(check, output)
        else:
            do_unit_check_logic(check, output)
    for disk in conf.disks:
        output["disks"].append(get_disk_status(disk))
    output["needrestart"] = check_needrestart()

    with open(conf.json_report_output_file, mode="wt", encoding="utf-8") as output_file:
        json.dump(output, output_file, indent=2)

    if conf.scp_command is not None:
        cmd_args = shlex.split(conf.scp_command)
        result = subprocess.run(
            cmd_args,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            timeout=5,
            check=False,
        )
        if result.returncode != 0:
            logger.error("Command failed with output:\n%s", result.stdout)
        else:
            logger.info("Uploaded status report based on configured command")


if __name__ == "__main__":
    main()
