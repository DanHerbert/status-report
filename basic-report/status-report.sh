#!/bin/bash -e

if [[ $EUID != 0 ]]; then
    echo 'Script must be run as root'
    exit 1
fi

primary_user_state_home="/home/dan/.local/state"
app_state_path="$primary_user_state_home/dotfiles"
status_path="$app_state_path/system_state"
mail_path="$app_state_path/mail_state"
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
    if [[ $system_state == "$prev_state" ]] && [[ -n "$prev_timestamp" ]]; then
        timestamp="$prev_timestamp"
    fi
    echo "$uname $user_system_state $timestamp" >> "$status_path"
done

truncate -s 0 "$mail_path"
if mail -e >/dev/null 2>&1; then
    echo "mailbox_unread root yes" >> "$mail_path"
fi
for uname in "${user_names[@]}"; do
    if [[ -e "/var/mail/$uname" ]] || [[ -e "/var/spool/mail/$uname" ]]; then
        echo "mailbox_unread $uname yes" >> "$mail_path"
    fi
done
