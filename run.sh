#!/usr/bin/env bash

USER_SCRIPT="$1"
DEFAULT_IMAGE="ubuntu:latest"
PIPELINE_NAME="$(basename $USER_SCRIPT .sh)"

if [ -z "$1" ]; then
    echo "[ERROR] Argument needed to specify algorithm script file"
    exit 1
fi

if [ ! -f $USER_SCRIPT ]; then
    echo "[ERROR] Algorithm script file '$USER_SCRIPT' not found!"
    exit 1
fi
echo "[INFO] TESTING PIPELINE '${PIPELINE_NAME}'"

# Determine the Docker image from the user script
IMAGE=$(grep '^#DOCKER_IMAGE=' "$USER_SCRIPT" | cut -d= -f2)
if [ -z "$IMAGE" ]; then
    IMAGE="$DEFAULT_IMAGE"
fi

# Prepare the output directory
OUTPUT_DIR="$(pwd)/recons/${PIPELINE_NAME}"
rm -rf "$OUTPUT_DIR"
mkdir -p "$OUTPUT_DIR"
echo "[INFO] Preparing required Docker image $IMAGE with container name '${PIPELINE_NAME}'"

# Check if the container is running
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

echo "[INFO] Setting up copy of BIDS directory..."
rm -rf bids-copy
cp -r bids bids-copy

echo "[INFO] Creating and starting the container '$PIPELINE_NAME' with image $IMAGE..."
docker run --rm --name "$PIPELINE_NAME" -d \
    -v "$(pwd)/bids-copy:/tmp/bids" \
    -v "$OUTPUT_DIR:/tmp/output" \
    "$IMAGE" tail -f /dev/null

# Ensure /tmp/output exists and is writable inside the container
docker exec "$PIPELINE_NAME" mkdir -p /tmp/output
docker exec "$PIPELINE_NAME" chmod 777 /tmp/output

# Run the user script in the container
echo "[INFO] Running $USER_SCRIPT in container..."
docker cp "$USER_SCRIPT" "$PIPELINE_NAME":/tmp/$(basename $USER_SCRIPT)
docker exec "$PIPELINE_NAME" bash -c "cd /tmp && chmod +x $(basename $USER_SCRIPT) && ./$(basename $USER_SCRIPT)"

echo "[INFO] Consolidating outputs in recons/${PIPELINE_NAME}"
OUTPUT_FILES=$(ls recons/${PIPELINE_NAME}/*.nii* 2> /dev/null | wc -l)
if [ "$OUTPUT_FILES" -eq 0 ]; then
    echo "[ERROR] Expected output not found! Check that the script correctly places one NIfTI file in 'output/'"
    exit 1
elif [ "$OUTPUT_FILES" -ne 1 ]; then
    echo "[ERROR] More than one output file found! '`ls recons/${PIPELINE_NAME} -m`'"
    exit 1
else
    if [ ! -f recons/${PIPELINE_NAME}/*.nii.gz ]; then
        gzip -f recons/${PIPELINE_NAME}/*.nii
    fi
    mv recons/${PIPELINE_NAME}/*.nii.gz recons/${PIPELINE_NAME}/${PIPELINE_NAME}.nii.gz
fi

