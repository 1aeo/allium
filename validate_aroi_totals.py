#!/usr/bin/env python3
"""
Validate AROI operator totals against network totals
"""
import json
import sys

def main():
    # Load the processed data
    with open('allium/data.json', 'r') as f:
        data = json.load(f)
    
    # Get network totals
    network_totals = data.get('network_totals', {})
    total_network_relays = network_totals.get('total_relays', 0)
    total_guard_cw = network_totals.get('guard_consensus_weight', 0)
    total_middle_cw = network_totals.get('middle_consensus_weight', 0)
    total_exit_cw = network_totals.get('exit_consensus_weight', 0)
    total_network_cw = total_guard_cw + total_middle_cw + total_exit_cw
    
    # Calculate total network bandwidth
    total_network_bandwidth = 0
    for relay in data.get('relays', []):
        total_network_bandwidth += relay.get('observed_bandwidth', 0)
    
    print("=== NETWORK TOTALS ===")
    print(f"Total relays: {total_network_relays:,}")
    print(f"Total bandwidth: {total_network_bandwidth / (1024**3):.2f} GB/s")
    print(f"Total consensus weight: {total_network_cw}")
    print(f"  - Guard CW: {total_guard_cw}")
    print(f"  - Middle CW: {total_middle_cw}")
    print(f"  - Exit CW: {total_exit_cw}")
    
    # Get contact-based data
    contacts = data.get('sorted', {}).get('contact', {})
    print(f"\nTotal contact groups: {len(contacts)}")
    
    # Calculate AROI operator totals
    aroi_operators_with_contact = 0
    total_aroi_bandwidth = 0
    total_aroi_cw = 0
    total_aroi_relays = 0
    
    for contact_hash, contact_data in contacts.items():
        # Get contact info from first relay in this contact group
        relay_indices = contact_data.get('relays', [])
        if not relay_indices:
            continue
            
        first_relay = data['relays'][relay_indices[0]]
        contact_info = first_relay.get('contact', '')
        aroi_domain = first_relay.get('aroi_domain', 'none')
        
        # Skip operators without contact information (AROI requires contact info)
        if not contact_info or contact_info.strip() == '':
            continue
        if aroi_domain == 'none' and not contact_info:
            continue
            
        # This is a valid AROI operator
        aroi_operators_with_contact += 1
        total_aroi_bandwidth += contact_data.get('bandwidth', 0)
        total_aroi_cw += contact_data.get('consensus_weight_fraction', 0.0)
        total_aroi_relays += len(relay_indices)
    
    print("\n=== AROI TOTALS ===")
    print(f"AROI operators (with contact): {aroi_operators_with_contact:,}")
    print(f"AROI bandwidth: {total_aroi_bandwidth / (1024**3):.2f} GB/s")
    print(f"AROI consensus weight: {total_aroi_cw:.4f} ({total_aroi_cw * 100:.1f}%)")
    print(f"AROI relays: {total_aroi_relays:,}")
    
    print("\n=== COVERAGE ANALYSIS ===")
    print(f"AROI bandwidth coverage: {(total_aroi_bandwidth / total_network_bandwidth) * 100:.1f}%")
    print(f"AROI consensus weight coverage: {(total_aroi_cw / 1.0) * 100:.1f}%")
    print(f"AROI relay coverage: {(total_aroi_relays / total_network_relays) * 100:.1f}%")
    
    # Check for potential issues
    print("\n=== VALIDATION CHECKS ===")
    if total_aroi_cw > 1.0:
        print("⚠️  WARNING: AROI consensus weight sum exceeds 100% - potential double counting!")
    else:
        print("✅ AROI consensus weight sum is reasonable")
        
    if (total_aroi_bandwidth / total_network_bandwidth) > 1.0:
        print("⚠️  WARNING: AROI bandwidth sum exceeds network total - potential double counting!")
    else:
        print("✅ AROI bandwidth sum is reasonable")
        
    if total_aroi_relays > total_network_relays:
        print("⚠️  WARNING: AROI relay count exceeds network total - potential double counting!")
    else:
        print("✅ AROI relay count is reasonable")

if __name__ == '__main__':
    main() 