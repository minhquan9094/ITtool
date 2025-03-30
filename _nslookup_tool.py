import ipaddress
import sys
import csv
import datetime
import argparse # Module for command-line arguments
import os

# --- Required 3rd Party Library ---
try:
    import dns.resolver
    import dns.reversename
    import dns.exception
except ImportError:
    print("Error: 'dnspython' library not found.")
    print("Please install it using: pip install dnspython")
    sys.exit(1)
# --- End Required Library ---

# --- Default Configuration (Used if not overridden by CLI args) ---
DEFAULT_INPUT_LIST = [
    "google.com",
    "8.8.8.8",
    "192.168.1.1", # Resolution depends heavily on the DNS server used
    "github.com",
    "1.1.1.1",
    "cloudflare.com",
    "nonexistentdomain.local",
    "10.0.0.50"
]
DEFAULT_OUTPUT_DIR = "." # Current directory
# --- End Default Configuration ---

# --- Command Line Argument Parsing ---
parser = argparse.ArgumentParser(
    description="Perform DNS lookups for a list of inputs (hostnames/IPs) and save results to CSV.",
    formatter_class=argparse.ArgumentDefaultsHelpFormatter # Show defaults in help message
    )
parser.add_argument(
    "-i", "--input-file",
    help="Path to a text file containing one IP or hostname per line. Overrides the default internal list.",
    metavar="FILE"
    )
parser.add_argument(
    "-d", "--dns-server",
    help="Optional: IP address of the custom DNS server to use. If omitted, uses system default.",
    metavar="IP_ADDRESS"
    )
parser.add_argument(
    "-o", "--output-dir",
    default=DEFAULT_OUTPUT_DIR,
    help="Directory where the output CSV file will be saved.",
    metavar="DIRECTORY"
    )
parser.add_argument(
    "-t", "--timeout",
    type=float, default=2.0,
    help="DNS query timeout in seconds.",
    metavar="SECONDS"
    )

args = parser.parse_args()
# --- End Argument Parsing ---


# --- Determine Input List ---
input_list = []
if args.input_file:
    try:
        with open(args.input_file, 'r') as f:
            input_list = [line.strip() for line in f if line.strip()]
        print(f"Reading input list from file: {args.input_file}")
    except FileNotFoundError:
        print(f"Error: Input file '{args.input_file}' not found.")
        sys.exit(1)
    except IOError as e:
         print(f"Error reading input file '{args.input_file}': {e}")
         sys.exit(1)
else:
    print("Using the default internal input list.")
    input_list = DEFAULT_INPUT_LIST

if not input_list:
     print("Error: Input list is empty.")
     sys.exit(1)
# --- End Determine Input List ---


# --- Prepare Output Path ---
output_dir = args.output_dir
if not os.path.isdir(output_dir):
    try:
        print(f"Output directory '{output_dir}' does not exist. Creating it...")
        os.makedirs(output_dir, exist_ok=True)
    except OSError as e:
        print(f"Error: Could not create output directory '{output_dir}': {e}")
        sys.exit(1)

timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
output_csv_file = os.path.join(output_dir, f'dns_lookup_results_{timestamp}.csv')
# --- End Prepare Output Path ---


# --- Setup DNS Resolver based on input ---
resolver = dns.resolver.Resolver()
custom_dns_server = args.dns_server # Get from command line argument
dns_server_display = "System Default"

if custom_dns_server and custom_dns_server.strip():
    # Basic validation if it looks like an IP
    try:
        ipaddress.ip_address(custom_dns_server.strip()) # Validate format
        resolver.nameservers = [custom_dns_server.strip()]
        dns_server_display = resolver.nameservers[0]
        print(f"Using custom DNS server: {dns_server_display}")
    except ValueError:
         print(f"Warning: Invalid IP format for --dns-server '{custom_dns_server}'. Using system default.")
         custom_dns_server = None # Fallback
         dns_server_display = "System Default (Invalid Input)"

if not custom_dns_server: # If None or fallback occurred
    try:
         default_servers = dns.resolver.get_default_resolver().nameservers
         if default_servers:
             resolver.nameservers = default_servers
             dns_server_display = "; ".join(resolver.nameservers) # Can be multiple
             print(f"Using system default DNS server(s): {dns_server_display}")
         else:
              print("Warning: Could not determine system default DNS servers. Relying on resolver defaults.")
              dns_server_display = "System Default (Unknown)"
    except Exception as e:
         print(f"Warning: Could not determine system default DNS servers: {e}. Relying on resolver defaults.")
         dns_server_display = "System Default (Error)"

# Apply timeout from arguments
resolver.timeout = args.timeout
resolver.lifetime = args.timeout * 2 # Allow slightly longer overall lifetime
# --- End Setup DNS Resolver ---


print(f"Starting DNS lookups... Output will be saved to '{output_csv_file}'")

# Prepare data for CSV
csv_data = []
csv_header = ['Input', 'LookupType', 'Result', 'Status', 'ErrorMessage', 'DnsServerUsed']

# --- Main Lookup Loop ---
for item in input_list:
    # (The lookup logic inside the loop remains the same as the previous Python script)
    # ... [Lookup logic as in dns_lookup_to_csv_custom_dns.py] ...

    print(f"Processing: {item}")
    lookup_type = "Unknown"
    result_value = ""
    status = "FAILED"
    error_message = ""
    # Use the display string determined earlier
    dns_server_used_for_row = dns_server_display

    is_ip = False
    try:
        ip_obj = ipaddress.ip_address(item)
        is_ip = True
        if ip_obj.is_loopback or ip_obj.is_private:
             print(f"  ℹ️  Info: Input '{item}' is a loopback/private IP.")
    except ValueError:
        is_ip = False

    if is_ip:
        lookup_type = "Reverse (IP -> Hostname)"
        try:
            reversed_name = dns.reversename.from_address(item)
            answers = resolver.resolve(reversed_name, 'PTR')
            hostnames = [str(rdata.target).rstrip('.') for rdata in answers] # Clean trailing dot
            result_value = "; ".join(hostnames)
            status = "SUCCESS"
            print(f"  ✅ SUCCESS: IP: {item} -> Hostname(s): {result_value}")
        except dns.resolver.NXDOMAIN:
            error_message = "NXDOMAIN (No such domain for reverse lookup)"
            result_value = "Not Found"
            print(f"  ❌ FAILED (Reverse - NXDOMAIN): IP: {item} -> {error_message}")
        except dns.resolver.NoAnswer:
             error_message = "NoAnswer (Record type PTR does not exist at this name)"
             result_value = "Not Found (No PTR Record)"
             print(f"  ❌ FAILED (Reverse - NoAnswer): IP: {item} -> {error_message}")
        except dns.exception.Timeout:
            error_message = f"Timeout querying DNS server ({dns_server_display})"
            result_value = "Timeout"
            print(f"  ❌ FAILED (Reverse - Timeout): IP: {item} -> {error_message}")
        except dns.resolver.NoNameservers as e:
             error_message = f"No nameservers available: {e}"
             result_value = "Configuration Error"
             status="ERROR"
             print(f"  ❌ ERROR (Reverse - NoNameservers): IP: {item} -> {error_message}")
        except Exception as e:
            error_message = f"Unexpected error: {type(e).__name__} - {e}"
            result_value = "Error"
            status = "ERROR"
            print(f"  ❌ ERROR (Reverse - Other): IP: {item} -> {error_message}")

    else: # Hostname
        lookup_type = "Forward (Hostname -> IP)"
        try:
            # Prefer A records (IPv4), but could query 'AAAA' for IPv6
            answers = resolver.resolve(item, 'A')
            ips = [rdata.address for rdata in answers]
            result_value = "; ".join(ips)
            status = "SUCCESS"
            print(f"  ✅ SUCCESS: Hostname: {item} -> IP(s): {result_value}")
        except dns.resolver.NXDOMAIN:
            error_message = "NXDOMAIN (No such domain)"
            result_value = "Not Found"
            print(f"  ❌ FAILED (Forward - NXDOMAIN): Hostname: {item} -> {error_message}")
        except dns.resolver.NoAnswer:
             error_message = "NoAnswer (Record type A does not exist at this name, but domain exists)"
             result_value = "Not Found (No A Record)"
             print(f"  ❌ FAILED (Forward - NoAnswer): Hostname: {item} -> {error_message}")
        except dns.exception.Timeout:
            error_message = f"Timeout querying DNS server ({dns_server_display})"
            result_value = "Timeout"
            print(f"  ❌ FAILED (Forward - Timeout): Hostname: {item} -> {error_message}")
        except dns.resolver.NoNameservers as e:
             error_message = f"No nameservers available: {e}"
             result_value = "Configuration Error"
             status="ERROR"
             print(f"  ❌ ERROR (Forward - NoNameservers): Hostname: {item} -> {error_message}")
        except Exception as e:
            error_message = f"Unexpected error: {type(e).__name__} - {e}"
            result_value = "Error"
            status = "ERROR"
            print(f"  ❌ ERROR (Forward - Other): Hostname: {item} -> {error_message}")

    # Append row data for CSV
    csv_data.append([item, lookup_type, result_value, status, error_message, dns_server_used_for_row])
    print("-" * 20)
# --- End Main Lookup Loop ---


# Write data to CSV file
try:
    with open(output_csv_file, 'w', newline='', encoding='utf-8') as csvfile:
        writer = csv.writer(csvfile)
        writer.writerow(csv_header) # Write header
        writer.writerows(csv_data) # Write all data rows
    print(f"\nSuccessfully wrote results to '{output_csv_file}'")
except IOError as e:
    print(f"\nError writing to CSV file '{output_csv_file}': {e}")
except Exception as e:
     print(f"\nAn unexpected error occurred during CSV writing: {e}")

print("\nDNS lookups complete.")