#!/usr/bin/env bash

set -e

# Install jq if not already installed
if ! command -v jq &> /dev/null; then
    sudo apt-get update
    sudo apt-get install jq
fi

JSON_FILE="recons/${ALGO_NAME}/metrics.json"
NIFTI_FILE="recons/${ALGO_NAME}/${ALGO_NAME}.nii"

NIFTI_HASH=$(md5sum "${NIFTI_FILE}" | awk '{print $1}')
DIRNAME=$(dirname "${NIFTI_FILE}")
BASENAME=$(basename "${NIFTI_FILE}")
cp "${DIRNAME}/${BASENAME}" "${NIFTI_HASH}_${BASENAME}"

echo "[DEBUG] Checking file..."
ls ${NIFTI_HASH}_${BASENAME} -lahtr

# Upload to Nectar Swift Object Storage
URL=https://object-store.rc.nectar.org.au:8888/v1/AUTH_dead991e1fa847e3afcca2d3a7041f5d/qsmxt/${NIFTI_HASH}_${BASENAME}
if curl --output /dev/null --silent --head --fail "${URL}"; then
    echo "[DEBUG] ${NIFTI_HASH}_${BASENAME} exists in nectar swift object storage"
else
    echo "[DEBUG] ${NIFTI_HASH}_${BASENAME} does not exist yet in nectar swift - uploading it there as well!"

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
    swift upload qsmxt "${NIFTI_HASH}_${BASENAME}" --segment-size 1073741824 --verbose

    # Check if it is uploaded to Nectar Swift Object Storage and if so, add it to the database
    if curl --output /dev/null --silent --head --fail "${URL}"; then
        echo "[DEBUG] ${NIFTI_HASH}_${BASENAME} exists in nectar swift object storage"

        curl -X POST \
        -H "X-Parse-Application-Id: ${PARSE_APPLICATION_ID}" \
        -H "X-Parse-REST-API-Key: ${PARSE_REST_API_KEY}" \
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
        echo "[DEBUG] ${NIFTI_HASH}_${BASENAME} does not exist yet in nectar swift"
        exit 2
    fi
fi

