#!/usr/bin/env python

import argparse
import os
import subprocess
import hashlib
import tempfile
import requests
import json

PARSEAPI_URL = "https://parseapi.back4app.com/classes/Images"

def find_metadata_file(algo_name):
    #Find the metadata file for the given algorithm.
    standard_path = f"algos/{algo_name}/metadata.json"
    if os.path.exists(standard_path):
        print(f"[DEBUG] Found metadata file: {standard_path}")
        return standard_path
    
    print(f"[WARNING] No metadata file found for algorithm {algo_name}")
    return None

def delete_all_images(parse_application_id, parse_rest_api_key, parse_master_key):
    headers = {
        "X-Parse-Application-Id": parse_application_id,
        "X-Parse-REST-API-Key": parse_rest_api_key,
        "X-Parse-Master-Key": parse_master_key,
        "Content-Type": "application/json"
    }

    # Fetch all image records from the database
    response = requests.get(
        PARSEAPI_URL,
        headers=headers
    )

    if response.status_code == 200:
        images = response.json().get('results', [])
        print(f"[DEBUG] Found {len(images)} images to delete.")

        for image in images:
            image_id = image['objectId']
            delete_url = f"{PARSEAPI_URL}/{image_id}"

            # Send a delete request for each image
            delete_response = requests.delete(delete_url, headers=headers)
            if delete_response.status_code == 200:
                print(f"[DEBUG] Deleted image with objectId: {image_id}")
            else:
                print(f"[DEBUG] Failed to delete image with objectId: {image_id}. Response: {delete_response.text}")
    else:
        print(f"[DEBUG] Failed to fetch images from the database. Response: {response.text}")

def upload_file_to_swift(nifti_file, json_file, algo_name, parse_application_id, parse_rest_api_key, parse_master_key):
    print("[INFO] In upload_file_to_swift")
    acq_name = None
    
    env_acq = os.getenv('BIDS_ACQUISITION')
    if env_acq and env_acq.lower() != "null":
        acq_name = env_acq
        print(f"[INFO] Detected acquisition from environment: {acq_name}")

    # 2) Fallback: read from group_xxx.json if available
    if not acq_name:
        group_files = [f for f in os.listdir('.') if f.startswith('group_') and f.endswith('.json')]
        if group_files:
            group_file = group_files[0]
            try:
                with open(group_file, 'r') as f:
                    group_data = json.load(f)
                if isinstance(group_data, list) and len(group_data) > 0:
                    acq_name = group_data[0].get("--acq")
                    print(f"[INFO] Detected acquisition from {group_file}: {acq_name}")
            except Exception as e:
                print(f"[WARN] Could not read {group_file}: {e}")

    # 3) Fallback: qsm-forward-params.json if neither of the above
    if not acq_name:
        params_file = '/workdir/qsm-forward-params.json'
        if os.path.exists(params_file):
            try:
                with open(params_file, 'r') as f:
                    params = json.load(f)
                if isinstance(params, list) and len(params) > 0:
                    acq_name = params[0].get("--acq")
                    print(f"[INFO] Detected acquisition from qsm-forward-params.json: {acq_name}")
            except Exception as e:
                print(f"[WARN] Could not read {params_file}: {e}")

    # 4) Final fallback
    if not acq_name:
        acq_name = "unknown"
        print("[WARN] Could not determine acquisition name, using 'unknown'.")

    # Compute the MD5 hash of the local file
    with open(nifti_file, 'rb') as f:
        local_md5 = hashlib.md5(f.read()).hexdigest()
    print(f"[DEBUG] Local file MD5: {local_md5}")

    # Nectar Swift Object Storage URL
    if acq_name:
        url = f"https://object-store.rc.nectar.org.au:8888/v1/AUTH_dead991e1fa847e3afcca2d3a7041f5d/qsmxt/{algo_name}_acq-{acq_name}.nii"
    else:
        url = f"https://object-store.rc.nectar.org.au:8888/v1/AUTH_dead991e1fa847e3afcca2d3a7041f5d/qsmxt/{algo_name}.nii"

    # Try to download the remote file to a temp location and calculate its MD5
    with tempfile.NamedTemporaryFile(delete=False) as temp_file:
        temp_file_name = temp_file.name
        try:
            subprocess.run(['wget', '-O', temp_file_name, url], check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            with open(temp_file_name, 'rb') as f:
                remote_md5 = hashlib.md5(f.read()).hexdigest()
            print(f"[DEBUG] Remote file MD5: {remote_md5}")

            if local_md5 == remote_md5:
                print(f"[DEBUG] {algo_name} exists in Nectar Swift Object Storage and is up-to-date.")
                os.remove(temp_file_name)
                return

        except subprocess.CalledProcessError:
            print(f"[DEBUG] {algo_name} does not exist in Nectar Swift Object Storage or could not be downloaded.")

        finally:
            if os.path.exists(temp_file_name):
                os.remove(temp_file_name)
            else:
                print(f"[DEBUG] Temp file {temp_file_name} already removed — skipping cleanup.")


    print(f"[DEBUG] {nifti_file} is being uploaded to Nectar Swift Object Storage for algorithm {algo_name} (acq: {acq_name}).")

    # Configure for SWIFT storage
    print("[DEBUG] Configuring for SWIFT storage")
    result = subprocess.run(['pip3', 'install', 'setuptools', 'wheel', 'python-swiftclient', 'python-keystoneclient'], check=True)

    # print subprocess exit code and output
    print(f"[DEBUG] pip3 exit code: {result.returncode}")
    print(f"[DEBUG] pip3 output: {result.stdout}")

    if result.returncode != 0:
        print("[DEBUG] Failed to install required packages for SWIFT storage.")
        return 1

    os.environ['OS_AUTH_URL'] = 'https://keystone.rc.nectar.org.au:5000/v3/'
    os.environ['OS_AUTH_TYPE'] = 'v3applicationcredential'
    os.environ['OS_PROJECT_NAME'] = 'neurodesk'
    os.environ['OS_USER_DOMAIN_NAME'] = 'Default'
    os.environ['OS_REGION_NAME'] = 'Melbourne'

    # Set up rclone configuration for Swift storage
    rclone_config_dir = os.path.expanduser("~/.config/rclone")
    os.makedirs(rclone_config_dir, exist_ok=True)
    rclone_config_path = os.path.join(rclone_config_dir, "rclone.conf")

    # Load our template configuration
    import configparser
    template_config = configparser.ConfigParser()
    template_path = os.path.join(os.path.dirname(__file__), 'config', 'rclone.conf.template')

    template_config.read(template_path)
    print(f"[DEBUG] Loaded rclone config template from {template_path}")

    # Read existing user config if it exists
    user_config = configparser.ConfigParser()
    if os.path.exists(rclone_config_path):
        user_config.read(rclone_config_path)
        print(f"[DEBUG] Read existing rclone config from {rclone_config_path}")

    # Merge template sections into user config
    for section in template_config.sections():
        if section not in user_config:
            user_config[section] = {}
            print(f"[DEBUG] Adding section '{section}' to rclone config")
        else:
            print(f"[DEBUG] Updating existing section '{section}' in rclone config")

        # Update section with template values
        for key, value in template_config[section].items():
            user_config[section][key] = value

    # Write back the merged config
    with open(rclone_config_path, 'w') as f:
        user_config.write(f)

    print(f"[DEBUG] Updated rclone config at {rclone_config_path}")

    # Upload via rclone
    print("[DEBUG] Uploading via rclone...")
    if acq_name:
        subprocess.run(['rclone', 'copyto', nifti_file, f'nectar-swift-qsmxt:qsmxt/{algo_name}_acq-{acq_name}.nii'], check=True)
    else:
        subprocess.run(['rclone', 'copyto', nifti_file, f'nectar-swift-qsmxt:qsmxt/{algo_name}.nii'], check=True)

    # print subprocess exit code and output
    print(f"[DEBUG] rclone exit code: {result.returncode}")
    print(f"[DEBUG] rclone output: {result.stdout}")

    if result.returncode != 0:
        print("[DEBUG] Failed to upload via rclone.")
        return 1

    # Check if it is uploaded to Nectar Swift Object Storage
    response = requests.head(url)
    if response.status_code != 200:
        print(f"[DEBUG] Failed to upload {nifti_file} to Nectar Swift Object Storage.")
        print(f"[DEBUG] Response {response.status_code}: {response.text}")
        return 2
    
    print(f"[DEBUG] {nifti_file} now exists in Nectar Swift Object Storage as {algo_name}.nii")

    # Post metrics to the database
    with open(json_file, 'r') as jf:
        metrics = json.load(jf)

    # Find and read metadata file
    metadata_file = find_metadata_file(algo_name)
    metadata = {}
    if metadata_file:
        try:
            with open(metadata_file, 'r') as mf:
                metadata = json.load(mf)
            print(f"[DEBUG] Using metadata from: {metadata_file}")
        except Exception as e:
            print(f"[ERROR] Failed to read metadata file {metadata_file}: {e}")
            print(f"[WARNING] Using empty metadata due to error.")
            metadata = {}
    else:
        print(f"[WARNING] No metadata file found for algorithm {algo_name}. Using empty metadata.")

    payload = {
        "url": url,
        "acq": acq_name,  
        "RMSE": metrics.get('RMSE'),
        "NRMSE": metrics.get('NRMSE'),
        "HFEN": metrics.get('HFEN'),
        "MAD": metrics.get('MAD'),
        "XSIM": metrics.get('XSIM'),
        "CC1": metrics['CC'][0] if 'CC' in metrics and len(metrics['CC']) > 0 else None,
        "CC2": metrics['CC'][1] if 'CC' in metrics and len(metrics['CC']) > 1 else None,
        "NMI": metrics.get('NMI'),
        "GXE": metrics.get('GXE'),
        "algorithmDescription": metadata.get('algorithmDescription', ''),
        "tags": metadata.get('tags', [])
    }

    headers = {
        "X-Parse-Application-Id": parse_application_id,
        "X-Parse-REST-API-Key": parse_rest_api_key,
        "X-Parse-Master-Key": parse_master_key,
        "Content-Type": "application/json"
    }

    response = requests.post(
        PARSEAPI_URL,
        json=payload,
        headers=headers
    )

    # print response status code and text
    print(f"[DEBUG] Response status code: {response.status_code}")
    print(f"[DEBUG] Response text: {response.text}")

    if response.status_code == 201:
        print("[DEBUG] Metrics and acquisition info posted to the database successfully.")
    else:
        print(f"[DEBUG] Failed to post metrics to the database.")

def main():
    parser = argparse.ArgumentParser(description='Upload NIfTI file to Nectar Swift Object Storage')
    parser.add_argument('nifti_file', type=str, help='Path to the NIfTI file')
    parser.add_argument('json_file', type=str, help='Path to the JSON file produced by `qsm-ci eval` containing metrics')
    parser.add_argument('algo_name', type=str, nargs='?', help='Name of the algorithm (optional, will be constructed if not provided)')
    parser.add_argument('parse_application_id', type=str, help='Parse Application ID')
    parser.add_argument('parse_rest_api_key', type=str, help='Parse REST API Key')
    parser.add_argument('parse_master_key', type=str, help='Parse Master Key')
    args = parser.parse_args()

    # check if the files exist
    if not os.path.exists(args.nifti_file):
        print(f"[ERROR] NIfTI file {args.nifti_file} does not exist.")
        return 1
    if not os.path.exists(args.json_file):
        print(f"[ERROR] JSON file {args.json_file} does not exist.")
        return 1

    # Build unique algo_name if not provided
    algo_name = args.algo_name
    if not algo_name or algo_name.lower() == "none":
        base_name = os.getenv('PIPELINE_NAME', 'algo')
        acq = os.getenv('BIDS_ACQUISITION')
        subject = os.getenv('BIDS_SUBJECT')
        session = os.getenv('BIDS_SESSION')
        run = os.getenv('BIDS_RUN')
        algo_name = base_name
        if acq and acq.lower() != "null":
            algo_name += f"_acq-{acq}"
        if subject and subject.lower() != "null":
            algo_name += f"_sub-{subject}"
        if session and session.lower() != "null":
            algo_name += f"_ses-{session}"
        if run and run.lower() != "null":
            algo_name += f"_run-{run}"
        print(f"[DEBUG] Constructed unique algo_name: {algo_name}")

    # display the arguments
    print(f"[DEBUG] parse_application_id: {args.parse_application_id}")
    print(f"[DEBUG] parse_rest_api_key: {args.parse_rest_api_key}")
    print(f"[DEBUG] parse_master_key: {args.parse_master_key}")

    # upload the files to swift
    upload_file_to_swift(
        args.nifti_file,
        args.json_file,
        algo_name,
        args.parse_application_id,
        args.parse_rest_api_key,
        args.parse_master_key
    )


if __name__ == "__main__":
    main()