//  SPDX-FileCopyrightText: 2026 Daniel P. Herbert <status-report-dan@hrbrt.co>
//  SPDX-License-Identifier: AGPL-3.0-only
//  @license mmagnet:?xt=urn:btih:0b31508aeb0634b347b8270c7bee4d411b5d4109&dn=agpl-3.0.txt agpl-3.0

function formatTimeDeltaShort(timeDelta: TimeDelta, suffix: string) {
  let relativeStr = "";
  if (timeDelta.days > 0) {
    relativeStr += `${timeDelta.days}d `;
  }
  if (timeDelta.hours > 0) {
    relativeStr += `${timeDelta.hours}h `;
  }
  let minutes = Math.max(timeDelta.minutes, 1);
  if (timeDelta.seconds > 29) {
    minutes++;
  }
  relativeStr += `${minutes}m `;
  relativeStr += suffix;
  return relativeStr;
}

function formatTimeDeltaLong(timeDelta: TimeDelta, suffix: string) {
  let relativeStr = "";
  if (timeDelta.days > 0) {
    relativeStr += `${timeDelta.days} days `;
  }
  if (timeDelta.hours > 0) {
    if (timeDelta.hours === 1) {
      relativeStr += `${timeDelta.hours} hour `;
    } else {
      relativeStr += `${timeDelta.hours} hours `;
    }
  }
  let minutes = timeDelta.minutes;
  if (timeDelta.days > 0 || timeDelta.hours > 0) {
    minutes = Math.max(minutes, 1);
    if (timeDelta.seconds > 29) {
      minutes++;
    }
  }
  if (minutes > 0) {
    if (minutes === 1) {
      relativeStr += `${minutes} minute `;
    } else {
      relativeStr += `${minutes} minutes `;
    }
  }
  if (timeDelta.days === 0 && timeDelta.hours == 0) {
    if (timeDelta.seconds === 1) {
      relativeStr += `${timeDelta.seconds} second `;
    } else {
      relativeStr += `${timeDelta.seconds} seconds `;
    }
  }
  relativeStr += suffix;
  return relativeStr;
}

function timesToRelative() {
  document.querySelectorAll("time[datetime]").forEach((elem) => {
    const timeElem = elem as HTMLTimeElement;
    const elapsed = Date.now() - new Date(timeElem.dateTime).getTime();

    const seconds = Math.floor(elapsed / 1000);
    const minutes = Math.floor(seconds / 60);
    const hours = Math.floor(minutes / 60);

    const delta: TimeDelta = {
      days: Math.floor(hours / 24),
      hours: hours % 24,
      minutes: minutes % 60,
      seconds: seconds % 60,
    };

    if (timeElem.classList.contains("uptime")) {
      timeElem.innerText = formatTimeDeltaShort(delta, "");
    } else if (timeElem.classList.contains("check-time")) {
      timeElem.innerText = formatTimeDeltaShort(delta, "ago");
    } else {
      timeElem.innerText = formatTimeDeltaLong(delta, "ago");
    }
  });
}

setInterval(timesToRelative, 1000);
timesToRelative();

//  @license-end
