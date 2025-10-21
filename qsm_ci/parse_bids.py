#!/usr/bin/env python

import os
import re
import json
import argparse
import glob

def parse_bids_directory(bids_dir):
    """Parse BIDS directory and return a list of dictionaries."""
    print("[INFO] Scanning BIDS directory:", bids_dir)
    
    # Read qsm-forward-params.json to get B0_dir per acquisition
    params_file = 'qsm-forward-params.json'
    b0_dir_map = {}
    if os.path.exists(params_file):
        print(f"[INFO] Reading B0_dir from {params_file}")
        with open(params_file, 'r') as f:
            params = json.load(f)
            for param_set in params:
                acq = param_set.get('--acq')
                b0_dir = param_set.get('--B0-dir', [0, 0, 1])
                if acq:
                    b0_dir_map[acq] = b0_dir
                    print(f"[INFO] Found B0_dir for acq={acq}: {b0_dir}")
    
    # Dictionary to store acquisition-specific groups
    acq_groups = {}

    # Process files and directories
    for root, dirs, files in os.walk(bids_dir):
        # Extract the subject and session from the folder path
        subject_match = re.search(r'sub-(\w+)', root)
        session_match = re.search(r'ses-(\w+)', root)
        subject = subject_match.group(1) if subject_match else None
        session = session_match.group(1) if session_match else None

        # Sort files to ensure they are processed in the correct order
        files.sort()

        for file in files:
            if file.endswith('.nii') or file.endswith('.json') or file.endswith('.nii.gz'):
                # Extract acquisition and run
                acquisition_match = re.search(r'_acq-(\w+)_', file)
                acquisition = acquisition_match.group(1) if acquisition_match else None

                run_match = re.search(r'_run-(\d+)_', file)
                run = run_match.group(1) if run_match else None

                # Extract parts of the filename
                echo_match = re.search(r'_echo-(\d+)_', file)
                part_match = re.search(r'_part-(mag|phase)_', file)
                suffix_match = re.search(r'_MEGRE\.(nii|json)', file)

                # Skip files that don't match the raw BIDS MEGRE series (no derivatives)
                if not echo_match or not part_match or not suffix_match:
                    continue

                # MEGRE-related file processing
                if echo_match:
                    echo_number = int(echo_match.group(1))
                else:
                    echo_number = 1
                
                if part_match:
                    part = part_match.group(1)
                else:
                    part = 'mag'    

                # Initialize acquisition group if it doesn't exist
                if acquisition not in acq_groups:
                    acq_groups[acquisition] = {
                        "phase_nii": [],
                        "mag_nii": [],
                        "phase_json": [],
                        "mag_json": [],
                        "EchoTime": [],
                        "MagneticFieldStrength": None,
                        "Derivatives": {}
                    }

                # Add files to the acquisition group based on their type
                if part == "mag":
                    if file.endswith('.nii') or file.endswith('.nii.gz'):
                        if os.path.join(root, file) not in acq_groups[acquisition]['mag_nii']:
                            acq_groups[acquisition]['mag_nii'].append(os.path.join(root, file))
                    elif file.endswith('.json'):
                        if os.path.join(root, file) not in acq_groups[acquisition]['mag_json']:
                            acq_groups[acquisition]['mag_json'].append(os.path.join(root, file))
                            # Extract EchoTime and MagneticFieldStrength from JSON
                            with open(os.path.join(root, file), 'r') as f:
                                metadata = json.load(f)
                                if metadata.get('EchoTime') and metadata.get('EchoTime') not in acq_groups[acquisition]['EchoTime']:
                                    acq_groups[acquisition]['EchoTime'].append(metadata.get('EchoTime'))
                                if acq_groups[acquisition]['MagneticFieldStrength'] is None:
                                    acq_groups[acquisition]['MagneticFieldStrength'] = metadata.get('MagneticFieldStrength')
                elif part == "phase":
                    if file.endswith('.nii') or file.endswith('.nii.gz'):
                        if os.path.join(root, file) not in acq_groups[acquisition]['phase_nii']:
                            acq_groups[acquisition]['phase_nii'].append(os.path.join(root, file))
                    elif file.endswith('.json'):
                        if os.path.join(root, file) not in acq_groups[acquisition]['phase_json']:
                            acq_groups[acquisition]['phase_json'].append(os.path.join(root, file))
                            # Extract EchoTime and MagneticFieldStrength from JSON
                            with open(os.path.join(root, file), 'r') as f:
                                metadata = json.load(f)
                                if metadata.get('EchoTime') and metadata.get('EchoTime') not in acq_groups[acquisition]['EchoTime']:
                                    acq_groups[acquisition]['EchoTime'].append(metadata.get('EchoTime'))
                                if acq_groups[acquisition]['MagneticFieldStrength'] is None:
                                    acq_groups[acquisition]['MagneticFieldStrength'] = metadata.get('MagneticFieldStrength')

    # Convert groups to list format
    groups = []
    for acq, files in acq_groups.items():
        group = {
            "Subject": None,
            "Session": None,
            "Acquisition": acq,
            "Run": None,
            "phase_nii": files['phase_nii'],
            "mag_nii": files['mag_nii'],
            "phase_json": [],
            "mag_json": [],
            "EchoTime": [],
            "MagneticFieldStrength": None,
            "Derivatives": {},
            "B0_dir": b0_dir_map.get(acq, [0, 0, 1])  # Add B0_dir here
        }
        groups.append(group)
        print(f"[INFO] Group for acq={acq} created with B0_dir={group['B0_dir']}")

    # Return the groups
    parsed_data = {"Groups": groups}
    parsed_data = sorted(parsed_data["Groups"], key=lambda x: (x['Subject'], x['Session'] if x['Session'] else "", x['Acquisition'] if x['Acquisition'] else "", x['Run'] if x['Run'] else ""))
    return parsed_data

def save_groups_to_json(groups, output_dir):
    # Ensure output directory exists
    os.makedirs(output_dir, exist_ok=True)

    # Write each group to its own JSON file
    for i, group in enumerate(groups):
        group_filename = os.path.join(output_dir, f"group_{i+1:03}.json")
        with open(group_filename, 'w') as json_file:
            json.dump(group, json_file, indent=4)

def main():
    # Parse command-line arguments
    parser = argparse.ArgumentParser(description='Parse a BIDS directory and save group data as JSON files.')
    parser.add_argument('bids_dir', type=str, help='Path to the BIDS directory')
    parser.add_argument('output_dir', type=str, help='Directory to save the output JSON files')

    args = parser.parse_args()

    # Parse the BIDS directory
    parsed_data = parse_bids_directory(args.bids_dir)

    # Save the parsed groups to JSON files
    save_groups_to_json(parsed_data, args.output_dir)

if __name__ == "__main__":
    main()
