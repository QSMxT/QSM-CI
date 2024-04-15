#!/usr/bin/env bash

set -e

# Install jq if not already installed
if ! command -v jq &> /dev/null; then
    sudo apt-get update -y
    sudo apt-get install jq -y
fi

JSON_FILE="output/${PIPELINE_NAME}/metrics.json"
NIFTI_FILE="output/${PIPELINE_NAME}/${PIPELINE_NAME}.nii.gz"

DIRNAME=$(dirname "${NIFTI_FILE}")
BASENAME=$(basename "${NIFTI_FILE}")
cp "${DIRNAME}/${BASENAME}" "${BASENAME}"

echo "[DEBUG] Checking file..."
ls ${BASENAME} -lahtr

# Compute the MD5 hash of the local file
LOCAL_MD5=$(md5sum "${BASENAME}" | cut -d' ' -f1)
echo "[DEBUG] Local file MD5: ${LOCAL_MD5}"

# Upload to Nectar Swift Object Storage
URL=https://object-store.rc.nectar.org.au:8888/v1/AUTH_dead991e1fa847e3afcca2d3a7041f5d/qsmxt/${BASENAME}

# Try to download the remote file to a temp location and calculate its MD5
TEMP_FILE=$(mktemp)
if wget -O "${TEMP_FILE}" "${URL}" 2>/dev/null; then
    REMOTE_MD5=$(md5sum "${TEMP_FILE}" | cut -d' ' -f1)
    echo "[DEBUG] Remote file MD5: ${REMOTE_MD5}"

    if [ "${LOCAL_MD5}" = "${REMOTE_MD5}" ]; then
        echo "[DEBUG] ${BASENAME} exists in Nectar Swift Object Storage and is up-to-date."
        rm -f "${TEMP_FILE}"
        exit 0
    fi
else
    echo "[DEBUG] ${BASENAME} does not exist in Nectar Swift Object Storage or could not be downloaded."
fi
rm -f "${TEMP_FILE}"

echo "[DEBUG] ${BASENAME} is being uploaded to Nectar Swift Object Storage."

if [ -n "$swift_setup_done" ]; then
    echo "[DEBUG] Setup already done. Skipping."
else
    echo "[DEBUG] Configure for SWIFT storage"
    sudo pip3 install setuptools
    sudo pip3 install wheel
    sudo pip3 install python-swiftclient python-keystoneclient
    export OS_AUTH_URL=https://keystone.rc.nectar.org.au:5000/v3/
    export OS_AUTH_TYPE=v3applicationcredential
    export OS_PROJECT_NAME="neurodesk"
    export OS_USER_DOMAIN_NAME="Default"
    export OS_REGION_NAME="Melbourne"
    export swift_setup_done="true"
fi

echo "[DEBUG] Uploading via swift..."
rclone copy "${BASENAME}" nectar-swift-qsmxt:qsmxt

# Check if it is uploaded to Nectar Swift Object Storage and if so, add it to the database
if curl --output /dev/null --silent --head --fail "${URL}"; then
    echo "[DEBUG] ${BASENAME} exists in nectar swift object storage"

    echo "[DEBUG] Posting metrics for ${BASENAME} to the database."
    echo curl -X POST \
    -H "X-Parse-Application-Id: ${PARSE_APPLICATION_ID}" \
    -H "X-Parse-REST-API-Key: ${PARSE_REST_API_KEY}" \
    -H "X-Parse-Master-Key: ${PARSE_MASTER_KEY}" \
    -H "Content-Type: application/json" \
    -d "{
        \"url\":\"$URL\",
        \"RMSE\": $(jq '.RMSE' "$JSON_FILE"),
        \"NRMSE\": $(jq '.NRMSE' "$JSON_FILE"),
        \"HFEN\": $(jq '.HFEN' "$JSON_FILE"),
        \"MAD\": $(jq '.MAD' "$JSON_FILE"),
        \"XSIM\": $(jq '.XSIM' "$JSON_FILE"),
        \"CC1\": $(jq '.CC[0]' "$JSON_FILE"),
        \"CC2\": $(jq '.CC[1]' "$JSON_FILE"),
        \"NMI\": $(jq '.NMI' "$JSON_FILE"),
        \"GXE\": $(jq '.GXE' "$JSON_FILE")
    }" \
    https://parseapi.back4app.com/classes/Images

else
    echo "[DEBUG] ${BASENAME} does not exist yet in nectar swift"
    exit 2
fi

