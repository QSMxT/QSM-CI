#!/usr/bin/env python

import argparse
import os
import subprocess
import hashlib
import tempfile
import requests
import json

PARSEAPI_URL = "https://parseapi.back4app.com/classes/Images"

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

    # Compute the MD5 hash of the local file
    with open(nifti_file, 'rb') as f:
        local_md5 = hashlib.md5(f.read()).hexdigest()
    print(f"[DEBUG] Local file MD5: {local_md5}")

    # Nectar Swift Object Storage URL
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
            os.remove(temp_file_name)

    print(f"[DEBUG] {nifti_file} is being uploaded to Nectar Swift Object Storage for algorithm {algo_name}.")

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

    # Upload via rclone
    print("[DEBUG] Uploading via rclone...")
    result = subprocess.run(['rclone', 'copy', nifti_file, 'nectar-swift-qsmxt:qsmxt'], check=True)

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

    payload = {
        "url": url,
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

    response = requests.post(
        PARSEAPI_URL,
        json=payload,
        headers=headers
    )

    # print response status code and text
    print(f"[DEBUG] Response status code: {response.status_code}")
    print(f"[DEBUG] Response text: {response.text}")

    if response.status_code == 201:
        print("[DEBUG] Metrics posted to the database successfully.")
    else:
        print(f"[DEBUG] Failed to post metrics to the database.")

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

