#!/usr/bin/env python3
# -*- coding: utf-8 -*-

# --- Flask Backend with CSV Input/Output Support ---
# Purpose: Listens for requests, runs tests based on single target OR CSV data,
#          optionally saves results to file on server, returns results via API.

# --- Prerequisites ---
# pip install Flask Flask-CORS requests colorama

import os
import sys
import io # Required for StringIO
import csv # Required for CSV parsing/writing
from flask import Flask, request, jsonify
from flask_cors import CORS
from datetime import datetime
import traceback # For error logging

# --- Configuration ---
# Define a safe directory on the SERVER where results can be saved
# IMPORTANT: Ensure this directory exists and the server process has write permissions!
# Avoid using paths derived directly from user input for security.
RESULTS_OUTPUT_DIR = "./test_results" # Save in a sub-directory relative to app.py

# --- Placeholder for your actual testing logic ---
# You MUST integrate your real test_ping, test_http_https, test_tcp_port functions here.
# They need to RETURN a result dictionary.

# Assume these constants are defined (or imported)
STATUS_SUCCESS = "SUCCESS"
STATUS_FAILED = "FAILED"
STATUS_SKIPPED = "SKIPPED"
CSV_FIELDNAMES = ['Timestamp', 'TargetHost', 'Service', 'Status', 'Details'] # For CSV export

# Placeholder: Replace with calls to your actual test functions
def run_network_tests(targets):
    """
    Placeholder function to simulate running tests.
    Takes a list of target dictionaries [{'host': '...', 'services': [...]}]
    Returns a list of result dictionaries.
    """
    all_results = []
    print(f"Backend received targets: {targets}") # Server-side log
    if not targets:
        return all_results

    for target in targets:
        host = target.get('host')
        services = target.get('services', [])
        if not host or not services:
            print(f"Skipping invalid target entry: {target}")
            continue

        for service in services:
            # *** Replace this section with actual calls to your test functions ***
            # Example:
            # if service == 'ping': result = test_ping(host)
            # elif service == 'https': result = test_http_https(host, 'https')
            # elif service.startswith('tcp:'): result = test_tcp_port(host, service.split(':')[1])
            # else: ... create skipped result ...
            # *** End of replacement section ***

            # Dummy result generation:
            status = STATUS_SUCCESS if hash(host + service) % 3 != 0 else STATUS_FAILED # Simulate
            details = f"{status} simulated for {service} on {host}"
            if status == STATUS_FAILED: details += " (simulated error)"

            result_data = {
                'Timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                'TargetHost': host,
                'Service': service,
                'Status': status,
                'Details': details
                # 'SuccessBool' is not needed here
            }
            all_results.append(result_data)
            # import time
            # time.sleep(0.05) # Small delay

    print(f"Backend sending results: {len(all_results)} items") # Server-side log
    return all_results

# --- Helper Function to Parse CSV Data from String ---
def parse_csv_data(csv_string_data):
    """Parses CSV data from a string and returns a list of target dicts."""
    targets = []
    if not csv_string_data:
        return targets

    try:
        # Use io.StringIO to treat the string as a file
        csvfile = io.StringIO(csv_string_data)
        # Skip potential empty lines or comment lines before header
        valid_lines = filter(lambda row: row.strip() and not row.strip().startswith('#'), csvfile)
        reader = csv.reader(valid_lines)

        try:
            header = next(reader)
        except StopIteration:
             print(f"{STATUS_WARNING}: CSV data is empty or only contains comments.")
             return targets # Return empty list

        # Basic header validation
        if not header or len(header) < 2 or header[0].lower().strip() != 'hostname' or header[1].lower().strip() != 'services':
             print(f"{STATUS_ERROR}: Invalid CSV header in data. Expected 'hostname,services', got '{','.join(header)}'")
             # Optionally raise an error or return empty list
             raise ValueError("Invalid CSV header") # Raise error to signal problem

        # Process data rows
        for i, row in enumerate(reader):
             if len(row) >= 2:
                host = row[0].strip()
                services_str = row[1].strip()
                if host and services_str:
                    services_list = [s.strip().lower() for s in services_str.split(',') if s.strip()]
                    if services_list:
                        targets.append({'host': host, 'services': services_list})
                    else:
                        print(f"{STATUS_WARNING}: Skipping row {i+2} in CSV data - No valid services found for host '{host}'.")
                elif host:
                    print(f"{STATUS_WARNING}: Skipping row {i+2} in CSV data - Services column empty for host '{host}'.")
             elif row and row[0].strip():
                 print(f"{STATUS_WARNING}: Skipping row {i+2} in CSV data - Missing services column for host '{row[0].strip()}'.")

    except ValueError as ve: # Catch header error
         raise ve # Re-raise to be caught by endpoint handler
    except Exception as e:
        print(f"Error parsing CSV string data: {e}")
        traceback.print_exc()
        raise ValueError(f"Failed to parse CSV data: {e}") # Raise error

    return targets

# --- Helper Function to Save Results to CSV ---
def save_results_to_csv(results, filename):
    """Saves the results list of dicts to a CSV file on the server."""
    if not filename:
        return "No output filename provided."
    if not results:
        return "No results to save."

    # **Security:** Basic filename sanitization (prevent path traversal)
    base_filename = os.path.basename(filename)
    # Optional: further restrict allowed characters if needed
    if not base_filename or base_filename != filename:
         return f"Error: Invalid output filename '{filename}'. Path components not allowed."

    # Ensure the output directory exists
    try:
        os.makedirs(RESULTS_OUTPUT_DIR, exist_ok=True)
    except OSError as e:
        return f"Error: Could not create output directory '{RESULTS_OUTPUT_DIR}': {e}"

    # Construct full path safely
    full_path = os.path.join(RESULTS_OUTPUT_DIR, base_filename)
    print(f"Attempting to save results to server path: {full_path}")

    try:
        with open(full_path, mode='w', newline='', encoding='utf-8') as csvfile:
            # Use fieldnames defined globally or pass them
            writer = csv.DictWriter(csvfile, fieldnames=CSV_FIELDNAMES, extrasaction='ignore')
            writer.writeheader()
            writer.writerows(results)
        return f"Successfully saved results to '{base_filename}' on the server."
    except IOError as e:
        print(f"Error writing CSV to {full_path}: {e}")
        return f"Error: Could not write results to file '{base_filename}' on server: {e}"
    except Exception as e:
        print(f"Unexpected error saving CSV to {full_path}: {e}")
        traceback.print_exc()
        return f"Error: Unexpected error saving results file '{base_filename}' on server."


# --- Flask App Setup ---
app = Flask(__name__)
CORS(app) # Enable CORS for all origins

# --- API Endpoint for Testing ---
@app.route('/test', methods=['POST'])
def handle_test_request():
    """Handles POST requests to run network tests."""
    print(f"[{datetime.now()}] Received request on /test")
    targets_to_test = []
    output_filename = None
    file_save_status = None # Status message about saving file

    try:
        data = request.get_json()
        if not data:
            return jsonify({"error": "Invalid or empty JSON payload"}), 400

        output_filename = data.get('output_filename') # Get optional output filename

        # --- Determine Input Method and Extract Targets ---
        if 'csv_data' in data:
            print("Processing CSV data from request...")
            try:
                targets_to_test = parse_csv_data(data['csv_data'])
            except ValueError as e: # Catch parsing errors (e.g., bad header)
                 return jsonify({"error": f"CSV Parsing Error: {e}"}), 400
        elif 'host' in data and 'services' in data:
             print("Processing single host data from request...")
             host = data.get('host')
             services = data.get('services')
             if isinstance(host, str) and isinstance(services, list) and host and services:
                 targets_to_test.append({'host': host, 'services': services})
             else:
                 return jsonify({"error": "Invalid 'host' or 'services' format for single target"}), 400
        # Add elif for 'csv_filename' if implementing server-side file access
        else:
            return jsonify({"error": "Missing 'csv_data' or 'host'/'services' pair in request"}), 400

        # --- Run Tests ---
        if not targets_to_test:
             print("No valid targets to test after parsing.")
             # Return empty results list? Or an error? Let's return empty results.
             results = []
        else:
             results = run_network_tests(targets_to_test) # Use actual test logic here

        # --- Save Results to File (if requested) ---
        if output_filename:
            file_save_status = save_results_to_csv(results, output_filename)
            print(f"File save status: {file_save_status}") # Log status on server

        # --- Return Results (and file save status) ---
        response_payload = {
            "results": results,
            "file_save_status": file_save_status # Will be null if filename wasn't provided
        }
        return jsonify(response_payload)

    except Exception as e:
        print(f"Error processing /test request: {e}")
        traceback.print_exc()
        return jsonify({"error": "An internal server error occurred."}), 500

# --- Run the Flask App ---
if __name__ == '__main__':
    # Basic check for dependencies needed by backend/tests
    missing_deps = []
    try: import requests
    except ImportError: missing_deps.append('requests')
    try: import colorama # Needed if test functions use it internally
    except ImportError: missing_deps.append('colorama')

    if missing_deps:
        print(f"Error: Missing required Python libraries for testing: {', '.join(missing_deps)}")
        print(f"Please install them using: pip install {' '.join(missing_deps)}")
        # sys.exit(1) # Don't exit, Flask might still run but tests will fail

    print("Starting Flask backend server with CORS enabled...")
    print(f"Results directory configured: '{os.path.abspath(RESULTS_OUTPUT_DIR)}'")
    # Ensure results directory exists on startup
    try:
        os.makedirs(RESULTS_OUTPUT_DIR, exist_ok=True)
    except OSError as e:
        print(f"Warning: Could not create results directory '{RESULTS_OUTPUT_DIR}': {e}")

    app.run(host='127.0.0.1', port=5000, debug=True)

