#!/usr/bin/env python

import argparse
import json
import os
import shutil
import docker
import glob
import subprocess
import logging

from tinyrange import TinyRange, PlanDefinition, BuildVMDefinition
from qsm_ci import parse_bids

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='[%(levelname)s] %(message)s'
)
logger = logging.getLogger(__name__)

def create_overlay(overlay_path, size_mb=1024):
    """Create an overlay file if it doesn't already exist."""
    if not os.path.exists(overlay_path):
        logger.info(f"Creating overlay at {overlay_path} with size {size_mb}MB")
        # Create an empty file of the specified size
        subprocess.run(['dd', 'if=/dev/zero', f'of={overlay_path}', 'bs=1M', f'count={size_mb}'])
        # Format the file as ext3 filesystem
        subprocess.run(['mkfs.ext3', '-F', overlay_path])
    else:
        logger.info(f"Using existing overlay at {overlay_path}")

def setup_environment(bids_dir, algo_dir, work_dir, container_engine):
    """Set up the environment and prepare directories for the algorithm execution."""
    work_dir = os.path.abspath(work_dir)
    algo_name = os.path.basename(os.path.normpath(algo_dir))

    if not os.path.exists(work_dir):
        os.makedirs(work_dir)
    elif os.listdir(work_dir):
        logger.warning(f"The working directory {work_dir} is not empty.")

    main_script_path = os.path.join(algo_dir, 'main.sh')
    if not os.path.isfile(main_script_path):
        raise FileNotFoundError(f"{main_script_path} does not exist.")

    with open(main_script_path, 'r') as file:
        main_script_content = file.read()

    docker_image = 'ubuntu:latest'
    apptainer_image = 'docker://ubuntu:latest'
    tinyrange_image = None
    tinyrange_resources = {
        'memory_mb': 2048,    # defaults
        'cpu_cores': 4,
        'storage_mb': 4096,
    }
    
    for line in main_script_content.splitlines():
        if line.startswith('#DOCKER_IMAGE='):
            docker_image = line.split('=')[1].strip()
        if line.startswith('#SINGULARITY_IMAGE='):
            apptainer_image = line.split('=')[1].strip()
        if line.startswith('#TINYRANGE_IMAGE='):
            tinyrange_image = line.split('=')[1].strip()
        elif line.startswith("#TINYRANGE_MEMORY_MB="):
            tinyrange_resources['memory_mb'] = int(line.split("=", 1)[1].strip())
        elif line.startswith("#TINYRANGE_CPU_CORES="):
            tinyrange_resources['cpu_cores'] = int(line.split("=", 1)[1].strip())
        elif line.startswith("#TINYRANGE_STORAGE_MB="):
            tinyrange_resources['storage_mb'] = int(line.split("=", 1)[1].strip())

    if container_engine == 'docker':
        client = docker.from_env()
        try:
            client.images.get(docker_image)
            logger.info(f"Docker image {docker_image} found locally.")
        except docker.errors.ImageNotFound:
            logger.info(f"Pulling Docker image {docker_image}...")
            client.images.pull(docker_image)
    elif container_engine == 'apptainer':
        if not apptainer_image:
            raise ValueError("Apptainer image is not specified in the algorithm script.")
        logger.info(f"Using Apptainer image: {apptainer_image}")
    elif container_engine == 'tinyrange':
        if not tinyrange_image:
            tinyrange_image = docker_image
        logger.info(f"Using TinyRange image: {tinyrange_image}")

    logger.info(f"Removing existing BIDS directory in {work_dir}...")
    work_bids_dir = os.path.join(work_dir, 'bids')
    if os.path.exists(work_bids_dir):
        shutil.rmtree(work_bids_dir)
    
    logger.info(f"Copying BIDS directory to {work_bids_dir}...")
    shutil.copytree(bids_dir, work_bids_dir)
    logger.info(f"Copied BIDS directory to {work_bids_dir}")

    logger.info(f"Copying algorithm directory to {work_dir}...")
    for item in os.listdir(algo_dir):
        s = os.path.join(algo_dir, item)
        d = os.path.join(work_dir, item)
        if os.path.isdir(s):
            shutil.copytree(s, d, dirs_exist_ok=True)
        else:
            shutil.copy2(s, d)

    return docker_image, apptainer_image, tinyrange_image, tinyrange_resources, algo_name, work_dir

def run_algo(client, docker_image, apptainer_image, tinyrange_image, tinyrange_resources, algo_name, bids_dir, work_dir, input_json, container_engine, overlay_path=None):
    bids_dir = os.path.abspath(bids_dir)

    with open(os.path.join(work_dir, 'inputs.json'), 'w') as json_file:
        json.dump(input_json, json_file, indent=4)

    if container_engine == 'docker':
        run_docker_algo(client, docker_image, algo_name, bids_dir, work_dir, input_json)
    elif container_engine == 'apptainer':
        run_apptainer_algo(apptainer_image, algo_name, bids_dir, work_dir, input_json, overlay_path)
    elif container_engine == 'tinyrange':
        run_tinyrange_algo(tinyrange_image, tinyrange_resources, algo_name, bids_dir, work_dir, input_json)

def run_docker_algo(client, docker_image, algo_name, bids_dir, work_dir, input_json):
    try:
        container = client.containers.get(algo_name)
        logger.info(f"Container with name {algo_name} already exists! Stopping and removing it...")
        container.stop()
        container.remove()
    except docker.errors.NotFound:
        pass

    subject = input_json.get('Subject')
    session = input_json.get('Session')
    acq = input_json.get('Acquisition')
    run = input_json.get('Run')

    logger.info(f"Creating container {algo_name}...")        
    volumes = {work_dir: {'bind': '/workdir', 'mode': 'rw'}}
    container = client.containers.create(
        image=docker_image,
        name=algo_name,
        volumes=volumes,
        working_dir='/workdir',
        command=["./main.sh"],
        auto_remove=False,
        environment={
            'BIDS_SUBJECT': subject,
            'BIDS_SESSION': session,
            'BIDS_ACQUISITION': acq,
            'BIDS_RUN': run,
            'PIPELINE_NAME': algo_name,
            'INPUTS_JSON': '/workdir/inputs.json'
        }
    )
    logger.info(f"Container {algo_name} created successfully.")

    if container.status != 'running':
        container.start()

    for log in container.logs(stream=True):
        print(log.decode().strip())

    exit_code = container.wait()
    handle_output(work_dir, algo_name, input_json)

def run_tinyrange_algo(tinyrange_image, tinyrange_resources, algo_name, bids_dir, work_dir, input_json):
    """Run algorithm using TinyRange VM"""
    # Initialize TinyRange client
    client = TinyRange()
    
    # Create VM definition with parsed resources
    vm = BuildVMDefinition(
        cpu_cores=tinyrange_resources['cpu_cores'],
        memory_mb=tinyrange_resources['memory_mb'],
        storage_size=tinyrange_resources['storage_mb']
    )
    
    # Determine whether to use TinyRange native plan or Docker OCI image
    if '@' in tinyrange_image:
        # Use TinyRange native plan (e.g., ubuntu@noble)  
        logger.info(f"Using TinyRange native plan: {tinyrange_image}")
        
        # Create plan with essential packages only
        plan = PlanDefinition(tinyrange_image)
        # Add only absolutely essential packages
        plan.add_search("bash")
        
        # Add plan to VM
        vm.add_plan_directive(plan)
    else:
        # Use Docker OCI image (e.g., ubuntu:latest, vnmd/qsmxt_6.2.0:20231012)
        logger.info(f"Using TinyRange Docker OCI image: {tinyrange_image}")
        
        # Parse Docker image string to extract registry, image, and tag
        if '/' in tinyrange_image and '.' in tinyrange_image.split('/')[0]:
            # Has explicit registry (e.g., quay.io/vnmd/qsmxt_6.2.0:20231012)
            if ':' in tinyrange_image:
                image_part, tag = tinyrange_image.rsplit(':', 1)
            else:
                image_part, tag = tinyrange_image, "latest"
            
            registry, image = image_part.split('/', 1)
        else:
            # Docker Hub or user/image format (e.g., ubuntu:latest, vnmd/qsmxt_6.2.0:20231012)
            if ':' in tinyrange_image:
                image_part, tag = tinyrange_image.rsplit(':', 1)
            else:
                image_part, tag = tinyrange_image, "latest"
            
            registry = "docker.io"
            if '/' in image_part:
                # User/organization image (e.g., vnmd/qsmxt_6.2.0)
                image = image_part
            else:
                # Official image (e.g., ubuntu) - prepend 'library/'
                image = f"library/{image_part}"
        
        # Fetch Docker image and add to VM
        vm.add_fetch_oci_image(registry, image, tag)
    
    logger.info("TinyRange VM Configuration:")
    logger.info(f"  CPU Cores: {tinyrange_resources['cpu_cores']}")
    logger.info(f"  Memory MB: {tinyrange_resources['memory_mb']}")
    logger.info(f"  Storage MB: {tinyrange_resources['storage_mb']}")
    
    # Add algorithm files to VM
    main_sh_path = os.path.join(work_dir, 'main.sh')
    with open(main_sh_path, 'r') as f:
        main_sh_content = f.read()
    
    # Strip shebang line to work around TinyRange bug
    lines = main_sh_content.split('\n')
    if lines[0].startswith('#!'):
        main_sh_content = '\n'.join(lines[1:])
        logger.info("Stripped shebang line from main.sh")
    
    # Convert apt/apk commands if needed  
    if tinyrange_image and "ubuntu" not in tinyrange_image.lower():
        main_sh_content = main_sh_content.replace('apt-get update', 'apk update')
        main_sh_content = main_sh_content.replace('apt-get install wget -y', 'apk add wget')
        main_sh_content = main_sh_content.replace('apt-get install', 'apk add')
        logger.info("Converted apt commands to apk for Alpine Linux")
    
    vm.add_file("main.sh", main_sh_content.encode('utf-8'))
    
    # Add other algorithm files from work_dir
    for item in os.listdir(work_dir):
        if item == "main.sh" or item == "inputs.json" or item == "bids":
            continue
        
        item_path = os.path.join(work_dir, item)
        if os.path.isfile(item_path):
            try:
                with open(item_path, 'r', encoding='utf-8') as f:
                    content = f.read()
                
                # Strip shebang if present
                lines = content.split('\n')
                if lines and lines[0].startswith('#!'):
                    content = '\n'.join(lines[1:])
                
                vm.add_file(item, content.encode('utf-8'))
                logger.info(f"Added {item} to VM")
            except Exception as e:
                logger.warning(f"Failed to add {item}: {e}")
    
    # Add inputs.json
    inputs_path = os.path.join(work_dir, 'inputs.json')
    with open(inputs_path, 'r') as f:
        inputs_content = f.read()
    vm.add_file("inputs.json", inputs_content.encode('utf-8'))
    
    # Add BIDS data files
    logger.info("Adding BIDS data files to VM...")
    files_to_add = set()
    
    if 'mask' in input_json and input_json['mask']:
        files_to_add.add(input_json['mask'])
    
    for file_list_key in ['mag_nii', 'phase_nii', 'mag_json', 'phase_json']:
        if file_list_key in input_json:
            for file_path in input_json[file_list_key]:
                files_to_add.add(file_path)
    
    # Add each BIDS file to the VM
    for rel_path in files_to_add:
        if rel_path.startswith('bids/challenges/bids/'):
            # Convert to absolute host path
            bids_rel_path = rel_path.replace('bids/challenges/bids/', '')
            host_file_path = os.path.join(bids_dir, bids_rel_path)
            
            # VM path (just the relative path from bids root)
            vm_file_path = bids_rel_path
            
            if os.path.exists(host_file_path):
                vm.add_local_file(vm_file_path, os.path.abspath(host_file_path))
            else:
                logger.warning(f"BIDS file not found: {host_file_path}")
    
    logger.info(f"Added {len(files_to_add)} BIDS files to VM")
    
    # Set the output file for extraction
    vm.set_output_file("out.nii.gz")
    
    # Run the algorithm
    vm.add_command("bash main.sh")
    
    logger.info(f"Building and running TinyRange VM for {algo_name}...")
    
    # Build and execute the VM
    try:
        artifact = client.build_def(vm)
        logger.info("TinyRange VM execution completed successfully")
    except Exception as e:
        raise RuntimeError(f"TinyRange VM execution failed: {e}")
    
    # Extract output file from VM
    output_dir = os.path.join(work_dir, 'output')
    os.makedirs(output_dir, exist_ok=True)
    output_file = os.path.join(output_dir, 'chimap.nii.gz')
    
    try:
        logger.info("Extracting output file from TinyRange VM...")
        with open(output_file, "wb") as f:
            f.write(artifact.open_default("rb").read())
        logger.info(f"Output file extracted to {output_file}")
    except Exception as e:
        logger.warning(f"Failed to extract output file: {e}")
        # Not fatal - algorithm may have created output differently
    
    # Call handle_output for consistency with other container engines
    try:
        handle_output(work_dir, algo_name, input_json)
    except Exception as e:
        logger.warning(f"Output handling failed: {e}")
        # Don't fail the whole process for output handling issues

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

    subject = input_json.get('Subject')
    session = input_json.get('Session')
    acq = input_json.get('Acquisition')
    run = input_json.get('Run')

    env_vars = {
        'BIDS_SUBJECT': subject,
        'BIDS_SESSION': session,
        'BIDS_ACQUISITION': acq,
        'BIDS_RUN': run,
        'PIPELINE_NAME': algo_name,
        'INPUTS_JSON': '/workdir/inputs.json'
    }

    for var, value in env_vars.items():
        command.extend(['--env', f"{var}={value}"])

    command.extend([apptainer_image, './main.sh'])

    logger.info(f"Running Apptainer command: {' '.join(command)}")

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

    # gunzip any gzipped files
    for i, nifti_file in enumerate(nifti_files):
        if nifti_file.endswith('.gz'):
            logger.info(f"Unzipping {nifti_file}")
            subprocess.run(['gunzip', nifti_file])
            nifti_files[i] = nifti_file.replace('.gz', '')

    if not nifti_files:
        logger.warning(f"No NIfTI files found in {output_dir}.")
    else:
        for nifti_file in nifti_files:
            dest_dir = construct_bids_derivative_path(input_json, algo_name, work_dir)
            os.makedirs(dest_dir, exist_ok=True)
            dest_file = construct_bids_filename(input_json, nifti_file)
            shutil.move(nifti_file, os.path.join(dest_dir, dest_file))
            logger.info(f"Moved {nifti_file} to {os.path.join(dest_dir, dest_file)}")

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
    parser.add_argument('algo_dir', type=str, help='Path to the QSM algorithm')
    parser.add_argument('bids_dir', type=str, help='Path to the BIDS directory')
    parser.add_argument('work_dir', type=str, help='Path to the working directory')
    parser.add_argument('inputs_json', type=str, nargs='?', help='Path to the inputs.json file')
    parser.add_argument('--container_engine', type=str, default='docker', choices=['docker', 'apptainer', 'tinyrange'], help='Choose between Docker, Apptainer, or TinyRange')
    parser.add_argument('--overlay', type=str, help='Path to overlay image (for Apptainer)')
    parser.add_argument('--overlay_size', type=int, default=4096, help='Size of overlay in MB (if using Apptainer)')
    args = parser.parse_args()
    logger.info(f"bids_dir: {args.bids_dir}")
    logger.info(f"algo_dir: {args.algo_dir}")
    logger.info(f"work_dir: {args.work_dir}")

    client = None
    docker_image, apptainer_image, tinyrange_image, tinyrange_resources, algo_name, work_dir = setup_environment(args.bids_dir, args.algo_dir, args.work_dir, args.container_engine)

    if args.container_engine == 'apptainer' and args.overlay:
        create_overlay(args.overlay, size_mb=args.overlay_size)

    if args.container_engine == 'docker':
        client = docker.from_env()

    if not args.inputs_json:
        for input_json in parse_bids.parse_bids_directory(args.bids_dir):
            run_algo(client, docker_image, apptainer_image, tinyrange_image, tinyrange_resources, algo_name, args.bids_dir, work_dir, input_json, args.container_engine, args.overlay)
    else:
        with open(args.inputs_json, 'r') as json_file:
            input_json = json.load(json_file)
        run_algo(client, docker_image, apptainer_image, tinyrange_image, tinyrange_resources, algo_name, args.bids_dir, work_dir, input_json, args.container_engine, args.overlay)

    if client and args.container_engine == 'docker':
        container = client.containers.get(algo_name)
        container.remove()
        logger.info(f"Container {algo_name} has been removed.")

if __name__ == '__main__':
    main()
