#!/usr/bin/env python

import os
import re
import json
import argparse
import subprocess

def parse_bids_directory(bids_dir):
    print("[DEBUG] Scanning BIDS directory:", bids_dir)
    print("[DEBUG] BIDS directory contents:")
    subprocess.run(['ls', '-R', bids_dir])

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

    # List to store groups
    groups = []

    # Dictionary to temporarily store derivatives if the group doesn't exist yet
    temp_derivatives = {}

    # Walk through the BIDS directory
    for root, dirs, files in os.walk(bids_dir):
        for file in files:
            if file.endswith('.nii') or file.endswith('.json') or file.endswith('.nii.gz'):
                # Extract subject, session, acquisition, and run from the file path
                rel_path = os.path.relpath(root, bids_dir)
                path_parts = rel_path.split(os.sep)

                if len(path_parts) < 2:
                    continue  # Skip files that don't have subject/session in the path

                subject = path_parts[0]
                session = path_parts[1] if len(path_parts) > 1 else None
                acquisition = re.search(r'_acq-(\w+)', file)
                run = re.search(r'_run-(\d+)', file)

                acquisition = acquisition.group(1) if acquisition else None
                run = run.group(1) if run else None

                # Initialize group variable
                group = None

                # Check if the group already exists
                for g in groups:
                    if g["Subject"] == subject and g["Session"] == session and g["Acquisition"] == acquisition:
                        group = g
                        break

                if not group:
                    # Create a new group if it doesn't exist
                    group = {
                        "Subject": subject,
                        "Session": session,
                        "Acquisition": acquisition,
                        "Run": run,
                        "phase_nii": [],
                        "phase_json": [],
                        "mag_nii": [],
                        "mag_json": [],
                        "EchoTime": [],
                        "MagneticFieldStrength": None,
                        "Derivatives": {},
                        "B0_dir": b0_dir_map.get(acquisition, [0, 0, 1])  # Add B0_dir here
                    }
                    groups.append(group)
                    print(f"[INFO] Group for acq={acquisition} created with B0_dir={group['B0_dir']}")

                # ...existing code for file processing...

    # ...existing code for derivatives matching...

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
