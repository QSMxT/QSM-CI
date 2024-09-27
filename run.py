import argparse
import json
import os
import shutil
import docker
import glob
import subprocess
from utils import parse_bids

def setup_environment(bids_dir, algo_dir, work_dir):
    # Ensure work_dir is an absolute path
    work_dir = os.path.abspath(work_dir)

    # Get the algo_name (name of the final folder)
    algo_name = os.path.basename(os.path.normpath(algo_dir))

    # Create the output working directory (if it already exists, throw a warning only if it's not empty)
    if not os.path.exists(work_dir):
        os.makedirs(work_dir)
    elif os.listdir(work_dir):
        print(f"Warning: The working directory {work_dir} is not empty.")

    # Read the text content of {algo_dir}/main.sh
    main_script_path = os.path.join(algo_dir, 'main.sh')
    if not os.path.isfile(main_script_path):
        raise FileNotFoundError(f"{main_script_path} does not exist.")

    with open(main_script_path, 'r') as file:
        main_script_content = file.read()

    # Determine the docker_image to use by reading the line with #DOCKER_IMG=... (default 'ubuntu:latest')
    docker_image = 'ubuntu:latest'
    for line in main_script_content.splitlines():
        if line.startswith('#DOCKER_IMAGE='):
            docker_image = line.split('=')[1].strip()
            break

    # Pull the docker_image if we do not already have it
    client = docker.from_env()
    try:
        client.images.get(docker_image)
        print(f"Docker image {docker_image} found locally.")
    except docker.errors.ImageNotFound:
        print(f"Pulling Docker image {docker_image}...")
        client.images.pull(docker_image)

    # Copy the BIDS directory into the work_dir
    work_bids_dir = os.path.join(work_dir, 'bids')
    if os.path.exists(work_bids_dir):
        shutil.rmtree(work_bids_dir)
    shutil.copytree(bids_dir, work_bids_dir)

    # Copy algorithm files into the work_dir
    for item in os.listdir(algo_dir):
        s = os.path.join(algo_dir, item)
        d = os.path.join(work_dir, item)
        if os.path.isdir(s):
            shutil.copytree(s, d, dirs_exist_ok=True)
        else:
            shutil.copy2(s, d)

    return client, docker_image, algo_name, work_dir

def run_algo(client, docker_image, algo_name, work_dir, input_json):
    # Write the input JSON to the work directory
    with open(os.path.join(work_dir, 'inputs.json'), 'w') as json_file:
        json.dump(input_json, json_file, indent=4)

    # Check if a container with the same name already exists
    try:
        container = client.containers.get(algo_name)
        print(f"Container with name {algo_name} already exists.")
    except docker.errors.NotFound:
        print(f"No existing container with name {algo_name} found. Proceeding to create a new one.")

        # Prepare environment variables from the host environment
        environment = {}
        
        if 'BIDS_SUBJECT' in os.environ:
            print(f"Passing BIDS_SUBJECT={os.environ['BIDS_SUBJECT']}")
            environment['BIDS_SUBJECT'] = os.environ['BIDS_SUBJECT']
        if 'BIDS_SESSION' in os.environ:
            print(f"Passing BIDS_SESSION={os.environ['BIDS_SESSION']}")
            environment['BIDS_SESSION'] = os.environ['BIDS_SESSION']
        if 'BIDS_ACQUISITION' in os.environ:
            print(f"Passing BIDS_ACQUISITION={os.environ['BIDS_ACQUISITION']}")
            environment['BIDS_ACQUISITION'] = os.environ['BIDS_ACQUISITION']
        if 'BIDS_RUN' in os.environ:
            print(f"Passing BIDS_RUN={os.environ['BIDS_RUN']}")
            environment['BIDS_RUN'] = os.environ['BIDS_RUN']

        # Create the docker container using docker_image and call it the algo_name
        container = client.containers.create(
            image=docker_image,
            name=algo_name,
            volumes={work_dir: {'bind': '/workdir', 'mode': 'rw'}},
            working_dir='/workdir',
            command=["./main.sh"],  # Execute the main.sh script
            environment=environment,  # Pass the environment variables
            auto_remove=False
        )
        if container:
            print(f"Container {algo_name} created successfully with ID: {container.id}")
        else:
            print(f"Failed to create the container {algo_name}.")

    # Start the container
    if container.status != 'running':
        print(f"Starting container {algo_name}...")
        container.start()
    else:
        print(f"Container already running")

    # Stream logs from the container to monitor the process
    print(f"Streaming logs from container {algo_name}...")
    for log in container.logs(stream=True):
        print(log.decode().strip())
    print("Log finished!")

    # Wait for the container to finish
    exit_code = container.wait()
    print(f"Container {algo_name} exited with code {exit_code['StatusCode']}")
    if exit_code != 0:
        raise RuntimeError(f"Container {algo_name} exited with code {exit_code['StatusCode']}")

    # Change ownership of files in the output directory to the current user
    subprocess.run(['sudo', 'chown', '-R', f"{os.getuid()}:{os.getgid()}", os.path.join(work_dir, 'output')])

    # Move the NIfTI file to the correct BIDS directory
    output_dir = os.path.join(work_dir, 'output')
    nifti_files = glob.glob(os.path.join(output_dir, "*.nii*"))  # Find .nii and .nii.gz files

    if not nifti_files:
        print(f"No NIfTI files found in {output_dir}.")
    else:
        for nifti_file in nifti_files:
            dest_dir = construct_bids_derivative_path(input_json, algo_name, work_dir)
            os.makedirs(dest_dir, exist_ok=True)
            dest_file = construct_bids_filename(input_json, nifti_file)
            shutil.move(nifti_file, os.path.join(dest_dir, dest_file))
            print(f"Moved {nifti_file} to {os.path.join(dest_dir, dest_file)}")

    return container

def construct_bids_derivative_path(input_json, algo_name, work_dir):
    # Construct the path for the derivatives
    subject = input_json.get('Subject')
    session = input_json.get('Session')
    
    path = os.path.join(work_dir, 'bids', 'derivatives', algo_name, f"sub-{subject}")
    
    if session:
        path = os.path.join(path, f"ses-{session}")
    
    path = os.path.join(path, 'anat')
    
    return path

def construct_bids_filename(input_json, nifti_file):
    # Construct the filename based on the BIDS format
    subject = input_json.get('Subject')
    session = input_json.get('Session')
    acq = input_json.get('Acq')
    run = input_json.get('Run')
    
    filename = f"sub-{subject}"
    
    if session:
        filename += f"_ses-{session}"
    if acq:
        filename += f"_acq-{acq}"
    if run:
        filename += f"_run-{run}"
    
    filename += f"_Chimap." + ".".join(nifti_file.split('.')[1:])
    
    return filename


def main():
    # Parse command-line arguments
    parser = argparse.ArgumentParser(description='Run a QSM algorithm on BIDS data using a working directory.')
    parser.add_argument('bids_dir', type=str, help='Path to the BIDS directory')
    parser.add_argument('algo_dir', type=str, help='Path to the QSM algorithm')
    parser.add_argument('work_dir', type=str, help='Path to the working directory')
    parser.add_argument('inputs_json', type=str, nargs='?', help='Path to the inputs.json file')
    args = parser.parse_args()

    # Set up the environment once
    client, docker_image, algo_name, work_dir = setup_environment(args.bids_dir, args.algo_dir, args.work_dir)

    if not args.inputs_json:
        # Loop through each input_json generated by parse_bids
        for input_json in parse_bids.parse_bids_directory(args.bids_dir):
            run_algo(client, docker_image, algo_name, work_dir, input_json)
    else:
        # Run once with the provided inputs_json
        with open(args.inputs_json, 'r') as json_file:
            input_json = json.load(json_file)
        run_algo(client, docker_image, algo_name, work_dir, input_json)

    # Optionally remove the container after all processing
    container = client.containers.get(algo_name)
    container.remove()
    print(f"Container {algo_name} has been removed.")

if __name__ == '__main__':
    main()

