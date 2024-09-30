import argparse
import json
import os
import shutil
import docker
import glob
import subprocess

from qsm_ci import parse_bids

def create_overlay(overlay_path, size_mb=1024):
    """Create an overlay file if it doesn't already exist."""
    if not os.path.exists(overlay_path):
        print(f"Creating overlay at {overlay_path} with size {size_mb}MB")
        # Create an empty file of the specified size
        subprocess.run(['dd', 'if=/dev/zero', f'of={overlay_path}', 'bs=1M', f'count={size_mb}'])
        # Format the file as ext3 filesystem
        subprocess.run(['mkfs.ext3', '-F', overlay_path])
    else:
        print(f"Using existing overlay at {overlay_path}")

def setup_environment(bids_dir, algo_dir, work_dir, container_system):
    """Set up the environment and prepare directories for the algorithm execution."""
    work_dir = os.path.abspath(work_dir)
    algo_name = os.path.basename(os.path.normpath(algo_dir))

    if not os.path.exists(work_dir):
        os.makedirs(work_dir)
    elif os.listdir(work_dir):
        print(f"Warning: The working directory {work_dir} is not empty.")

    main_script_path = os.path.join(algo_dir, 'main.sh')
    if not os.path.isfile(main_script_path):
        raise FileNotFoundError(f"{main_script_path} does not exist.")

    with open(main_script_path, 'r') as file:
        main_script_content = file.read()

    docker_image = 'ubuntu:latest'
    apptainer_image = 'docker://ubuntu:latest'
    for line in main_script_content.splitlines():
        if line.startswith('#DOCKER_IMAGE='):
            docker_image = line.split('=')[1].strip()
        if line.startswith('#SINGULARITY_IMAGE='):
            apptainer_image = line.split('=')[1].strip()

    if container_system == 'docker':
        client = docker.from_env()
        try:
            client.images.get(docker_image)
            print(f"Docker image {docker_image} found locally.")
        except docker.errors.ImageNotFound:
            print(f"Pulling Docker image {docker_image}...")
            client.images.pull(docker_image)
    else:
        if not apptainer_image:
            raise ValueError("Apptainer image is not specified in the algorithm script.")
        print(f"Using Apptainer image: {apptainer_image}")

    work_bids_dir = os.path.join(work_dir, 'bids')
    if os.path.exists(work_bids_dir):
        shutil.rmtree(work_bids_dir)
    shutil.copytree(bids_dir, work_bids_dir)
    print(f"Copied BIDS directory to {work_bids_dir}")

    for item in os.listdir(algo_dir):
        s = os.path.join(algo_dir, item)
        d = os.path.join(work_dir, item)
        if os.path.isdir(s):
            shutil.copytree(s, d, dirs_exist_ok=True)
        else:
            shutil.copy2(s, d)

    return docker_image, apptainer_image, algo_name, work_dir

def run_algo(client, docker_image, apptainer_image, algo_name, bids_dir, work_dir, input_json, container_system, overlay_path=None):
    bids_dir = os.path.abspath(bids_dir)

    with open(os.path.join(work_dir, 'inputs.json'), 'w') as json_file:
        json.dump(input_json, json_file, indent=4)

    if container_system == 'docker':
        run_docker_algo(client, docker_image, algo_name, bids_dir, work_dir, input_json)
    else:
        run_apptainer_algo(apptainer_image, algo_name, bids_dir, work_dir, input_json, overlay_path)

def run_docker_algo(client, docker_image, algo_name, bids_dir, work_dir, input_json):
    try:
        container = client.containers.get(algo_name)
        print(f"Container with name {algo_name} already exists.")
    except docker.errors.NotFound:
        print(f"No existing container with name {algo_name} found. Proceeding to create a new one.")
        volumes = {work_dir: {'bind': '/workdir', 'mode': 'rw'}}
        container = client.containers.create(
            image=docker_image,
            name=algo_name,
            volumes=volumes,
            working_dir='/workdir',
            command=["./main.sh"],
            auto_remove=False
        )
        print(f"Container {algo_name} created successfully.")

    if container.status != 'running':
        container.start()

    for log in container.logs(stream=True):
        print(log.decode().strip())

    exit_code = container.wait()
    handle_output(work_dir)

def run_apptainer_algo(apptainer_image, algo_name, bids_dir, work_dir, input_json, overlay_path=None):
    main_script_path = os.path.join(work_dir, 'main.sh')
    if not os.path.isfile(main_script_path):
        raise FileNotFoundError(f"{main_script_path} does not exist in {work_dir}.")

    subprocess.run(['chmod', '+x', main_script_path])

    command = [
        'apptainer', 'run',
        '--bind', f"{work_dir}:/workdir",
        '--pwd', '/workdir',
        '--fakeroot'
    ]

    if overlay_path:
        command.extend(['--overlay', overlay_path])

    command.extend([apptainer_image, './main.sh'])

    print(f"Running Apptainer command: {' '.join(command)}")

    process = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    for line in process.stdout:
        print(line.decode().strip())                        

    process.wait()
    if process.returncode != 0:
        raise RuntimeError(f"Apptainer run failed with code {process.returncode}")

    handle_output(work_dir, algo_name, input_json)

def handle_output(work_dir, algo_name, input_json):
    subprocess.run(['sudo', 'chown', '-R', f"{os.getuid()}:{os.getgid()}", os.path.join(work_dir, 'output')])

    output_dir = os.path.join(work_dir, 'output')
    nifti_files = glob.glob(os.path.join(output_dir, "*.nii*"))

    if not nifti_files:
        print(f"No NIfTI files found in {output_dir}.")
    else:
        for nifti_file in nifti_files:
            dest_dir = construct_bids_derivative_path(input_json, algo_name, work_dir)
            os.makedirs(dest_dir, exist_ok=True)
            dest_file = construct_bids_filename(input_json, nifti_file)
            shutil.move(nifti_file, os.path.join(dest_dir, dest_file))
            print(f"Moved {nifti_file} to {os.path.join(dest_dir, dest_file)}")

def construct_bids_derivative_path(input_json, algo_name, work_dir):
    subject = input_json.get('Subject')
    session = input_json.get('Session')

    path = os.path.join(work_dir, 'bids', 'derivatives', algo_name, f"sub-{subject}")

    if session:
        path = os.path.join(path, f"ses-{session}")

    path = os.path.join(path, 'anat')

    return path

def construct_bids_filename(input_json, nifti_file):
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
    parser = argparse.ArgumentParser(description='Run a QSM algorithm on BIDS data using a working directory.')
    parser.add_argument('bids_dir', type=str, help='Path to the BIDS directory')
    parser.add_argument('algo_dir', type=str, help='Path to the QSM algorithm')
    parser.add_argument('work_dir', type=str, help='Path to the working directory')
    parser.add_argument('inputs_json', type=str, nargs='?', help='Path to the inputs.json file')
    parser.add_argument('--container_system', type=str, default='docker', choices=['docker', 'apptainer'], help='Choose between Docker or Apptainer')
    parser.add_argument('--overlay', type=str, help='Path to overlay image (for Apptainer)')
    parser.add_argument('--overlay_size', type=int, default=1024, help='Size of overlay in MB (if using Apptainer)')
    args = parser.parse_args()

    client = None
    docker_image, apptainer_image, algo_name, work_dir = setup_environment(args.bids_dir, args.algo_dir, args.work_dir, args.container_system)

    if args.container_system == 'apptainer' and args.overlay:
        create_overlay(args.overlay, size_mb=args.overlay_size)

    if args.container_system == 'docker':
        client = docker.from_env()

    if not args.inputs_json:
        for input_json in parse_bids.parse_bids_directory(args.bids_dir):
            run_algo(client, docker_image, apptainer_image, algo_name, args.bids_dir, work_dir, input_json, args.container_system, args.overlay)
    else:
        with open(args.inputs_json, 'r') as json_file:
            input_json = json.load(json_file)
        run_algo(client, docker_image, apptainer_image, algo_name, args.bids_dir, work_dir, input_json, args.container_system, args.overlay)

    if client and args.container_system == 'docker':
        container = client.containers.get(algo_name)
        container.remove()
        print(f"Container {algo_name} has been removed.")

if __name__ == '__main__':
    main()
