import re
import csv
import json
import argparse
import logging
from collections import Counter, defaultdict
from datetime import datetime


# Supported log format:
# YYYY-MM-DD HH:MM:SS | LEVEL | SERVICE | MESSAGE

LOG_PATTERN = re.compile(
    r"^(?P<timestamp>\d{4}-\d{2}-\d{2} "
    r"\d{2}:\d{2}:\d{2})\s*\|\s*"
    r"(?P<level>INFO|WARNING|ERROR|CRITICAL)\s*\|\s*"
    r"(?P<service>[^|]+?)\s*\|\s*"
    r"(?P<message>.*)$"
)


def parse_log_line(line):
    match = LOG_PATTERN.match(line.strip())

    if not match:
        return None

    data = match.groupdict()

    return {
        "timestamp": data["timestamp"],
        "level": data["level"],
        "service": data["service"].strip(),
        "message": data["message"].strip()
    }


def normalize_error(message):
    message_lower = message.lower()

    if "database connection" in message_lower:
        return "database_connection_failed"

    if "timeout" in message_lower:
        return "timeout"

    if "authentication" in message_lower:
        return "authentication_error"

    if "login failed" in message_lower:
        return "authentication_error"

    if "payment failed" in message_lower:
        return "payment_error"

    if "not found" in message_lower:
        return "not_found_error"

    return "other_error"


def get_time_window(timestamp, window_minutes):
    dt = datetime.strptime(timestamp, "%Y-%m-%d %H:%M:%S")

    minute = (dt.minute // window_minutes) * window_minutes

    window_start = dt.replace(
        minute=minute,
        second=0
    )

    return window_start.strftime("%Y-%m-%d %H:%M:%S")


def read_logs(filename):
    logs = []

    with open(filename, "r", encoding="utf-8") as file:
        for line in file:
            parsed = parse_log_line(line)

            if parsed:
                logs.append(parsed)
            else:
                logging.warning("Invalid log line skipped")

    return logs


def aggregate_errors(logs, window_minutes):
    service_counts = Counter()
    error_type_counts = Counter()
    time_window_counts = Counter()
    combined_counts = Counter()

    for log in logs:
        if log["level"] in ("ERROR", "CRITICAL"):
            service = log["service"]
            error_type = normalize_error(log["message"])
            time_window = get_time_window(
                log["timestamp"],
                window_minutes
            )

            service_counts[service] += 1
            error_type_counts[error_type] += 1
            time_window_counts[time_window] += 1

            combined_counts[
                (service, error_type, time_window)
            ] += 1

    return (
        service_counts,
        error_type_counts,
        time_window_counts,
        combined_counts
    )


def detect_anomalies(time_window_counts, threshold):
    anomalies = []

    for time_window, count in time_window_counts.items():
        if count >= threshold:
            anomalies.append({
                "time_window": time_window,
                "error_count": count,
                "reason": "Error count exceeded threshold"
            })

    return anomalies


def generate_incident_report(logs):
    incidents = defaultdict(list)

    for log in logs:
        if log["level"] in ("ERROR", "CRITICAL"):
            error_type = normalize_error(log["message"])

            key = (
                log["service"],
                error_type
            )

            incidents[key].append(log)

    report = []

    for (service, error_type), entries in incidents.items():
        timestamps = [
            entry["timestamp"]
            for entry in entries
        ]

        report.append({
            "service": service,
            "error_type": error_type,
            "frequency": len(entries),
            "first_occurrence": min(timestamps),
            "last_occurrence": max(timestamps)
        })

    report.sort(
        key=lambda item: item["frequency"],
        reverse=True
    )

    return report


def export_csv(filename, report):
    if not report:
        return

    fieldnames = [
        "service",
        "error_type",
        "frequency",
        "first_occurrence",
        "last_occurrence"
    ]

    with open(
        filename,
        "w",
        newline="",
        encoding="utf-8"
    ) as file:

        writer = csv.DictWriter(
            file,
            fieldnames=fieldnames
        )

        writer.writeheader()
        writer.writerows(report)


def export_json(filename, report):
    with open(
        filename,
        "w",
        encoding="utf-8"
    ) as file:

        json.dump(
            report,
            file,
            indent=4
        )


def print_report(
    service_counts,
    error_type_counts,
    time_window_counts,
    anomalies,
    report
):
    print("\nINCIDENT SUMMARY")
    print("================")

    print("\nTop Incidents:")

    for incident in report[:10]:
        print(
            f"{incident['service']} | "
            f"{incident['error_type']} | "
            f"Frequency: {incident['frequency']} | "
            f"First: {incident['first_occurrence']} | "
            f"Last: {incident['last_occurrence']}"
        )

    print("\nErrors by Service:")

    for service, count in service_counts.most_common():
        print(f"{service}: {count}")

    print("\nErrors by Type:")

    for error_type, count in error_type_counts.most_common():
        print(f"{error_type}: {count}")

    print("\nErrors by Time Window:")

    for time_window, count in sorted(
        time_window_counts.items()
    ):
        print(f"{time_window}: {count}")

    print("\nDetected Anomalies:")

    if anomalies:
        for anomaly in anomalies:
            print(
                f"{anomaly['time_window']} - "
                f"{anomaly['error_count']} errors - "
                f"{anomaly['reason']}"
            )
    else:
        print("No anomalies detected.")


def main():
    parser = argparse.ArgumentParser(
        description="Log Monitoring & Incident Summary Tool"
    )

    parser.add_argument(
        "logfile",
        help="Path to the log file"
    )

    parser.add_argument(
        "--threshold",
        type=int,
        default=3,
        help="Error threshold for anomaly detection"
    )

    parser.add_argument(
        "--window",
        type=int,
        default=5,
        help="Time window size in minutes"
    )

    parser.add_argument(
        "--csv",
        help="Optional CSV output file"
    )

    parser.add_argument(
        "--json",
        help="Optional JSON output file"
    )

    args = parser.parse_args()

    logging.basicConfig(
        level=logging.INFO,
        format="%(levelname)s: %(message)s"
    )

    logging.info("Starting Log Monitoring Tool")

    logs = read_logs(args.logfile)

    if not logs:
        print("No valid logs found.")
        return

    logging.info(
        "Successfully parsed %d log entries",
        len(logs)
    )

    (
        service_counts,
        error_type_counts,
        time_window_counts,
        combined_counts
    ) = aggregate_errors(
        logs,
        args.window
    )

    anomalies = detect_anomalies(
        time_window_counts,
        args.threshold
    )

    report = generate_incident_report(logs)

    print_report(
        service_counts,
        error_type_counts,
        time_window_counts,
        anomalies,
        report
    )

    if args.csv:
        export_csv(
            args.csv,
            report
        )
        logging.info(
            "CSV report exported to %s",
            args.csv
        )

    if args.json:
        export_json(
            args.json,
            report
        )
        logging.info(
            "JSON report exported to %s",
            args.json
        )

    logging.info("Processing completed")


if __name__ == "__main__":
    main()