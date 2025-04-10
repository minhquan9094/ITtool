#!/usr/bin/env python3
# -*- coding: utf-8 -*-

# --- Flask Backend with Real Network Test Logic ---
# Purpose: Listens for requests, runs actual network tests (Ping, HTTP/S, TCP),
#          optionally saves results to file on server, returns results via API.

# --- Prerequisites ---
# pip install Flask Flask-CORS requests colorama

import os
import sys
import io
import csv
import subprocess
import platform
import requests
import socket
from flask import Flask, request, jsonify
from flask_cors import CORS
from datetime import datetime
import traceback

# --- Configuration ---
RESULTS_OUTPUT_DIR = "./test_results"
REQUEST_TIMEOUT = 5 # Timeout for HTTP/HTTPS requests
# --- Increased PING_TIMEOUT for debugging ---
PING_TIMEOUT = 5    # Timeout for ping command execution (Increased to 5s)
TCP_TIMEOUT = 3     # Timeout for generic TCP port connections

# --- Status Constants ---
# (Colorama setup remains the same)
try:
    import colorama
    from colorama import Fore, Style
    colorama.init(autoreset=True) # Might still be useful for backend console logs
    STATUS_SUCCESS = "SUCCESS" # Keep simple strings for JSON/CSV
    STATUS_FAILED = "FAILED"
    STATUS_SKIPPED = "SKIPPED"
except ImportError:
    print("Warning: colorama not found. Status strings will be plain.")
    STATUS_SUCCESS = "SUCCESS"
    STATUS_FAILED = "FAILED"
    STATUS_SKIPPED = "SKIPPED"

CSV_FIELDNAMES = ['Timestamp', 'TargetHost', 'Service', 'Status', 'Details']

# --- Actual Network Test Functions (Adapted from script) ---

# --- MODIFIED test_ping function ---
def test_ping(hostname):
    """
    Tests reachability using the system's ping command.
    Captures stderr for better diagnostics. Increased timeout.
    Returns a dictionary with test result details.
    """
    result_data = {
        'Timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
        'TargetHost': hostname, 'Service': 'ping', 'Status': STATUS_FAILED,
        'Details': '', 'SuccessBool': False
    }
    param = '-n' if platform.system().lower() == 'windows' else '-c'
    count = '2' # Send 2 packets instead of 1 for slightly more robustness
    timeout_param = []
    if platform.system().lower() == 'windows':
        # Windows timeout is in milliseconds, per hop. -w affects overall timeout less directly.
        # Using a larger overall subprocess timeout is more reliable here.
        timeout_param = ['-w', str(PING_TIMEOUT * 1000)] # Still set -w
    else:
        # Linux/macOS '-W' is overall timeout in seconds
        timeout_param = ['-W', str(PING_TIMEOUT)]
    # Use full path if known and potentially helpful (e.g., on Linux)
    ping_executable = 'ping'
    # if platform.system().lower() == 'linux': ping_executable = '/bin/ping' # Example

    command = [ping_executable, param, count] + timeout_param + [hostname]
    stderr_output = "" # To store error output from ping command

    try:
        print(f"Running command: {' '.join(command)}") # Log the command being run
        result = subprocess.run(
            command,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.PIPE, # CAPTURE stderr
            timeout=PING_TIMEOUT + 1, # Overall timeout for the subprocess
            check=False,
            text=True # Decode stderr as text
        )
        stderr_output = result.stderr.strip() # Store captured stderr

        if result.returncode == 0:
            result_data.update({'Status': STATUS_SUCCESS, 'Details': 'Responded to ICMP echo request', 'SuccessBool': True})
        else:
            # Ping command failed, try to determine why
            details = f"Ping command failed (Exit: {result.returncode})"
            if stderr_output:
                # Include stderr if the ping command printed anything
                details += f" | Stderr: {stderr_output}"

            # Try DNS resolution to add context
            try:
                 socket.gethostbyname(hostname)
                 # If DNS resolves, failure is likely reachability/firewall
                 # The exit code 1 and message was already suggesting this.
                 result_data['Details'] = f"{details} (Host resolved, but no reply/blocked?)"
            except socket.gaierror:
                 result_data['Details'] = f"{details} (DNS Resolution Error)"
            except Exception as dns_e:
                 result_data['Details'] = f"{details}, DNS Check Error: {dns_e}"

            # If details weren't updated by DNS check, use the base details
            if not result_data['Details']:
                 result_data['Details'] = details

    except subprocess.TimeoutExpired:
        result_data['Details'] = f'Timeout waiting for ping command (>{PING_TIMEOUT}s)'
        if stderr_output: result_data['Details'] += f" | Stderr: {stderr_output}"
    except FileNotFoundError:
        result_data['Details'] = f"Ping command '{ping_executable}' not found?"
    except Exception as e:
        result_data['Details'] = f"Error running ping: {e}"
        if stderr_output: result_data['Details'] += f" | Stderr: {stderr_output}"

    return result_data
# --- End of MODIFIED test_ping function ---

# (test_http_https and test_tcp_port functions remain the same as previous version)
def test_http_https(hostname, service_type='https', timeout=REQUEST_TIMEOUT):
    """
    Tests HTTP or HTTPS connectivity and checks for a successful status code (2xx).
    Returns a dictionary with test result details.
    """
    protocol = 'https' if service_type == 'https' else 'http'
    url = f"{protocol}://{hostname}"
    result_data = {
        'Timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
        'TargetHost': hostname, 'Service': service_type, 'Status': STATUS_FAILED,
        'Details': '', 'SuccessBool': False
    }
    try:
        verify_ssl = False
        headers = {'User-Agent': 'Python-NetworkTestScript/1.3-Backend'}
        response = requests.get(
            url, timeout=timeout, verify=verify_ssl,
            allow_redirects=True, headers=headers
        )
        result_data['Details'] = f"HTTP Status {response.status_code}"
        if 200 <= response.status_code < 300:
            result_data.update({'Status': STATUS_SUCCESS, 'SuccessBool': True})
    except requests.exceptions.Timeout:
        result_data['Details'] = 'Timeout'
    except requests.exceptions.SSLError as e:
         result_data['Details'] = f"SSL Error: {str(e).splitlines()[0]}"
    except requests.exceptions.ConnectionError: # Simplified error detail for backend
        try:
            socket.gethostbyname(hostname)
            result_data['Details'] = "Connection Error (Host resolved, connection failed)"
        except socket.gaierror:
             result_data['Details'] = "DNS Resolution Error"
        except Exception:
             result_data['Details'] = "Connection Error (Unknown)" # Generic connection error
    except requests.exceptions.RequestException as e:
        result_data['Details'] = f"Request Error: {e}"
    except Exception as e:
        result_data['Details'] = f"Unexpected Error: {e}"
    # Removed console print
    return result_data

def test_tcp_port(hostname, port, timeout=TCP_TIMEOUT):
    """
    Tests if a specific TCP port is open on the target host using sockets.
    Returns a dictionary with test result details.
    """
    service_name = f'tcp:{port}'
    try:
        port_int = int(port)
        if not 0 < port_int < 65536: raise ValueError("Port number must be between 1 and 65535")
    except ValueError as e:
         # Return error result immediately
         return {'Timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S'), 'TargetHost': hostname,
                 'Service': service_name, 'Status': STATUS_FAILED,
                 'Details': f'Invalid port number specified: {e}', 'SuccessBool': False}

    result_data = {'Timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S'), 'TargetHost': hostname,
                   'Service': f'tcp:{port_int}', 'Status': STATUS_FAILED, 'Details': '', 'SuccessBool': False}
    sock = None
    try:
        ip_address = socket.gethostbyname(hostname)
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(timeout)
        result_code = sock.connect_ex((ip_address, port_int))
        if result_code == 0:
            result_data.update({'Status': STATUS_SUCCESS, 'Details': f'Port {port_int} is open', 'SuccessBool': True})
        else:
            result_data['Details'] = f'Port {port_int} is closed or filtered (Error code: {result_code})'
    except socket.timeout:
        result_data['Details'] = f'Timeout connecting to port {port_int}'
    except socket.gaierror:
        result_data['Details'] = 'DNS Resolution Error'
    except OverflowError:
         result_data['Details'] = f'Invalid port number {port_int}'
    except Exception as e:
        result_data['Details'] = f"Error connecting to port {port_int}: {e}"
    finally:
        if sock: sock.close()
    # Removed console print
    return result_data


# --- Core Test Execution Logic ---
# (No changes needed from previous version)
def run_network_tests(targets):
    """
    Runs the actual network tests based on the target list.
    Takes a list of target dictionaries [{'host': '...', 'services': [...]}]
    Returns a list of result dictionaries (without 'SuccessBool').
    """
    all_results = []
    print(f"Backend processing {len(targets)} target(s)...") # Server-side log
    if not targets: return all_results

    for target in targets:
        host, services = target.get('host'), target.get('services', [])
        if not host or not services: continue
        print(f"Testing target: {host} for services: {services}") # Server log

        for service in services:
            result_data = None
            service_lower = service.lower()
            try:
                if service_lower == 'ping': result_data = test_ping(host)
                elif service_lower == 'http': result_data = test_http_https(host, service_type='http', timeout=REQUEST_TIMEOUT)
                elif service_lower == 'https': result_data = test_http_https(host, service_type='https', timeout=REQUEST_TIMEOUT)
                elif ':' in service_lower:
                    service_type, port_str = service_lower.split(':', 1)
                    if service_type == 'tcp': result_data = test_tcp_port(host, port_str, timeout=TCP_TIMEOUT)
                    else: details = f'Unsupported service type {service_type}'; result_data = {'Timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S'), 'TargetHost': host, 'Service': service, 'Status': STATUS_SKIPPED, 'Details': details}
                else: details = 'Unknown service type'; result_data = {'Timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S'), 'TargetHost': host, 'Service': service, 'Status': STATUS_SKIPPED, 'Details': details}
            except Exception as test_err:
                 print(f"Error during test '{service}' for host '{host}': {test_err}"); traceback.print_exc()
                 result_data = {'Timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S'), 'TargetHost': host, 'Service': service, 'Status': STATUS_FAILED, 'Details': f'Test execution error: {test_err}'}

            if result_data: result_data.pop('SuccessBool', None); all_results.append(result_data)
            # import time; time.sleep(0.05) # Optional delay

    print(f"Backend finished testing. Returning {len(all_results)} results.")
    return all_results


# --- Helper Function to Parse CSV Data from String ---
# (No changes needed from previous version)
def parse_csv_data(csv_string_data):
    """Parses CSV data from a string and returns a list of target dicts."""
    targets = []
    if not csv_string_data: return targets
    try:
        csvfile = io.StringIO(csv_string_data)
        valid_lines = filter(lambda row: row.strip() and not row.strip().startswith('#'), csvfile)
        reader = csv.reader(valid_lines)
        try: header = next(reader)
        except StopIteration: return targets
        if not header or len(header) < 2 or header[0].lower().strip() != 'hostname' or header[1].lower().strip() != 'services': raise ValueError("Invalid CSV header")
        for i, row in enumerate(reader):
             if len(row) >= 2:
                host, services_str = row[0].strip(), row[1].strip()
                if host and services_str:
                    services_list = [s.strip().lower() for s in services_str.split(',') if s.strip()]
                    if services_list: targets.append({'host': host, 'services': services_list})
    except ValueError as ve: raise ve
    except Exception as e: raise ValueError(f"Failed to parse CSV data: {e}")
    return targets

# --- Helper Function to Save Results to CSV ---
# (No changes needed from previous version)
def save_results_to_csv(results, filename):
    """Saves the results list of dicts to a CSV file on the server."""
    if not filename: return "No output filename provided."
    if not results: return "No results to save."
    base_filename = os.path.basename(filename)
    if not base_filename or base_filename != filename: return f"Error: Invalid output filename '{filename}'. Path components not allowed."
    try: os.makedirs(RESULTS_OUTPUT_DIR, exist_ok=True)
    except OSError as e: return f"Error: Could not create output directory '{RESULTS_OUTPUT_DIR}': {e}"
    full_path = os.path.join(RESULTS_OUTPUT_DIR, base_filename)
    print(f"Attempting to save results to server path: {full_path}")
    try:
        with open(full_path, mode='w', newline='', encoding='utf-8') as csvfile:
            writer = csv.DictWriter(csvfile, fieldnames=CSV_FIELDNAMES, extrasaction='ignore')
            writer.writeheader()
            writer.writerows(results)
        return f"Successfully saved results to '{base_filename}' on the server."
    except IOError as e: return f"Error: Could not write results to file '{base_filename}' on server: {e}"
    except Exception as e: print(f"Unexpected error saving CSV to {full_path}: {e}"); traceback.print_exc(); return f"Error: Unexpected error saving results file '{base_filename}' on server."


# --- Flask App Setup ---
app = Flask(__name__)
CORS(app) # Enable CORS

# --- API Endpoint for Testing ---
# (No changes needed from previous version)
@app.route('/test', methods=['POST'])
def handle_test_request():
    """Handles POST requests to run network tests."""
    print(f"[{datetime.now()}] Received request on /test")
    targets_to_test = []
    output_filename = None
    file_save_status = None
    try:
        data = request.get_json()
        if not data: return jsonify({"error": "Invalid or empty JSON payload"}), 400
        output_filename = data.get('output_filename')

        if 'csv_data' in data:
            print("Processing CSV data from request...")
            try: targets_to_test = parse_csv_data(data['csv_data'])
            except ValueError as e: return jsonify({"error": f"CSV Parsing Error: {e}"}), 400
        elif 'host' in data and 'services' in data:
             print("Processing single host data from request...")
             host, services = data.get('host'), data.get('services')
             if isinstance(host, str) and isinstance(services, list) and host and services: targets_to_test.append({'host': host, 'services': services})
             else: return jsonify({"error": "Invalid 'host' or 'services' format"}), 400
        else: return jsonify({"error": "Missing 'csv_data' or 'host'/'services' pair"}), 400

        if not targets_to_test: results = []
        else: results = run_network_tests(targets_to_test)

        if output_filename:
            file_save_status = save_results_to_csv(results, output_filename)
            print(f"File save status: {file_save_status}")

        response_payload = {"results": results, "file_save_status": file_save_status}
        return jsonify(response_payload)

    except Exception as e:
        print(f"Error processing /test request: {e}"); traceback.print_exc()
        return jsonify({"error": "An internal server error occurred."}), 500

# --- Run the Flask App ---
# (No changes needed from previous version)
if __name__ == '__main__':
    missing_deps = []
    try: import requests
    except ImportError: missing_deps.append('requests')
    try: import colorama
    except ImportError: missing_deps.append('colorama')
    if missing_deps: print(f"Error: Missing required Python libraries: {', '.join(missing_deps)}\nPlease install them using: pip install {' '.join(missing_deps)}")
    print("Starting Flask backend server with CORS enabled...")
    print(f"Results directory configured: '{os.path.abspath(RESULTS_OUTPUT_DIR)}'")
    try: os.makedirs(RESULTS_OUTPUT_DIR, exist_ok=True)
    except OSError as e: print(f"Warning: Could not create results directory '{RESULTS_OUTPUT_DIR}': {e}")
    app.run(host='127.0.0.1', port=5000, debug=True)

