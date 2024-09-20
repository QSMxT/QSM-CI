#!/usr/bin/env python

import os
import re
import json
import argparse

def parse_bids_directory(bids_dir):
    # List to store groups
    groups = []

    # Dictionary to temporarily store derivatives if the group doesn't exist yet
    temp_derivatives = {}

    # Process files and directories
    for root, dirs, files in os.walk(bids_dir):
        # Determine if we are in the derivatives directory
        is_derivative = 'derivatives' in root

        # Extract the session from the folder path
        session_match = re.search(r'ses-(\w+)', root)
        session = session_match.group(1) if session_match else None

        # Sort files to ensure they are processed in the correct order
        files.sort()

        for file in files:
            if file.endswith('.nii') or file.endswith('.json') or file.endswith('.nii.gz'):
                # Extract the subject from the directory structure
                subject_match = re.search(r'sub-(\w+)', root)
                if not subject_match:
                    continue
                subject = subject_match.group(1)

                # Extract session from filename if not already extracted from the folder
                if not session:
                    session_file_match = re.search(r'_ses-(\w+)', file)
                    session = session_file_match.group(1) if session_file_match else None

                # Extract acquisition and run
                acquisition_match = re.search(r'_acq-([^_]+)', file)
                acquisition = acquisition_match.group(1) if acquisition_match else None

                run_match = re.search(r'_run-([^_]+)_', file)
                run = run_match.group(1) if run_match else None

                # Extract parts of the filename
                echo_match = re.search(r'_echo-([^_]+)_', file)
                part_match = re.search(r'_part-(mag|phase)_', file)
                suffix_match = re.search(r'_MEGRE', file)

                # Skip files that don't match the MEGRE series
                if not echo_match or not part_match or not suffix_match:
                    # Handle derivatives that are not part of the MEGRE series
                    if is_derivative:
                        software_name_match = re.search(r'derivatives/([^/]+)/', root)
                        if software_name_match:
                            software_name = software_name_match.group(1)
                            derivative_type_match = re.search(r'_([^_]+)(?=\.(nii|nii\.gz))', file)
                            if derivative_type_match:
                                derivative_type = derivative_type_match.group(1)
                                if derivative_type == "mask":
                                    # Handle mask in the root node, create a list if needed
                                    group = next((g for g in groups if g['Subject'] == subject and
                                                                     g['Session'] == session and
                                                                     g['Acquisition'] == acquisition and
                                                                     g['Run'] == run), None)
                                    if not group:
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
                                            "Derivatives": {}
                                        }
                                        groups.append(group)
                                    if "mask" not in group:
                                        group["mask"] = os.path.join(root, file)
                                    else:
                                        if not isinstance(group["mask"], list):
                                            group["mask"] = [group["mask"]]
                                        group["mask"].append(os.path.join(root, file))
                                else:
                                    if subject not in temp_derivatives:
                                        temp_derivatives[subject] = []
                                    temp_derivatives[subject].append({
                                        "software_name": software_name,
                                        "type": derivative_type,
                                        "session": session,
                                        "acquisition": acquisition,
                                        "run": run,
                                        "path": os.path.join(root, file)
                                    })
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

                group = next((g for g in groups if g['Subject'] == subject and
                                                    g['Session'] == session and
                                                    g['Acquisition'] == acquisition and
                                                    g['Run'] == run), None)

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
                        "Derivatives": {}
                    }
                    groups.append(group)

                # Add files to the group based on their type
                if part == "mag":
                    if file.endswith('.nii'):
                        if os.path.join(root, file) not in group['mag_nii']:
                            group['mag_nii'].append(os.path.join(root, file))
                    elif file.endswith('.json'):
                        if os.path.join(root, file) not in group['mag_json']:
                            group['mag_json'].append(os.path.join(root, file))
                            # Extract EchoTime and MagneticFieldStrength from JSON
                            with open(os.path.join(root, file), 'r') as f:
                                metadata = json.load(f)
                                if metadata.get('EchoTime') and metadata.get('EchoTime') not in group['EchoTime']:
                                    group['EchoTime'].append(metadata.get('EchoTime'))
                                if group['MagneticFieldStrength'] is None:
                                    group['MagneticFieldStrength'] = metadata.get('MagneticFieldStrength')
                elif part == "phase":
                    if file.endswith('.nii'):
                        if os.path.join(root, file) not in group['phase_nii']:
                            group['phase_nii'].append(os.path.join(root, file))
                    elif file.endswith('.json'):
                        if os.path.join(root, file) not in group['phase_json']:
                            group['phase_json'].append(os.path.join(root, file))
                            # Extract EchoTime and MagneticFieldStrength from JSON
                            with open(os.path.join(root, file), 'r') as f:
                                metadata = json.load(f)
                                if metadata.get('EchoTime') and metadata.get('EchoTime') not in group['EchoTime']:
                                    group['EchoTime'].append(metadata.get('EchoTime'))
                                if group['MagneticFieldStrength'] is None:
                                    group['MagneticFieldStrength'] = metadata.get('MagneticFieldStrength')

                # Ensure that sorting only happens when the lengths of all lists are equal
                group['EchoTime'] = sorted(group['EchoTime'])
                group['mag_nii'] = sorted(group['mag_nii'])
                group['mag_json'] = sorted(group['mag_json'])
                group['phase_nii'] = sorted(group['phase_nii'])
                group['phase_json'] = sorted(group['phase_json'])

    # Match derivatives with the corresponding groups by subject, session, acquisition, and run
    for subject, derivatives in temp_derivatives.items():
        for derivative in derivatives:
            for group in groups:
                if (group['Subject'] == subject and 
                    group['Session'] == derivative['session'] and 
                    group['Acquisition'] == derivative['acquisition'] and 
                    group['Run'] == derivative['run']):
                    # Add derivatives to the matching group
                    if derivative['software_name'] not in group['Derivatives']:
                        group['Derivatives'][derivative['software_name']] = {}
                    if derivative['type'] not in group['Derivatives'][derivative['software_name']]:
                        group['Derivatives'][derivative['software_name']][derivative['type']] = []
                    if derivative['path'] not in group['Derivatives'][derivative['software_name']][derivative['type']]:
                        group['Derivatives'][derivative['software_name']][derivative['type']].append(derivative['path'])

    # Return the groups
    return {"Groups": groups}

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
    save_groups_to_json(sorted(parsed_data["Groups"], key=lambda x: (x['Subject'], x['Session'], x['Acquisition'], x['Run'])), args.output_dir)

if __name__ == "__main__":
    main()
    