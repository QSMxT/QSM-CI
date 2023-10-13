set -e

echo "[INFO] Downloading test data"
curl -OL https://api.opendata.ocs.oraclecloud.com/data/tomcat/TOMCAT_DIB/sub-01/ses-01_7T/anat/sub-01_ses-01_7T_IV1_defaced.nii.gz
curl -OL https://api.opendata.ocs.oraclecloud.com/data/tomcat/TOMCAT_DIB/sub-02/ses-01_7T/anat/sub-02_ses-01_7T_IV1_defaced.nii.gz

echo "[INFO] done"
ls -l

for file in `ls *.nii.gz`; do
    IMAGE_HASH=$(md5sum $file | awk '{print $1}')
    echo $IMAGE_HASH
    mv $file ${IMAGE_HASH}_$file

    # Upload to Nectar Swift Object Storage
    if curl --output /dev/null --silent --head --fail "https://object-store.rc.nectar.org.au:8888/v1/AUTH_dead991e1fa847e3afcca2d3a7041f5d/qsmxt/${IMAGE_HASH}_$file"; then
        echo "[DEBUG] ${IMAGE_HASH}_$file exists in nectar swift object storage"
    else
        echo "[DEBUG] ${IMAGE_HASH}_$file does not exist yet in nectar swift - uploading it there as well!"

        if [ -n "$swift_setup_done" ]; then
            echo "Setup already done. Skipping."
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

        swift upload qsmxt ${IMAGE_HASH}_$file --segment-size 1073741824
    fi

    # Check if it is uploaded to Nectar Swift Object Storage
    if curl --output /dev/null --silent --head --fail "https://object-store.rc.nectar.org.au:8888/v1/AUTH_dead991e1fa847e3afcca2d3a7041f5d/qsmxt/${IMAGE_HASH}_$file"; then
        echo "[DEBUG] ${IMAGE_HASH}_$file exists in nectar swift object storage"
    else
        echo "[DEBUG] ${IMAGE_HASH}_$file does not exist yet in nectar swift"
        exit 2
    fi

done
