#!/usr/bin/env python3
import subprocess
import platform
import requests
import socket
import argparse
import csv
import sys
import os
import colorama # Import colorama
from colorama import Fore, Style # Import specific objects
from datetime import datetime # For timestamp

# --- Initialize Colorama ---
colorama.init(autoreset=True)

# --- Configuration (Defaults & Constants) ---
REQUEST_TIMEOUT = 5
PING_TIMEOUT = 3

# --- Colored Status Strings ---
STATUS_SUCCESS = f"{Fore.GREEN}SUCCESS{Style.RESET_ALL}"
STATUS_FAILED = f"{Fore.RED}FAILED{Style.RESET_ALL}"
STATUS_WARNING = f"{Fore.YELLOW}WARNING{Style.RESET_ALL}"
STATUS_SKIP = f"{Fore.YELLOW}SKIP{Style.RESET_ALL}"
STATUS_ERROR = f"{Fore.RED}ERROR{Style.RESET_ALL}"

# --- Field names for CSV output ---
CSV_FIELDNAMES = ['Timestamp', 'TargetHost', 'Service', 'Status', 'Details']

# --- Test Functions (Modified to return result dictionary) ---

def test_ping(hostname):
    """
    Tests reachability using the system's ping command.
    Returns a dictionary with test result details.
    """
    result_data = {
        'Timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
        'TargetHost': hostname,
        'Service': 'ping',
        'Status': 'FAILED', # Default
        'Details': '',
        'SuccessBool': False # Internal flag
    }

    param = '-n' if platform.system().lower() == 'windows' else '-c'
    timeout_param = []
    if platform.system().lower() == 'windows':
        timeout_param = ['-w', str(PING_TIMEOUT * 1000)]
    else:
        timeout_param = ['-W', str(PING_TIMEOUT)]

    command = ['ping', param, '1'] + timeout_param + [hostname]
    console_status = STATUS_FAILED # Default console status

    try:
        result = subprocess.run(
            command,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            timeout=PING_TIMEOUT + 1,
            check=False
        )
        if result.returncode == 0:
            result_data['Status'] = 'SUCCESS'
            result_data['Details'] = 'Responded to ICMP echo request'
            result_data['SuccessBool'] = True
            console_status = STATUS_SUCCESS
        else:
            # Distinguish reason for failure
            try:
                 socket.gethostbyname(hostname)
                 result_data['Details'] = 'Host Unreachable / ICMP Blocked'
            except socket.gaierror:
                 result_data['Details'] = 'DNS Resolution Error'
            except Exception as dns_e:
                 result_data['Details'] = f"Ping failed (Exit: {result.returncode}), DNS Check Error: {dns_e}"
            else: # If DNS check succeeds but ping failed
                 result_data['Details'] = f"Ping failed (Exit: {result.returncode}), {result_data['Details']}"


    except subprocess.TimeoutExpired:
        result_data['Details'] = 'Timeout'
    except FileNotFoundError:
        result_data['Details'] = 'Ping command not found?'
        # Update console status directly here for clarity if needed
        # console_status = f"{STATUS_FAILED} ({STATUS_ERROR}: {result_data['Details']})"
    except Exception as e:
        result_data['Details'] = f"Error: {e}"
        # console_status = f"{STATUS_FAILED} ({STATUS_ERROR}: {e})"

    # Print console output (can now include details)
    # Determine console status based on SuccessBool AFTER try/except block
    final_console_status = STATUS_SUCCESS if result_data['SuccessBool'] else STATUS_FAILED
    details_for_console = f"({result_data['Details']})" if not result_data['SuccessBool'] and result_data['Details'] else ""
    print(f"  [PING]   {hostname:<25} -> {final_console_status} {details_for_console}")

    return result_data


def test_http_https(hostname, service_type='https', timeout=REQUEST_TIMEOUT):
    """
    Tests HTTP or HTTPS connectivity and checks for a successful status code (2xx).
    Returns a dictionary with test result details.
    """
    protocol = 'https' if service_type == 'https' else 'http'
    url = f"{protocol}://{hostname}"

    result_data = {
        'Timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
        'TargetHost': hostname,
        'Service': service_type,
        'Status': 'FAILED', # Default
        'Details': '',
        'SuccessBool': False # Internal flag
    }
    service_tag = f"[{service_type.upper()}]"
    # console_status = STATUS_FAILED # Default console status

    try:
        verify_ssl = True
        headers = {'User-Agent': 'Python-NetworkTestScript/1.2'} # Version bump

        response = requests.get(
            url,
            timeout=timeout,
            verify=verify_ssl,
            allow_redirects=True,
            headers=headers
        )

        result_data['Details'] = f"HTTP Status {response.status_code}"
        if response.status_code >= 200 and response.status_code < 300:
            result_data['Status'] = 'SUCCESS'
            result_data['SuccessBool'] = True
            # console_status = STATUS_SUCCESS
        # else: Status remains FAILED

    except requests.exceptions.Timeout:
        result_data['Details'] = 'Timeout'
    except requests.exceptions.SSLError as e:
         error_summary = str(e).splitlines()[0]
         result_data['Details'] = f"SSL Error: {error_summary}"
    except requests.exceptions.ConnectionError as e:
        # Try DNS resolution for context
        try:
            socket.gethostbyname(hostname)
            result_data['Details'] = "Connection Error - Host resolved, but couldn't connect"
        except socket.gaierror:
             result_data['Details'] = "DNS Resolution Error"
        except Exception as dns_e:
             result_data['Details'] = f"Connection/DNS Check Error: {dns_e}"
    except requests.exceptions.RequestException as e:
        result_data['Details'] = f"Request Error: {e}"
    except Exception as e:
        result_data['Details'] = f"Unexpected Error: {e}"

    # Print console output
    final_console_status = STATUS_SUCCESS if result_data['SuccessBool'] else STATUS_FAILED
    details_for_console = f"({result_data['Details']})" if result_data['Details'] else ""
    # Special case for SUCCESS details
    if result_data['SuccessBool']:
         details_for_console = f"({result_data['Details']})"

    print(f"  {service_tag:<7} {url:<28} -> {final_console_status} {details_for_console}")

    return result_data


# --- Argument Parsing & Target Loading ---
# (Load Targets function remains the same)
def load_targets_from_csv(filepath):
    """Loads target hosts and services from a CSV file."""
    targets = []
    if not os.path.isfile(filepath):
        print(f"{STATUS_ERROR}: CSV file not found at '{filepath}'")
        sys.exit(1)
    try:
        with open(filepath, mode='r', encoding='utf-8', newline='') as csvfile:
            reader = csv.reader(filter(lambda row: row.strip() and not row.strip().startswith('#'), csvfile))
            try:
                header = next(reader)
            except StopIteration:
                 print(f"{STATUS_WARNING}: CSV file '{filepath}' is empty or only contains comments.")
                 return targets
            if not header or len(header) < 2 or header[0].lower() != 'hostname' or header[1].lower() != 'services':
                 print(f"{STATUS_ERROR}: Invalid CSV header in '{filepath}'. Expected 'hostname,services', got '{','.join(header)}'")
                 sys.exit(1)
            for i, row in enumerate(reader):
                 if not row or not any(field.strip() for field in row): continue
                 if len(row) >= 2:
                    host = row[0].strip()
                    services_str = row[1].strip()
                    if host and services_str:
                        services_list = [s.strip().lower() for s in services_str.split(',') if s.strip()]
                        if services_list: targets.append({'host': host, 'services': services_list})
                        else: print(f"{STATUS_WARNING}: Skipping row {i+2} in CSV - No valid services found for host '{host}'.")
                    elif host: print(f"{STATUS_WARNING}: Skipping row {i+2} in CSV - Services column empty for host '{host}'.")
                 elif row and row[0].strip(): print(f"{STATUS_WARNING}: Skipping row {i+2} in CSV - Missing services column for host '{row[0].strip()}'.")
    except FileNotFoundError:
        print(f"{STATUS_ERROR}: CSV file not found at '{filepath}'")
        sys.exit(1)
    except Exception as e:
        print(f"{STATUS_ERROR} reading CSV file '{filepath}': {e}")
        sys.exit(1)
    if not targets: print(f"{STATUS_WARNING}: No valid targets loaded from CSV file '{filepath}'.")
    return targets

# (Setup Arg Parser function remains the same)
def setup_arg_parser():
    """Configures and returns the argument parser."""
    parser = argparse.ArgumentParser(
        description=f"{Style.BRIGHT}Network Service Test Script{Style.RESET_ALL}. Test ping, HTTP, HTTPS connectivity and optionally export results.",
        epilog="Example Usage:\n"
               "  Single Host: python network_test.py --host google.com --services ping,https\n"
               "  From CSV:    python network_test.py --csv targets.csv\n"
               "  Export CSV:  python network_test.py --csv targets.csv --output-file results.csv",
        formatter_class=argparse.RawDescriptionHelpFormatter
    )
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument('--host', type=str, help='Hostname or IP address of the single target to test.')
    group.add_argument('--csv', type=str, help='Path to the CSV file containing targets (hostname,services).')
    parser.add_argument('--services', type=str, help='Comma-separated list of services to test for the single host (e.g., "ping,http,https"). Required if --host is used.')
    parser.add_argument('--output-file', '--outfile', type=str, default=None,
                        help='Optional path to export detailed results to a CSV file.')
    return parser

# --- Main Execution ---

if __name__ == "__main__":
    parser = setup_arg_parser()
    args = parser.parse_args()

    targets_to_test = []
    # Load targets (logic remains the same)
    if args.csv:
        print(f"Loading targets from CSV file: {Fore.CYAN}{args.csv}{Style.RESET_ALL}")
        targets_to_test = load_targets_from_csv(args.csv)
    elif args.host:
        if not args.services: parser.error("--services is required when --host is specified.")
        host = args.host.strip(); services_str = args.services.strip()
        if host and services_str:
            services_list = [s.strip().lower() for s in services_str.split(',') if s.strip()]
            if services_list: targets_to_test = [{'host': host, 'services': services_list}]
            else: print(f"{STATUS_ERROR}: No valid services provided via --services argument."); sys.exit(1)
        else: print(f"{STATUS_ERROR}: --host and --services arguments cannot be empty."); sys.exit(1)

    if not targets_to_test:
        print("No targets specified or loaded. Exiting.")
        sys.exit(0)

    print(f"\n{Style.BRIGHT}Starting Network Service Tests...{Style.RESET_ALL}")
    if args.output_file:
        print(f"(Results will also be exported to: {Fore.CYAN}{args.output_file}{Style.RESET_ALL})")

    all_tests_passed = True
    all_results_data = [] # List to store result dictionaries for export

    for target in targets_to_test:
        host = target.get('host')
        services = target.get('services', [])
        print(f"\nTesting Target: {Fore.CYAN}{host}{Style.RESET_ALL}")
        target_all_passed = True

        for service in services:
            result_data = None # Reset
            service_lower = service.lower()

            if service_lower == 'ping':
                result_data = test_ping(host)
            elif service_lower == 'http':
                result_data = test_http_https(host, service_type='http', timeout=REQUEST_TIMEOUT)
            elif service_lower == 'https':
                result_data = test_http_https(host, service_type='https', timeout=REQUEST_TIMEOUT)
            else:
                print(f"  [{STATUS_SKIP}]   Unknown service type '{service}' for host {host}")
                # Create placeholder result for CSV if needed
                result_data = {
                    'Timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                    'TargetHost': host,
                    'Service': service,
                    'Status': 'SKIPPED',
                    'Details': 'Unknown service type',
                    'SuccessBool': True # Treat skip as not-a-failure
                }

            # Store result and check status
            if result_data:
                all_results_data.append(result_data)
                if not result_data['SuccessBool'] and result_data['Status'] != 'SKIPPED':
                    target_all_passed = False
                    all_tests_passed = False

        # Optional: Print per-target summary
        status_word = STATUS_SUCCESS if target_all_passed else STATUS_FAILED
        print(f"Target Status [{Fore.CYAN}{host}{Style.RESET_ALL}]: {status_word}")
        print("-" * 50) # Separator

    # --- Export Results if requested ---
    if args.output_file:
        if all_results_data:
            print(f"\nExporting results to {Fore.CYAN}{args.output_file}{Style.RESET_ALL}...")
            try:
                # Ensure directory exists
                output_dir = os.path.dirname(args.output_file)
                if output_dir and not os.path.exists(output_dir):
                    print(f"Creating output directory: {output_dir}")
                    os.makedirs(output_dir, exist_ok=True)

                # Write to CSV using DictWriter
                with open(args.output_file, mode='w', newline='', encoding='utf-8') as csvfile:
                    # *** FIX: Add extrasaction='ignore' to handle the extra 'SuccessBool' key ***
                    writer = csv.DictWriter(csvfile, fieldnames=CSV_FIELDNAMES, extrasaction='ignore')
                    writer.writeheader()
                    writer.writerows(all_results_data) # Now ignores 'SuccessBool' automatically

                print(f"Export {Fore.GREEN}complete.{Style.RESET_ALL}")
            except IOError as e:
                print(f"{STATUS_ERROR} writing to output file '{args.output_file}': {e}")
                all_tests_passed = False # Mark overall status as failed if export fails
            except Exception as e:
                print(f"{STATUS_ERROR} during export: {e}")
                all_tests_passed = False
        else:
            print(f"\n{STATUS_WARNING}: No results to export.")


    # --- Final Summary ---
    print(f"\n{Style.BRIGHT}Testing Complete.{Style.RESET_ALL}")
    if all_tests_passed:
        print(f"Overall Status: {Fore.GREEN}{Style.BRIGHT}All specified tests passed (and export successful if attempted).{Style.RESET_ALL}")
        sys.exit(0)
    else:
        print(f"Overall Status: {Fore.RED}{Style.BRIGHT}One or more tests failed (or export failed).{Style.RESET_ALL}")
        sys.exit(1)
