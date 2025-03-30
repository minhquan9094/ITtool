
# How to Use the DNS Lookup Scripts

These scripts allow you to perform forward (hostname -> IP) and reverse (IP -> hostname) DNS lookups for a list of inputs. You can optionally provide a specific DNS server IP address for the lookups and save the results to a CSV file.

## Python Script (`dns_lookup_to_csv_cli.py`)

This script uses the `dnspython` library and accepts command-line arguments for configuration.

**1. Prerequisite:**

* You need Python 3 installed.
* You must install the `dnspython` library. Open your terminal or command prompt and run:
    ```bash
    pip install dnspython
    ```

**2. Saving the Script:**

* Save the final Python code (provided in the previous response) as `dns_lookup_to_csv_cli.py`.

**3. Running the Script:**

* Open your terminal or command prompt.
* Navigate to the directory where you saved the script.
* Run the script using `python dns_lookup_to_csv_cli.py` followed by optional arguments.

**4. Command-Line Arguments:**

| Argument                | Short | Description                                                                                 | Default                         |
| :---------------------- | :---- | :------------------------------------------------------------------------------------------ | :------------------------------ |
| `--input-file FILE`     | `-i`  | Path to a text file with one IP/hostname per line. Overrides internal default list.       | Uses internal default list      |
| `--dns-server IP`       | `-d`  | IP address of the custom DNS server to use. If omitted, uses system default resolver.       | System default DNS              |
| `--output-dir DIR`      | `-o`  | Directory to save the output CSV file.                                                      | Current directory (`.`)         |
| `--timeout SECONDS`     | `-t`  | DNS query timeout in seconds.                                                               | `2.0`                           |
| `--help`                | `-h`  | Show the help message listing all arguments and exit.                                       | N/A                             |

**5. Examples:**

* **Use system default DNS and internal list:**
    ```bash
    python dns_lookup_to_csv_cli.py
    ```
* **Use a custom DNS server (e.g., 1.1.1.1) and internal list:**
    ```bash
    python dns_lookup_to_csv_cli.py --dns-server 1.1.1.1
    ```
    *or*
    ```bash
    python dns_lookup_to_csv_cli.py -d 1.1.1.1
    ```
* **Use an input file and Google's DNS (8.8.8.8), save to a specific directory:**
    ```bash
    python dns_lookup_to_csv_cli.py -i my_hosts.txt -d 8.8.8.8 -o ./results
    ```
* **Use an input file and system default DNS:**
    ```bash
    python dns_lookup_to_csv_cli.py -i my_hosts.txt
    ```

**6. Output:**

* The script prints progress to the console.
* A CSV file named `dns_lookup_results_YYYYMMDD_HHMMSS.csv` is created in the specified output directory (or current directory by default).
* The CSV file contains the columns: `Input`, `LookupType`, `Result`, `Status`, `ErrorMessage`, `DnsServerUsed`.

---

## PowerShell Script (`DnsLookupToCsvCustomDns.ps1`)

This script uses the built-in `Resolve-DnsName` cmdlet and accepts parameters for configuration.

**1. Prerequisite:**

* Requires PowerShell version 3.0 or higher (standard on modern Windows).

**2. Saving the Script:**

* Save the final PowerShell code (provided in the previous responses) as `DnsLookupToCsvCustomDns.ps1`.

**3. Running the Script:**

* Open PowerShell.
* Navigate (`cd`) to the directory where you saved the script.
* **Execution Policy:** You might need to adjust your PowerShell execution policy. To allow the script to run just for the current session, you can use:
    ```powershell
    Set-ExecutionPolicy -ExecutionPolicy Bypass -Scope Process
    ```
* Run the script using `.\DnsLookupToCsvCustomDns.ps1` followed by optional parameters.

**4. Parameters:**

| Parameter             | Description                                                                                 | Default                         |
| :-------------------- | :------------------------------------------------------------------------------------------ | :------------------------------ |
| `-InputListFilePath`  | Path to a text file with one IP/hostname per line. Overrides internal default list.       | Uses internal default list      |
| `-CustomDnsServer`    | IP address of the custom DNS server to use. If omitted, uses system default resolver.       | System default DNS              |
| `-OutputDirectory`    | Directory to save the output CSV file.                                                      | Current directory (`.`)         |
| `-Help`               | Show the help message listing all parameters and exit.                                      | N/A                             |

**5. Examples:**

* **Use system default DNS and internal list:**
    ```powershell
    .\DnsLookupToCsvCustomDns.ps1
    ```
* **Use a custom DNS server (e.g., 1.1.1.1) and internal list:**
    ```powershell
    .\DnsLookupToCsvCustomDns.ps1 -CustomDnsServer "1.1.1.1"
    ```
* **Use an input file and Google's DNS (8.8.8.8), save to a specific directory:**
    ```powershell
    .\DnsLookupToCsvCustomDns.ps1 -InputListFilePath "my_hosts.txt" -CustomDnsServer "8.8.8.8" -OutputDirectory "C:\Temp\Results"
    ```
* **Use an input file and system default DNS:**
    ```powershell
    .\DnsLookupToCsvCustomDns.ps1 -InputListFilePath ".\my_hosts.txt"
    ```
* **Get detailed help:**
    ```powershell
    Get-Help .\DnsLookupToCsvCustomDns.ps1 -Full
    ```

**6. Output:**

* The script prints progress to the PowerShell console.
* A CSV file named `dns_lookup_results_yyyyMMdd_HHmmss.csv` is created in the specified output directory (or current directory by default).
* The CSV file contains columns based on the custom object properties: `Input`, `LookupType`, `Result`, `Status`, `ErrorMessage`, `DnsServerUsed`.
