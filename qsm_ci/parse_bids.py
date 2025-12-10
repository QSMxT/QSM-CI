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

    # Process files and directories
    for root, dirs, files in os.walk(bids_dir):
        # Determine if we are in the derivatives directory
        rel_root = os.path.join('bids', os.path.sep.join(root.split(os.path.sep)[1:]))
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

                # Extract acquisition and run - treat run- as acquisition
                acquisition_match = re.search(r'_(?:acq|run)-(\w+)_', file)
                acquisition = acquisition_match.group(1) if acquisition_match else None

                run_match = re.search(r'_run-(\d+)_', file)
                run = run_match.group(1) if run_match else None

                # Extract parts of the filename
                echo_match = re.search(r'_echo-(\d+)_', file)
                part_match = re.search(r'_part-(mag|phase)_', file)
                suffix_match = re.search(r'_MEGRE\.(nii|json)', file)

                # Skip files that don't match the raw BIDS MEGRE series (no derivatives)
                if not echo_match or not part_match or not suffix_match or is_derivative:
                    # Handle derivatives that are not part of the MEGRE series
                    if is_derivative:
                        software_name_match = re.search(r'derivatives/([^/]+)/', root)
                        if software_name_match:
                            software_name = software_name_match.group(1)
                            derivative_type_match = re.search(r'_([^_]+)(?=\.(nii|nii\.gz))', file)
                            if derivative_type_match:
                                derivative_type = derivative_type_match.group(1)
                                # Store all derivatives the same way, including mask
                                if subject not in temp_derivatives:
                                    temp_derivatives[subject] = []
                                temp_derivatives[subject].append({
                                    "software_name": software_name,
                                    "type": derivative_type,
                                    "session": session,
                                    "acquisition": acquisition,
                                    "run": run,
                                    "path": os.path.join(rel_root, file)
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
                        "Derivatives": {},
                        "B0_dir": b0_dir_map.get(acquisition, [0, 0, 1])  # Only for synthetic data
                    }
                    groups.append(group)
                    print(f"[INFO] Group for acq={acquisition} created with B0_dir={group['B0_dir']}")

                # Add files to the group based on their type
                if part == "mag":
                    if file.endswith('.nii') or file.endswith('.nii.gz'):
                        if os.path.join(rel_root, file) not in group['mag_nii']:
                            group['mag_nii'].append(os.path.join(rel_root, file))
                    elif file.endswith('.json'):
                        if os.path.join(rel_root, file) not in group['mag_json']:
                            group['mag_json'].append(os.path.join(rel_root, file))
                            # Extract EchoTime and MagneticFieldStrength from JSON
                            with open(os.path.join(root, file), 'r') as f:
                                metadata = json.load(f)
                                if metadata.get('EchoTime') and metadata.get('EchoTime') not in group['EchoTime']:
                                    group['EchoTime'].append(metadata.get('EchoTime'))
                                if group['MagneticFieldStrength'] is None:
                                    group['MagneticFieldStrength'] = metadata.get('MagneticFieldStrength')
                                # For COSMOS/Synthetic: read B0 from JSON (prefer B0_direction, else B0_dir)
                                if 'B0_direction' in metadata:
                                    group['B0_dir'] = metadata['B0_direction']
                                elif 'B0_dir' in metadata:
                                    group['B0_dir'] = metadata['B0_dir']
                elif part == "phase":
                    if file.endswith('.nii') or file.endswith('.nii.gz'):
                        if os.path.join(rel_root, file) not in group['phase_nii']:
                            group['phase_nii'].append(os.path.join(rel_root, file))
                    elif file.endswith('.json'):
                        if os.path.join(rel_root, file) not in group['phase_json']:
                            group['phase_json'].append(os.path.join(rel_root, file))
                            # Extract EchoTime and MagneticFieldStrength from JSON
                            with open(os.path.join(root, file), 'r') as f:
                                metadata = json.load(f)
                                if metadata.get('EchoTime') and metadata.get('EchoTime') not in group['EchoTime']:
                                    group['EchoTime'].append(metadata.get('EchoTime'))
                                if group['MagneticFieldStrength'] is None:
                                    group['MagneticFieldStrength'] = metadata.get('MagneticFieldStrength')
                                # For COSMOS/Synthetic: read B0 from JSON (prefer B0_direction, else B0_dir)
                                if 'B0_direction' in metadata:
                                    group['B0_dir'] = metadata['B0_direction']
                                elif 'B0_dir' in metadata:
                                    group['B0_dir'] = metadata['B0_dir']

                # Ensure that sorting only happens when the lengths of all lists are equal
                group['EchoTime'] = sorted(group['EchoTime'])
                group['mag_nii'] = sorted(group['mag_nii'])
                group['mag_json'] = sorted(group['mag_json'])
                group['phase_nii'] = sorted(group['phase_nii'])
                group['phase_json'] = sorted(group['phase_json'])

    # Match derivatives with the corresponding groups by subject, session, acquisition, and run
    for subject, derivatives in temp_derivatives.items():
        for derivative in derivatives:
            # Find all groups for this subject with MEGRE data
            subject_groups = [g for g in groups if g['Subject'] == subject and len(g.get('mag_nii', [])) > 0]
            
            if subject_groups:
                # Sort by acquisition number to get the first run (handle None values)
                subject_groups.sort(key=lambda x: int(x.get('Acquisition', '0')) if x.get('Acquisition') and x.get('Acquisition').isdigit() else 999)
                
                # Check if this is COSMOS data
                first_group = subject_groups[0]
                first_acq = first_group.get('Acquisition')
                is_cosmos_data = first_acq and first_acq.isdigit()
                
                if is_cosmos_data:
                    # For COSMOS: Add derivatives to the first group (run-1)
                    target_group = subject_groups[0]
                    
                    # Add derivatives to the target group
                    if derivative['software_name'] not in target_group['Derivatives']:
                        target_group['Derivatives'][derivative['software_name']] = {}
                    if derivative['type'] not in target_group['Derivatives'][derivative['software_name']]:
                        target_group['Derivatives'][derivative['software_name']][derivative['type']] = []
                    if derivative['path'] not in target_group['Derivatives'][derivative['software_name']][derivative['type']]:
                        target_group['Derivatives'][derivative['software_name']][derivative['type']].append(derivative['path'])
                    
                    # For COSMOS: Add mask to ALL groups, not just the first one
                    if derivative['type'] == "mask":
                        for cosmos_group in subject_groups:
                            cosmos_group["mask"] = derivative['path']
                            print(f"[INFO] Added mask to COSMOS run {cosmos_group.get('Acquisition')}: {derivative['path']}")
                else:
                    # For synthetic data: Try to match by exact acquisition/run
                    matching_groups = [g for g in subject_groups if 
                                     g.get('Session') == derivative['session'] and 
                                     g.get('Acquisition') == derivative['acquisition'] and 
                                     g.get('Run') == derivative['run']]
                            
                    for group in matching_groups:
                        # Add derivatives to matching groups
                        if derivative['software_name'] not in group['Derivatives']:
                            group['Derivatives'][derivative['software_name']] = {}
                        if derivative['type'] not in group['Derivatives'][derivative['software_name']]:
                            group['Derivatives'][derivative['software_name']][derivative['type']] = []
                        if derivative['path'] not in group['Derivatives'][derivative['software_name']][derivative['type']]:
                            group['Derivatives'][derivative['software_name']][derivative['type']].append(derivative['path'])
                        
                        # Also add mask to root level for backward compatibility
                        if derivative['type'] == "mask":
                            group["mask"] = derivative['path']
            else:
                # Skip creating empty groups for derivatives in COSMOS data
                pass

    # Remove empty groups (derivatives-only groups)
    groups = [g for g in groups if len(g.get('mag_nii', [])) > 0 or len(g.get('Derivatives', {})) == 0]

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