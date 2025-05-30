#!/bin/bash
# DHCP test script that runs inside the container

set -e

echo "=== DHCP Client Timeout Test ==="

# Function to check DHCP timeout
check_dhcp_timeout() {
    local timeout_value=0
    local config_file=""
    
    # Check dhclient.conf
    if [ -f /host/etc/dhcp/dhclient.conf ]; then
        config_file="/host/etc/dhcp/dhclient.conf"
        timeout_value=$(grep -E "^\s*timeout" "$config_file" | awk '{print $2}' | tr -d ';' | head -1)
        echo "Found dhclient.conf timeout: ${timeout_value:-not set}"
    fi
    
    # Check dhcpcd.conf
    if [ -f /host/etc/dhcpcd.conf ]; then
        config_file="/host/etc/dhcpcd.conf"
        local dhcpcd_timeout=$(grep -E "^\s*timeout" "$config_file" | awk '{print $2}' | head -1)
        if [ -n "$dhcpcd_timeout" ]; then
            timeout_value="$dhcpcd_timeout"
            echo "Found dhcpcd.conf timeout: $timeout_value"
        fi
    fi
    
    # Check systemd-networkd
    if [ -d /host/etc/systemd/network ]; then
        for file in /host/etc/systemd/network/*.network; do
            if [ -f "$file" ]; then
                local networkd_timeout=$(grep -i "DHCPv4.*Timeout" "$file" | cut -d= -f2 | tr -d 's' | head -1)
                if [ -n "$networkd_timeout" ]; then
                    timeout_value="$networkd_timeout"
                    echo "Found systemd-networkd timeout in $file: $timeout_value"
                    break
                fi
            fi
        done
    fi
    
    # Default for Azure VMs
    if [ -z "$timeout_value" ] || [ "$timeout_value" = "0" ]; then
        if grep -q "Microsoft\|Azure" /host/etc/waagent.conf 2>/dev/null; then
            echo "Azure VM detected, using default timeout of 300s"
            timeout_value=300
        else
            echo "No explicit timeout found, using system default"
            timeout_value=60
        fi
    fi
    
    # Validate timeout
    if [ "$timeout_value" -ge 300 ]; then
        echo "✓ PASS: DHCP timeout ($timeout_value seconds) meets requirement (>= 300s)"
        return 0
    else
        echo "✗ FAIL: DHCP timeout ($timeout_value seconds) is less than required 300s"
        return 1
    fi
}

# Run the test
check_dhcp_timeout