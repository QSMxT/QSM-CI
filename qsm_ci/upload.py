
import shutil
import os
import subprocess
import hashlib
import tempfile
import requests
import json

def upload_file_to_swift(pipeline_name, parse_application_id, parse_rest_api_key, parse_master_key):
    print("[INFO] In upload_file_to_swift")

    # Paths to files
    json_file = f"output/{pipeline_name}/metrics.json"
    nifti_file = f"output/{pipeline_name}/{pipeline_name}.nii.gz"

    dirname = os.path.dirname(nifti_file)
    basename = os.path.basename(nifti_file)

    # Copy NIfTI file to current directory
    shutil.copy(os.path.join(dirname, basename), basename)

    # Compute the MD5 hash of the local file
    with open(basename, 'rb') as f:
        local_md5 = hashlib.md5(f.read()).hexdigest()
    print(f"[DEBUG] Local file MD5: {local_md5}")

    # Upload to Nectar Swift Object Storage
    url = f"https://object-store.rc.nectar.org.au:8888/v1/AUTH_dead991e1fa847e3afcca2d3a7041f5d/qsmxt/{basename}"

    # Try to download the remote file to a temp location and calculate its MD5
    with tempfile.NamedTemporaryFile(delete=False) as temp_file:
        temp_file_name = temp_file.name
        try:
            subprocess.run(['wget', '-O', temp_file_name, url], check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            with open(temp_file_name, 'rb') as f:
                remote_md5 = hashlib.md5(f.read()).hexdigest()
            print(f"[DEBUG] Remote file MD5: {remote_md5}")

            if local_md5 == remote_md5:
                print(f"[DEBUG] {basename} exists in Nectar Swift Object Storage and is up-to-date.")
                os.remove(temp_file_name)
                return

        except subprocess.CalledProcessError:
            print(f"[DEBUG] {basename} does not exist in Nectar Swift Object Storage or could not be downloaded.")

        finally:
            os.remove(temp_file_name)

    print(f"[DEBUG] {basename} is being uploaded to Nectar Swift Object Storage.")

    # Configure for SWIFT storage
    print("[DEBUG] Configuring for SWIFT storage")
    subprocess.run(['pip3', 'install', 'setuptools', 'wheel', 'python-swiftclient', 'python-keystoneclient'], check=True)

    os.environ['OS_AUTH_URL'] = 'https://keystone.rc.nectar.org.au:5000/v3/'
    os.environ['OS_AUTH_TYPE'] = 'v3applicationcredential'
    os.environ['OS_PROJECT_NAME'] = 'neurodesk'
    os.environ['OS_USER_DOMAIN_NAME'] = 'Default'
    os.environ['OS_REGION_NAME'] = 'Melbourne'

    # Upload via rclone
    print("[DEBUG] Uploading via rclone...")
    subprocess.run(['rclone', 'copy', basename, 'nectar-swift-qsmxt:qsmxt'], check=True)

    # Check if it is uploaded to Nectar Swift Object Storage
    response = requests.head(url)
    if response.status_code == 200:
        print(f"[DEBUG] {basename} exists in Nectar Swift Object Storage")

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
            "https://parseapi.back4app.com/classes/Images",
            json=payload,
            headers=headers
        )

        if response.status_code == 201:
            print("[DEBUG] Metrics posted to the database successfully.")
        else:
            print(f"[DEBUG] Failed to post metrics to the database. Response: {response.text}")
    else:
        print(f"[DEBUG] {basename} does not exist yet in Nectar Swift.")
        return 2

