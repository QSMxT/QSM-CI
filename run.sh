#!/usr/bin/env bash
set -e

SCRIPT_PATH=$(realpath "$0")
SCRIPT_DIR=$(dirname "$SCRIPT_PATH")
USER_SCRIPT_DIR=$(realpath "$1")
PIPELINE_NAME="$(basename $USER_SCRIPT_DIR)"

echo "[DEBUG] SCRIPT_PATH $SCRIPT_PATH"
echo "[DEBUG] SCRIPT_DIR $SCRIPT_DIR"
echo "[DEBUG] USER_SCRIPT_DIR $USER_SCRIPT_DIR"
echo "[DEBUG] PIPELINE_NAME $PIPELINE_NAME"
echo "[DEBUG] BIDS_SUBJECT=$BIDS_SUBJECT"
echo "[DEBUG] BIDS_SESSION=$BIDS_SESSION"
echo "[DEBUG] BIDS_ACQUISITION=$BIDS_ACQUISITION"
echo "[DEBUG] BIDS_RUN=$BIDS_RUN"
echo "[DEBUG] INPUTS_JSON $INPUTS_JSON"

if [ -z "$1" ]; then
    echo "[ERROR] Argument needed to specify algorithm directory"
    exit 1
fi

if [ ! -d $USER_SCRIPT_DIR ]; then
    echo "[ERROR] Algorithm directory '$USER_SCRIPT_DIR' not found!"
    exit 1
fi
echo "[INFO] TESTING ALGORITHM '${PIPELINE_NAME}'"

# Determine the Docker image from the user script
IMAGE=$(grep '^#DOCKER_IMAGE=' "$USER_SCRIPT_DIR/main.sh" | cut -d= -f2)
if [ -z "$IMAGE" ]; then
    IMAGE="ubuntu:latest"
fi

# Check if the container is running
echo "[INFO] Preparing required Docker image $IMAGE with container name '${PIPELINE_NAME}'"
if [ "$(docker ps -q -f name=^/${PIPELINE_NAME}$)" ]; then
    echo "[INFO] Container named '${PIPELINE_NAME}' exists and is running. Stopping..."
    docker stop "$PIPELINE_NAME"
    sleep 5
fi

# Check if the container exists (whether stopped or running previously)
if docker inspect "$PIPELINE_NAME" &>/dev/null; then
    echo "[INFO] Container named '${PIPELINE_NAME}' exists. Removing..."
    docker rm -f "$PIPELINE_NAME"
fi

echo "[INFO] Setting up testing directories..."
OUTPUT_DIR="$SCRIPT_DIR/output/${PIPELINE_NAME}"
rm -rf "$OUTPUT_DIR"
mkdir -p "$OUTPUT_DIR"

UUID=$(uuidgen)
rm -rf /tmp/$UUID
mkdir -p /tmp/$UUID
trap "sudo rm -rf '/tmp/$UUID'" EXIT
cp -r bids /tmp/$UUID/bids
cp -r $USER_SCRIPT_DIR/*.* /tmp/$UUID/
cp $INPUTS_JSON /tmp/$UUID/inputs.json

echo "[INFO] Creating and starting the container '$PIPELINE_NAME' with image $IMAGE..."
docker run --rm --name "$PIPELINE_NAME" -d \
    -e BIDS_SUBJECT=$BIDS_SUBJECT \
    -e BIDS_SESSION=$BIDS_SESSION \
    -e BIDS_ACQUISITION=$BIDS_ACQUISITION \
    -e BIDS_RUN=$BIDS_RUN \
    -v "/tmp/$UUID:/qsmci" \
    -v "$OUTPUT_DIR:/qsmci/output" \
    "$IMAGE" tail -f /dev/null

echo "[INFO] Running $USER_SCRIPT_DIR/main.sh in container..."
docker exec "$PIPELINE_NAME" bash -c "cd /qsmci && chmod +x main.sh && ./main.sh"

echo "[INFO] Consolidating output in output/${PIPELINE_NAME}"
OUTPUT_FILES=$(ls output/${PIPELINE_NAME}/*.nii* 2> /dev/null | wc -l)
if [ "$OUTPUT_FILES" -eq 0 ]; then
    echo "[ERROR] Expected output not found! Check that the script correctly places one NIfTI file in 'output/'"
    exit 1
elif [ "$OUTPUT_FILES" -ne 1 ]; then
    echo "[ERROR] More than one output file found! '`ls output/${PIPELINE_NAME} -m`'"
    exit 1
else
    if [ ! -f output/${PIPELINE_NAME}/*.nii.gz ]; then
        gzip -f output/${PIPELINE_NAME}/*.nii
    fi
    if [ ! -f output/${PIPELINE_NAME}/${PIPELINE_NAME}.nii.gz ]; then
        mv output/${PIPELINE_NAME}/*.nii.gz output/${PIPELINE_NAME}/${PIPELINE_NAME}.nii.gz
    fi
fi

echo "[INFO] Completed run.sh"

