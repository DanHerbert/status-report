#!/bin/bash -e

if [[ $EUID != 0 ]]; then
    echo 'Script must be run as root'
    exit 1
fi

primary_uid=$(grep -m 1 -E '^UID_MIN\s' /etc/login.defs | awk '{ print $2 }')
primary_user=$(id -nu "$primary_uid")
user_home=$(eval echo "~${primary_user}")
primary_user_state_home="$user_home/.local/state"
app_state_path="$primary_user_state_home/dotfiles"
status_path="$app_state_path/system_state"
mail_path="$app_state_path/mail_state"
raid_path="$app_state_path/raid_failure"

mapfile -t user_names < <(loginctl list-users | tail -n+2 | head -n-2 | grep 'yes' | awk '{ print $2 }')
declare -A previous_states
if [[ -e "$status_path" ]] && (( $(wc -l < "$status_path") > 0 )); then
    while IFS="" read -r line || [ -n "$line" ]; do
        user=$(echo "$line" | awk '{ print $1 }')
        state=$(echo "$line" | awk '{ print $2 }')
        timestamp=$(echo "$line" | awk '{ print $3 }')
        previous_states["$user"]="$state $timestamp"
    done < "$status_path"
fi

truncate -s 0 "$status_path"

system_state="$(systemctl show --value --property=SystemState)"
previous_state_details="${previous_states['root']}"
prev_state=$(echo "$previous_state_details" | awk '{ print $1 }')
prev_timestamp=$(echo "$previous_state_details" | awk '{ print $2 }')
timestamp=$(date -u +%s)
if [[ $system_state == "$prev_state" ]] && [[ -n "$prev_timestamp" ]]; then
    timestamp=$prev_timestamp
fi
echo "root $system_state $timestamp" >> "$status_path"

for uname in "${user_names[@]}"; do
    user_system_state="$(systemctl --machine="$uname"@ --user show --value --property=SystemState)"
    previous_state_details="${previous_states[$uname]}"
    prev_state=$(echo "$previous_state_details" | awk '{ print $1 }')
    prev_timestamp=$(echo "$previous_state_details" | awk '{ print $2 }')
    timestamp=$(date -u +%s)
    if [[ $user_system_state == "$prev_state" ]] && [[ -n "$prev_timestamp" ]]; then
        timestamp="$prev_timestamp"
    fi
    echo "$uname $user_system_state $timestamp" >> "$status_path"
done

# Some system failures are reported to the local mailbox, so checking mail can
# sometimes reveal problems.
truncate -s 0 "$mail_path"
if mail -e >/dev/null 2>&1; then
    echo "root yes" >> "$mail_path"
fi
for uname in "${user_names[@]}"; do
    if [[ -e "/var/mail/$uname" ]] || [[ -e "/var/spool/mail/$uname" ]]; then
        if (( "$(wc --bytes < <(cat "/var/mail/$uname"))" > 0 )) ||
                (( "$(wc --bytes < <(cat "/var/spool/mail/$uname"))" > 0 )); then
            echo "$uname yes" >> "$mail_path"
        fi
    fi
done

# If the system has any RAID arrays, check if there are any failures.
if [[ -e "$raid_path" ]]; then
    rm "$raid_path"
fi
find /dev -maxdepth 1 -name 'md*' 2>/dev/null | while read -r raid_volume; do
    failed_count=$(mdadm --detail "$raid_volume" | grep 'Failed Devices' | awk -F ' : ' '{ print $2 }')
    if [[ $failed_count -gt 0 ]]; then
        mdadm --detail "$raid_volume" > "$raid_path" 2>&1
    fi
done
