#Requires -Version 3.0

<#
.SYNOPSIS
Performs DNS lookups (forward and reverse) for a list of inputs and outputs to a CSV file.
Allows specifying a custom DNS server.

.DESCRIPTION
Reads a list of hostnames or IP addresses, attempts to resolve them using either the system's
default DNS or a specified custom DNS server, and saves the results to a timestamped CSV file.

.PARAMETER InputListFilePath
Optional. Path to a text file containing one IP address or hostname per line.
If not provided, uses the hardcoded list within the script.

.PARAMETER CustomDnsServer
Optional. The IP address of the DNS server to use for lookups.
If not provided or empty, the system's default DNS resolver is used. Examples: "1.1.1.1", "8.8.8.8".

.PARAMETER OutputDirectory
Optional. The directory where the output CSV file will be saved. Defaults to the script's current directory.

.EXAMPLE
.\DnsLookupToCsvCustomDns.ps1 -CustomDnsServer "1.1.1.1"
Runs the script using the hardcoded input list and Cloudflare's DNS server (1.1.1.1).

.EXAMPLE
.\DnsLookupToCsvCustomDns.ps1 -InputListFilePath ".\my_devices.txt" -OutputDirectory "C:\temp\lookups"
Runs the script using inputs from 'my_devices.txt', using the system default DNS, and saves the CSV to C:\temp\lookups.

.EXAMPLE
.\DnsLookupToCsvCustomDns.ps1
Runs the script using the hardcoded list and system default DNS, saving the CSV in the current directory.
#>
param(
    [string]$InputListFilePath,

    [string]$CustomDnsServer,

    [string]$OutputDirectory = "." # Default to current directory
)

# --- Configuration ---
# Hardcoded list (used if InputListFilePath is not provided)
[string[]]$DefaultInputList = @(
    "google.com",
    "8.8.8.8",
    "192.168.1.1", # Resolution depends heavily on the DNS server used
    "github.com",
    "1.1.1.1",
    "cloudflare.com",
    "nonexistentdomain.local",
    "10.0.0.50"
)

# --- Determine Input Source ---
[string[]]$InputList
if (-not [string]::IsNullOrWhiteSpace($InputListFilePath)) {
    $resolvedPath = $ExecutionContext.SessionState.Path.GetUnresolvedProviderPathFromPSPath($InputListFilePath)
    if (Test-Path -Path $resolvedPath -PathType Leaf) {
        Write-Verbose "Reading input list from file: $resolvedPath"
        try {
            $InputList = Get-Content -Path $resolvedPath -ErrorAction Stop | Where-Object { $_.Trim() -ne '' }
        }
        catch {
            Write-Error "Error reading input file '$resolvedPath': $($_.Exception.Message)"
            exit 1
        }
    } else {
         Write-Error "Input file not found: $resolvedPath"
         exit 1
    }
} else {
    Write-Verbose "Using hardcoded input list."
    $InputList = $DefaultInputList
}

# --- Determine Output Path ---
$resolvedOutputDir = $ExecutionContext.SessionState.Path.GetUnresolvedProviderPathFromPSPath($OutputDirectory)
if (-not (Test-Path -Path $resolvedOutputDir -PathType Container)) {
    Write-Warning "Output directory '$resolvedOutputDir' does not exist. Attempting to create it."
    try {
        $null = New-Item -Path $resolvedOutputDir -ItemType Directory -Force -ErrorAction Stop
        Write-Verbose "Created output directory: $resolvedOutputDir"
    } catch {
         Write-Error "Failed to create output directory '$resolvedOutputDir': $($_.Exception.Message)"
         exit 1
    }
}
$timestamp = Get-Date -Format "yyyyMMdd_HHmmss"
$outputCsvFile = Join-Path -Path $resolvedOutputDir -ChildPath "dns_lookup_results_$($timestamp).csv"

# --- Determine DNS Server to Use ---
$dnsServerToUse = $null
$dnsServerDisplay = "System Default"
if (-not [string]::IsNullOrWhiteSpace($CustomDnsServer)) {
    # Basic validation if it looks like an IP
    if ($CustomDnsServer -match '^\d{1,3}(\.\d{1,3}){3}$') {
        $dnsServerToUse = $CustomDnsServer.Trim()
        $dnsServerDisplay = $dnsServerToUse
        Write-Host "Using custom DNS server: $dnsServerToUse" -ForegroundColor Cyan
    } else {
        Write-Warning "Invalid format for CustomDnsServer: '$CustomDnsServer'. Expected an IPv4 address. Falling back to system default."
    }
} else {
     Write-Host "Using system default DNS server(s)." -ForegroundColor Cyan
}


# --- Start Processing ---
Write-Host "Starting DNS lookups... Output will be saved to '$outputCsvFile'" -ForegroundColor Yellow
Write-Host ""

# Array to hold result objects
$resultsCollection = @()

foreach ($item in $InputList) {
    Write-Host "Processing: $item"

    # Default values
    $lookupType = "Unknown"
    $resultValue = ""
    $status = "FAILED"
    $errorMessage = ""
    $isIP = $item -match '^\d{1,3}(\.\d{1,3}){3}$'

    if ($isIP) { $lookupType = "Reverse (IP -> Hostname)" } else { $lookupType = "Forward (Hostname -> IP)"}

    # Prepare parameters for Resolve-DnsName using splatting
    $resolveParams = @{
        Name     = $item
        DnsOnly  = $true # Avoid LLMNR/NetBIOS
        ErrorAction = 'Stop' # Ensure errors are caught by 'catch'
        # Add Type preference if needed, e.g. -Type A,AAAA,PTR but auto often works
    }
    # Add custom DNS server if specified
    if ($dnsServerToUse) {
        $resolveParams.Server = $dnsServerToUse
    }

    try {
        # Execute lookup
        Write-Verbose "Executing: Resolve-DnsName @resolveParams"
        $dnsResult = Resolve-DnsName @resolveParams

        if ($dnsResult) {
             $firstResultType = $dnsResult[0].Type
             if ($firstResultType -eq 'PTR') {
                 $lookupType = "Reverse (IP -> Hostname)" # Correct based on result
                 $resultValue = ($dnsResult | Where-Object { $_.Type -eq 'PTR' }).NameHost -join '; '
                 $status = "SUCCESS"
                 Write-Host "  `u{2705} SUCCESS (Reverse): IP [$item] -> Hostname(s): [$resultValue]" -ForegroundColor Green
             } elseif ($firstResultType -eq 'A' -or $firstResultType -eq 'AAAA') {
                 $lookupType = "Forward (Hostname -> IP)" # Correct based on result
                 $resultValue = ($dnsResult | Where-Object { $_.Type -eq 'A' -or $_.Type -eq 'AAAA' }).IPAddress -join '; '
                 $status = "SUCCESS"
                 Write-Host "  `u{2705} SUCCESS (Forward): Hostname [$item] -> IP(s): [$resultValue]" -ForegroundColor Green
             } else {
                 $lookupType = "Other ($($firstResultType))"
                 $resultValue = "Resolved (Type: $($firstResultType))"
                 $status = "SUCCESS (Other Type)"
                 $errorMessage = "Resolved to type $($firstResultType), not standard A/AAAA/PTR."
                 Write-Warning "  `u{26A0} WARNING: Resolved '$item' to type '$firstResultType'."
             }
        } else {
             $errorMessage = "Resolve-DnsName returned no results without error."
             $resultValue = "No Results"
             Write-Warning "  `u{26A0} WARNING: No results for '$item'."
        }

    } catch [System.Management.Automation.CmdletInvocationException] {
        $errorMessage = $_.Exception.InnerException.Message -replace "`r?`n", " "
        $resultValue = "Resolution Failed"
        Write-Host "  `u{274C} FAILED: Could not resolve [$item] (Server: $dnsServerDisplay). Error: $errorMessage" -ForegroundColor Red
    } catch {
        $errorMessage = $_.Exception.Message -replace "`r?`n", " "
        $resultValue = "Script Error"
        $status = "ERROR"
        Write-Host "  `u{274C} ERROR: Unexpected error resolving [$item] (Server: $dnsServerDisplay). Error: $errorMessage" -ForegroundColor Red
    }

    # Add result object to collection
    $resultsCollection += [PSCustomObject]@{
        Input         = $item
        LookupType    = $lookupType
        Result        = $resultValue
        Status        = $status
        ErrorMessage  = $errorMessage
        DnsServerUsed = $dnsServerDisplay # Record which server setting was used
    }
     Write-Host ("-" * 20) # Separator
}

# Export the collected results to CSV
try {
    $resultsCollection | Export-Csv -Path $outputCsvFile -NoTypeInformation -Encoding UTF8 -ErrorAction Stop
    Write-Host "`nSuccessfully wrote results to '$outputCsvFile'" -ForegroundColor Green
} catch {
     Write-Error "Failed to write CSV file '$outputCsvFile': $($_.Exception.Message)"
}

Write-Host "`nDNS lookups complete." -ForegroundColor Yellow