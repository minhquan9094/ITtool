#!/usr/bin/env python3
# -*- coding: utf-8 -*-

# Author: [Your Name/Initials Here] - Based on Gemini Script
# Date: 2025-04-05
# Purpose: Tests network connectivity (Ping, HTTP/S, TCP Ports) for specified hosts.
#          Supports input via CSV or command-line args, outputs to console and optionally CSV file.

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
REQUEST_TIMEOUT = 5 # Timeout for HTTP/HTTPS requests
PING_TIMEOUT = 3    # Timeout for ping command execution
TCP_TIMEOUT = 3     # Timeout for generic TCP port connections

# --- Colored Status Strings ---
STATUS_SUCCESS = f"{Fore.GREEN}SUCCESS{Style.RESET_ALL}"
STATUS_FAILED = f"{Fore.RED}FAILED{Style.RESET_ALL}"
STATUS_WARNING = f"{Fore.YELLOW}WARNING{Style.RESET_ALL}"
STATUS_SKIP = f"{Fore.YELLOW}SKIP{Style.RESET_ALL}"
STATUS_ERROR = f"{Fore.RED}ERROR{Style.RESET_ALL}"

# --- Field names for CSV output ---
CSV_FIELDNAMES = ['Timestamp', 'TargetHost', 'Service', 'Status', 'Details']

# --- Test Functions ---

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
    else: # Linux, macOS - '-W' is timeout in seconds
        timeout_param = ['-W', str(PING_TIMEOUT)]

    command = ['ping', param, '1'] + timeout_param + [hostname]

    try:
        # Use subprocess.run for better control
        result = subprocess.run(
            command,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            timeout=PING_TIMEOUT + 1, # Give subprocess slightly more time
            check=False # Don't raise exception on non-zero exit code
        )
        if result.returncode == 0:
            result_data['Status'] = 'SUCCESS'
            result_data['Details'] = 'Responded to ICMP echo request'
            result_data['SuccessBool'] = True
        else:
            # Distinguish reason for failure if possible
            try:
                 socket.gethostbyname(hostname) # Check DNS resolution
                 result_data['Details'] = 'Host Unreachable / ICMP Blocked'
            except socket.gaierror:
                 result_data['Details'] = 'DNS Resolution Error'
            except Exception as dns_e:
                 # Fallback if DNS check fails unexpectedly
                 result_data['Details'] = f"Ping failed (Exit: {result.returncode}), DNS Check Error: {dns_e}"
            else: # DNS resolved, but ping failed
                 result_data['Details'] = f"Ping failed (Exit: {result.returncode}), {result_data['Details']}"

    except subprocess.TimeoutExpired:
        result_data['Details'] = 'Timeout'
    except FileNotFoundError:
        result_data['Details'] = 'Ping command not found?'
    except Exception as e:
        result_data['Details'] = f"Error: {e}"

    # Print console output
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

    try:
        verify_ssl = True # Set to False for self-signed certs (use with caution)
        headers = {'User-Agent': 'Python-NetworkTestScript/1.3'} # Version bump

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
        # else: Status remains FAILED

    except requests.exceptions.Timeout:
        result_data['Details'] = 'Timeout'
    except requests.exceptions.SSLError as e:
         error_summary = str(e).splitlines()[0] # Get first line of error
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

def test_tcp_port(hostname, port, timeout=TCP_TIMEOUT):
    """
    Tests if a specific TCP port is open on the target host using sockets.
    Returns a dictionary with test result details.
    """
    service_name = f'tcp:{port}' # Original requested service name for logging
    # Validate port is integer and in range
    try:
        port_int = int(port)
        if not 0 < port_int < 65536:
            raise ValueError("Port number must be between 1 and 65535")
    except ValueError as e:
         # Return error result immediately if port is invalid
         print(f"  [TCP:{port:<4}] {hostname:<25} -> {STATUS_FAILED} (Invalid port: {e})")
         return {
            'Timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            'TargetHost': hostname,
            'Service': service_name,
            'Status': 'FAILED',
            'Details': f'Invalid port number specified: {e}',
            'SuccessBool': False
        }

    # Valid port, proceed with test
    result_data = {
        'Timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
        'TargetHost': hostname,
        'Service': f'tcp:{port_int}', # Log with the validated integer port
        'Status': 'FAILED', # Default
        'Details': '',
        'SuccessBool': False
    }
    sock = None # Ensure socket variable exists for the finally block

    try:
        # Resolve hostname first to provide better DNS error context
        ip_address = socket.gethostbyname(hostname)

        # Create socket
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(timeout)

        # Attempt connection using resolved IP and integer port
        # connect_ex returns 0 on success, otherwise an error indicator
        result_code = sock.connect_ex((ip_address, port_int))

        if result_code == 0:
            # Connection successful
            result_data['Status'] = 'SUCCESS'
            result_data['Details'] = f'Port {port_int} is open'
            result_data['SuccessBool'] = True
        else:
            # Connection failed - Provide error code context if available
            # Error codes can be OS-dependent (e.g., errno.ECONNREFUSED)
            result_data['Details'] = f'Port {port_int} is closed or filtered (Error code: {result_code})'

    except socket.timeout:
        result_data['Details'] = f'Timeout connecting to port {port_int}'
    except socket.gaierror: # DNS resolution failed
        result_data['Details'] = 'DNS Resolution Error'
    except OverflowError: # Port number might be invalid (less likely with check above)
         result_data['Details'] = f'Invalid port number {port_int}'
    except Exception as e:
        # Catch other potential socket/network errors
        result_data['Details'] = f"Error connecting to port {port_int}: {e}"
    finally:
        # Ensure the socket is closed
        if sock:
            sock.close()

    # Print console output
    final_console_status = STATUS_SUCCESS if result_data['SuccessBool'] else STATUS_FAILED
    details_for_console = f"({result_data['Details']})" if result_data['Details'] else ""
    if result_data['SuccessBool']: # Show details even on success for port check
         details_for_console = f"({result_data['Details']})"

    # Use port_int for aligned output tag
    print(f"  [TCP:{str(port_int):<4}] {hostname:<25} -> {final_console_status} {details_for_console}")

    return result_data


# --- Argument Parsing & Target Loading ---

def load_targets_from_csv(filepath):
    """Loads target hosts and services from a CSV file."""
    targets = []
    if not os.path.isfile(filepath):
        print(f"{STATUS_ERROR}: CSV file not found at '{filepath}'")
        sys.exit(1)
    try:
        with open(filepath, mode='r', encoding='utf-8', newline='') as csvfile:
            # Skip comment lines and empty lines robustly
            reader = csv.reader(filter(lambda row: row and row[0].strip() and not row[0].strip().startswith('#'), csvfile))
            try:
                header = next(reader) # Read the header row
            except StopIteration:
                 print(f"{STATUS_WARNING}: CSV file '{filepath}' is empty or only contains comments/empty lines.")
                 return targets # Return empty list

            # Basic header validation
            if not header or len(header) < 2 or header[0].lower().strip() != 'hostname' or header[1].lower().strip() != 'services':
                 print(f"{STATUS_ERROR}: Invalid CSV header in '{filepath}'. Expected 'hostname,services', got '{','.join(header)}'")
                 sys.exit(1)

            # Process data rows
            for i, row in enumerate(reader):
                 # Check if row has enough columns before accessing indices
                if len(row) >= 2:
                    host = row[0].strip()
                    services_str = row[1].strip()
                    if host and services_str: # Only add if host and services are not empty
                        # Split services string, strip whitespace, remove empty strings
                        services_list = [s.strip().lower() for s in services_str.split(',') if s.strip()]
                        if services_list: # Only add if there are actually services listed
                            targets.append({'host': host, 'services': services_list})
                        else:
                             print(f"{STATUS_WARNING}: Skipping row {i+2} in CSV - No valid services found for host '{host}'.")
                    elif host:
                         print(f"{STATUS_WARNING}: Skipping row {i+2} in CSV - Services column empty for host '{host}'.")
                    # Silently ignore rows with no host if desired, or add warning
                elif row and row[0].strip(): # Row exists but might be missing services column
                    print(f"{STATUS_WARNING}: Skipping row {i+2} in CSV - Missing services column for host '{row[0].strip()}'.")
                # Ignore completely empty rows (already filtered) or rows with only whitespace

    except FileNotFoundError: # Should be caught by os.path.isfile, but good practice
        print(f"{STATUS_ERROR}: CSV file not found at '{filepath}'")
        sys.exit(1)
    except Exception as e:
        print(f"{STATUS_ERROR} reading CSV file '{filepath}': {e}")
        sys.exit(1)

    if not targets:
        print(f"{STATUS_WARNING}: No valid targets loaded from CSV file '{filepath}'.")

    return targets


def setup_arg_parser():
    """Configures and returns the argument parser."""
    parser = argparse.ArgumentParser(
        description=f"{Style.BRIGHT}Network Service Test Script{Style.RESET_ALL}. Tests Ping, HTTP/S, and generic TCP ports.",
        epilog="Example Usage:\n"
               "  Single Host (Ping, HTTPS): python network_test.py --host google.com --services ping,https\n"
               "  Single Host (SSH Port):    python network_test.py --host my-server.local --services tcp:22\n"
               "  From CSV:                  python network_test.py --csv targets.csv\n"
               "  Export Results:            python network_test.py --csv targets.csv --output-file results.csv\n\n"
               "Service Format:\n"
               "  'ping', 'http', 'https'\n"
               "  'tcp:<port>' (e.g., 'tcp:22', 'tcp:3389')",
        formatter_class=argparse.RawDescriptionHelpFormatter # Keep newlines in epilog
    )

    # Group for mutually exclusive input methods
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument('--host', type=str, help='Hostname or IP address of the single target to test.')
    group.add_argument('--csv', type=str, help='Path to the CSV file containing targets (hostname,services).')

    # Services argument - only relevant if --host is used
    parser.add_argument('--services', type=str,
                        help='Comma-separated list of services to test for the single host (e.g., "ping,http,tcp:22"). Required if --host is used.')

    # Optional output file argument
    parser.add_argument('--output-file', '--outfile', type=str, default=None,
                        help='Optional path to export detailed results to a CSV file.')

    return parser

# --- Main Execution ---

if __name__ == "__main__":
    parser = setup_arg_parser()
    args = parser.parse_args()

    targets_to_test = []

    # Validate arguments and load targets
    if args.csv:
        print(f"Loading targets from CSV file: {Fore.CYAN}{args.csv}{Style.RESET_ALL}")
        targets_to_test = load_targets_from_csv(args.csv)
    elif args.host:
        # Load from command line arguments
        if not args.services:
            parser.error("--services is required when --host is specified.")
        host = args.host.strip()
        services_str = args.services.strip()
        if host and services_str:
            # Split services string, strip whitespace, remove empty strings
            services_list = [s.strip().lower() for s in services_str.split(',') if s.strip()]
            if services_list:
                targets_to_test = [{'host': host, 'services': services_list}]
            else:
                 print(f"{STATUS_ERROR}: No valid services provided via --services argument.")
                 sys.exit(1)
        else:
            print(f"{STATUS_ERROR}: --host and --services arguments cannot be empty.")
            sys.exit(1)
    # The 'required=True' in the mutually exclusive group ensures we have either --csv or --host.

    if not targets_to_test:
        print("No targets specified or loaded. Exiting.")
        sys.exit(0) # Exit gracefully if no targets loaded

    print(f"\n{Style.BRIGHT}Starting Network Service Tests...{Style.RESET_ALL}")
    if args.output_file:
        print(f"(Results will also be exported to: {Fore.CYAN}{args.output_file}{Style.RESET_ALL})")

    all_tests_passed = True
    all_results_data = [] # List to store result dictionaries for export

    for target in targets_to_test:
        host = target.get('host')
        services = target.get('services', []) # Default to empty list

        print(f"\nTesting Target: {Fore.CYAN}{host}{Style.RESET_ALL}")
        target_all_passed = True

        for service in services:
            result_data = None # Reset for each service test
            service_lower = service.lower() # Work with lowercase internally

            # --- Service Test Dispatch ---
            if service_lower == 'ping':
                result_data = test_ping(host)
            elif service_lower == 'http':
                result_data = test_http_https(host, service_type='http', timeout=REQUEST_TIMEOUT)
            elif service_lower == 'https':
                result_data = test_http_https(host, service_type='https', timeout=REQUEST_TIMEOUT)
            elif ':' in service_lower:
                # Handle format like "tcp:port", "dns:port", etc.
                try:
                    service_type, port_str = service_lower.split(':', 1)
                    # Currently only support 'tcp' type explicitly
                    if service_type == 'tcp':
                        result_data = test_tcp_port(host, port_str, timeout=TCP_TIMEOUT)
                    # Add elif for other types like 'dns' or 'udp' if functions are added
                    # elif service_type == 'dns':
                    #    result_data = test_dns_port(host, port_str)
                    else:
                        print(f"  [{STATUS_SKIP}]   Unsupported service type '{service_type}' in '{service}' for host {host}")
                        # Create placeholder for CSV
                        result_data = {
                            'Timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S'), 'TargetHost': host,
                            'Service': service, 'Status': 'SKIPPED',
                            'Details': f'Unsupported service type {service_type}', 'SuccessBool': True
                        }
                except ValueError: # Handle case where split fails (e.g., "tcp:")
                     print(f"  [{STATUS_SKIP}]   Invalid service format '{service}' for host {host}")
                     # Create placeholder for CSV
                     result_data = {
                         'Timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S'), 'TargetHost': host,
                         'Service': service, 'Status': 'SKIPPED',
                         'Details': 'Invalid service:port format', 'SuccessBool': True
                     }
            else: # Service didn't match known types or format
                print(f"  [{STATUS_SKIP}]   Unknown service type '{service}' for host {host}")
                # Create placeholder for CSV
                result_data = {
                    'Timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                    'TargetHost': host,
                    'Service': service,
                    'Status': 'SKIPPED',
                    'Details': 'Unknown service type',
                    'SuccessBool': True # Treat skip as not-a-failure
                }

            # --- Store Result and Check Status ---
            if result_data:
                all_results_data.append(result_data)
                # Check if this specific test failed (and wasn't skipped)
                if not result_data.get('SuccessBool', True) and result_data.get('Status') != 'SKIPPED':
                    target_all_passed = False
                    all_tests_passed = False # Update overall script status

        # --- Optional: Print per-target summary ---
        status_word = STATUS_SUCCESS if target_all_passed else STATUS_FAILED
        print(f"Target Status [{Fore.CYAN}{host}{Style.RESET_ALL}]: {status_word}")
        print("-" * 50) # Separator between hosts

    # --- Export Results if requested ---
    if args.output_file:
        if all_results_data:
            print(f"\nExporting results to {Fore.CYAN}{args.output_file}{Style.RESET_ALL}...")
            try:
                # Ensure output directory exists
                output_dir = os.path.dirname(args.output_file)
                if output_dir and not os.path.exists(output_dir):
                    print(f"Creating output directory: {output_dir}")
                    os.makedirs(output_dir, exist_ok=True)

                # Write to CSV using DictWriter
                with open(args.output_file, mode='w', newline='', encoding='utf-8') as csvfile:
                    # Use extrasaction='ignore' to handle the extra 'SuccessBool' key
                    writer = csv.DictWriter(csvfile, fieldnames=CSV_FIELDNAMES, extrasaction='ignore')
                    writer.writeheader()
                    writer.writerows(all_results_data) # Ignores 'SuccessBool' automatically

                print(f"Export {Fore.GREEN}complete.{Style.RESET_ALL}")
            except IOError as e:
                print(f"{STATUS_ERROR} writing to output file '{args.output_file}': {e}")
                all_tests_passed = False # Mark overall status as failed if export fails
            except Exception as e:
                print(f"{STATUS_ERROR} during export: {e}")
                all_tests_passed = False
        else:
            print(f"\n{STATUS_WARNING}: No results to export (list was empty).")


    # --- Final Summary ---
    print(f"\n{Style.BRIGHT}Testing Complete.{Style.RESET_ALL}")
    if all_tests_passed:
        print(f"Overall Status: {Fore.GREEN}{Style.BRIGHT}All specified tests passed (and export successful if attempted).{Style.RESET_ALL}")
        sys.exit(0) # Exit code 0 for success
    else:
        print(f"Overall Status: {Fore.RED}{Style.BRIGHT}One or more tests failed (or export failed).{Style.RESET_ALL}")
        sys.exit(1) # Exit code 1 for failure

# --- End of Script ---