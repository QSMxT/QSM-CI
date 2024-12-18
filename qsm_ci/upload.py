#!/usr/bin/env python

import argparse
import os
import subprocess
import hashlib
import tempfile
import requests
import json

PARSEAPI_URL = "https://parseapi.back4app.com/classes/Images"
OBJECT_STORAGE_URL = "https://object-store.rc.nectar.org.au:8888/v1/AUTH_dead991e1fa847e3afcca2d3a7041f5d"

def upload_file_to_swift(nifti_file, json_file, algo_name, parse_application_id, parse_rest_api_key, parse_master_key):
    print("[INFO] In upload_file_to_swift")

    def compute_md5(file_path):
        """Compute the MD5 hash of a local file."""
        with open(file_path, 'rb') as f:
            return hashlib.md5(f.read()).hexdigest()

    def check_remote_md5(url):
        """Download the remote file and compute its MD5 hash."""
        with tempfile.NamedTemporaryFile(delete=False) as temp_file:
            try:
                subprocess.run(['wget', '-O', temp_file.name, url], check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
                with open(temp_file.name, 'rb') as f:
                    remote_md5 = hashlib.md5(f.read()).hexdigest()
                return remote_md5
            except subprocess.CalledProcessError:
                print(f"[DEBUG] {url} does not exist or failed to download.")
                return None
            finally:
                os.remove(temp_file.name)

    def upload_to_swift(local_file, remote_path):
        """Upload a file to Swift storage using rclone."""
        print(f"[DEBUG] Uploading {local_file} to Swift as {remote_path}...")
        result = subprocess.run(['rclone', 'copyto', local_file, f'nectar-swift-qsmxt:{remote_path}'], check=True)
        if result.returncode != 0:
            print(f"[ERROR] Failed to upload {local_file}.")
            return False
        return True

    # Compute local hashes
    nifti_md5 = compute_md5(nifti_file)
    json_md5 = compute_md5(json_file)
    print(f"[DEBUG] Local NIfTI file MD5: {nifti_md5}")
    print(f"[DEBUG] Local JSON file MD5: {json_md5}")

    # Define remote file URLs and paths
    nifti_url = f"{OBJECT_STORAGE_URL}/qsmxt/{algo_name}.nii"
    json_url = f"{OBJECT_STORAGE_URL}/qsmxt/{algo_name}.json"

    # Check NIfTI hash remotely
    remote_nifti_md5 = check_remote_md5(nifti_url)
    if remote_nifti_md5 == nifti_md5:
        print("[DEBUG] NIfTI file is up-to-date. Skipping upload.")
    else:
        if not upload_to_swift(nifti_file, nifti_url):
            print("[ERROR] Failed to upload NIfTI file.")
            return 1
        print(f"[DEBUG] Uploaded NIfTI file: {nifti_url}")

    # Check JSON hash remotely
    remote_json_md5 = check_remote_md5(json_url)
    if remote_json_md5 == json_md5:
        print("[DEBUG] JSON file is up-to-date. Skipping upload.")
    else:
        print("[DEBUG] JSON file is not up-to-date, but we are skipping it anyway because something broke.")
        #if not upload_to_swift(json_file, json_url):
        #    print("[ERROR] Failed to upload JSON file.")
        #    return 1
        #print(f"[DEBUG] Uploaded JSON file: {json_url}")

    # Post metrics to Parse API
    with open(json_file, 'r') as jf:
        metrics = json.load(jf)

    payload = {
        "url": nifti_url,
        "RMSE": metrics.get('RMSE'),
        "NRMSE": metrics.get('NRMSE'),
        "HFEN": metrics.get('HFEN'),
        "MAD": metrics.get('MAD'),
        "XSIM": metrics.get('XSIM'),
        "CC1": metrics['CC'][0] if 'CC' in metrics and len(metrics['CC']) > 0 else None,
        "CC2": metrics['CC'][1] if 'CC' in metrics and len(metrics['CC']) > 1 else None,
        "NMI": metrics.get('NMI'),
        "GXE": metrics.get('GXE')
    }

    headers = {
        "X-Parse-Application-Id": parse_application_id,
        "X-Parse-REST-API-Key": parse_rest_api_key,
        "X-Parse-Master-Key": parse_master_key,
        "Content-Type": "application/json"
    }

    response = requests.post(PARSEAPI_URL, json=payload, headers=headers)
    print(f"[DEBUG] Response status code: {response.status_code}")
    print(f"[DEBUG] Response text: {response.text}")

    if response.status_code == 201:
        print("[DEBUG] Metrics and file URLs posted successfully to the database.")
    else:
        print("[ERROR] Failed to post metrics to the database.")

def main():
    parser = argparse.ArgumentParser(description='Upload NIfTI file to Nectar Swift Object Storage')
    parser.add_argument('nifti_file', type=str, help='Path to the NIfTI file')
    parser.add_argument('json_file', type=str, help='Path to the JSON file produced by `qsm-ci eval` containing metrics')
    parser.add_argument('algo_name', type=str, help='Name of the algorithm')
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
    
    # display the arguments
    print(f"[DEBUG] parse_application_id: {args.parse_application_id}")
    print(f"[DEBUG] parse_rest_api_key: {args.parse_rest_api_key}")
    print(f"[DEBUG] parse_master_key: {args.parse_master_key}")

    # upload the files to swift
    upload_file_to_swift(
        args.nifti_file,
        args.json_file,
        args.algo_name,
        args.parse_application_id,
        args.parse_rest_api_key,
        args.parse_master_key
    )


if __name__ == "__main__":
    main()

