#!/usr/bin/env python

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
        print(f"[INFO] Creating overlay at {overlay_path} with size {size_mb}MB")
        # Create an empty file of the specified size
        subprocess.run(['dd', 'if=/dev/zero', f'of={overlay_path}', 'bs=1M', f'count={size_mb}'])
        # Format the file as ext3 filesystem
        subprocess.run(['mkfs.ext3', '-F', overlay_path])
    else:
        print(f"[INFO] Using existing overlay at {overlay_path}")

def setup_environment(bids_dir, algo_dir, work_dir, container_engine):
    """Set up the environment and prepare directories for the algorithm execution."""
    work_dir = os.path.abspath(work_dir)
    algo_name = os.path.basename(os.path.normpath(algo_dir))

    if not os.path.exists(work_dir):
        os.makedirs(work_dir)
    elif os.listdir(work_dir):
        print(f"[WARNING] The working directory {work_dir} is not empty.")

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

    if container_engine == 'docker':
        client = docker.from_env()
        try:
            client.images.get(docker_image)
            print(f"[INFO] Docker image {docker_image} found locally.")
        except docker.errors.ImageNotFound:
            print(f"[INFO] Pulling Docker image {docker_image}...")
            client.images.pull(docker_image)
    else:
        if not apptainer_image:
            raise ValueError("Apptainer image is not specified in the algorithm script.")
        print(f"[INFO] Using Apptainer image: {apptainer_image}")

    print(f"[INFO] Removing existing BIDS directory in {work_dir}...")
    work_bids_dir = os.path.join(work_dir, 'bids')
    if os.path.exists(work_bids_dir):
        shutil.rmtree(work_bids_dir)

    print(f"[INFO] Copying BIDS directory to {work_bids_dir}...")
    shutil.copytree(bids_dir, work_bids_dir)
    
    # Debug BIDS directory contents
    print("[DEBUG] Contents of work_bids_dir after copy:")
    subprocess.run(['ls', '-R', work_bids_dir])

    print(f"[INFO] Copying algorithm directory to {work_dir}...")
    for item in os.listdir(algo_dir):
        s = os.path.join(algo_dir, item)
        d = os.path.join(work_dir, item)
        if os.path.isdir(s):
            shutil.copytree(s, d, dirs_exist_ok=True)
        else:
            shutil.copy2(s, d)

    return docker_image, apptainer_image, algo_name, work_dir

def run_algo(client, docker_image, apptainer_image, algo_name, bids_dir, work_dir, input_json, container_engine, overlay_path=None):
    bids_dir = os.path.abspath(bids_dir)

    print(f"[DEBUG] Input JSON contents:")
    print(json.dumps(input_json, indent=2))

    with open(os.path.join(work_dir, 'inputs.json'), 'w') as json_file:
        json.dump(input_json, json_file, indent=4)

    if container_engine == 'docker':
         # Return the actual container name used
        return run_docker_algo(client, docker_image, algo_name, bids_dir, work_dir, input_json)
    else:
        run_apptainer_algo(apptainer_image, algo_name, bids_dir, work_dir, input_json, overlay_path)

def run_docker_algo(client, docker_image, algo_name, bids_dir, work_dir, input_json):
    subject = input_json.get('Subject')
    session = input_json.get('Session')
    acq = input_json.get('Acquisition')  
    run = input_json.get('Run')

    # Build unique container name that includes all relevant info
    unique_name = algo_name
    if acq:
        unique_name += f"_acq-{acq}"
    if subject:
        unique_name += f"_sub-{subject}"
    if session:
        unique_name += f"_ses-{session}"
    if run:
        unique_name += f"_run-{run}"

    # Clean up any existing container with this exact name
    try:
        container = client.containers.get(unique_name)
        print(f"[INFO] Found existing container {unique_name}, removing...")
        container.stop()
        container.remove()
    except docker.errors.NotFound:
        pass

    print(f"[INFO] Creating container {unique_name}...")
    volumes = {work_dir: {'bind': '/workdir', 'mode': 'rw'}}
    container = client.containers.create(
        image=docker_image,
        name=unique_name,
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
    print(f"[INFO] Container {unique_name} created successfully.")

    # ---- Start container and block until it finishes ----
    container.start()
    print(f"[INFO] Running container {unique_name}...")

    for line in container.logs(stream=True, follow=True):
        line = line.decode(errors="ignore").strip()
        print(line)

    # ---- Wait for container exit ----
    exit_code = container.wait()
    print(f"[INFO] Container {unique_name} exited with code {exit_code['StatusCode']}")

    if exit_code['StatusCode'] != 0:
        logs = container.logs().decode(errors="ignore").split('\n')
        last_logs = '\n'.join(logs[-20:])
        raise RuntimeError(f"Container {unique_name} failed with exit code {exit_code['StatusCode']}\nLast logs:\n{last_logs}")

    # ---- Handle output (only after full completion) ----
    handle_output(work_dir, unique_name, input_json)

    # ---- Cleanup container ----
    try:
        container.remove()
        print(f"[INFO] Container {unique_name} removed successfully.")
    except Exception as e:
        print(f"[WARNING] Could not remove container {unique_name}: {e}")

    print(f"[INFO] Algorithm {algo_name} completed for subject {subject}, acquisition {acq}.")
    return unique_name


def run_apptainer_algo(apptainer_image, algo_name, bids_dir, work_dir, input_json, overlay_path=None):
    main_script_path = os.path.join(work_dir, 'main.sh')
    if not os.path.isfile(main_script_path):
        raise FileNotFoundError(f"{main_script_path} does not exist in {work_dir}.")

    subprocess.run(['chmod', '+x', main_script_path])

    command = [
        'apptainer', 'run',
        '--bind', f"{work_dir}:/workdir",
        '--pwd', '/workdir'
    ]
    
    # On HPC: use --fakeroot when overlay is enabled
    if '/scratch' in work_dir or os.environ.get('SLURM_JOBID'):
        print("[INFO] HPC environment detected")
        if overlay_path:
            print("[INFO] Overlay enabled -> using --fakeroot for Apptainer")
            command.extend(['--fakeroot', '--overlay', overlay_path])
        else:
            print("[INFO] No overlay - using --cleanenv")
            command.append('--cleanenv')
    else:
        print("[INFO] Local environment - using --fakeroot")
        command.append('--fakeroot')
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

    print(f"[INFO] Running Apptainer command: {' '.join(command)}")

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
        print(f"[ERROR] No NIfTI files found in {output_dir}.")
        raise FileNotFoundError(f"No NIfTI files found in {output_dir}.")
    else:
        # gunzip any gzipped files
        for i, nifti_file in enumerate(nifti_files):
            if nifti_file.endswith('.gz'):
                print(f"[INFO] Unzipping {nifti_file}")
                subprocess.run(['gunzip', nifti_file])
                nifti_files[i] = nifti_file.replace('.gz', '')
        for nifti_file in nifti_files:
            dest_dir = construct_bids_derivative_path(input_json, algo_name, work_dir)
            os.makedirs(dest_dir, exist_ok=True)
            dest_file = construct_bids_filename(input_json, nifti_file)
            shutil.move(nifti_file, os.path.join(dest_dir, dest_file))
            print(f"[INFO] Moved {nifti_file} to {os.path.join(dest_dir, dest_file)}")

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
    acq = input_json.get('Acquisition')  
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

def parse_run_selection(run_str, valid_results):
    """Parse run selection string to actual run numbers"""
    runs = []
    
    for part in run_str.split(','):
        part = part.strip()
        if '-' in part and part != '-':
            # Range like "5-7" 
            start, end = map(int, part.split('-'))
            runs.extend(range(start, end + 1))  # Include end
        else:
            # Single run like "5"
            runs.append(int(part))
    
    # Find matching groups by actual run number
    selected_groups = []
    for run_num in runs:
        for group in valid_results:
            if group.get('Acquisition') == str(run_num):
                selected_groups.append(group)
                break
    
    return selected_groups

def main():
    parser = argparse.ArgumentParser(description='Run a QSM algorithm on BIDS data using a working directory.')
    parser.add_argument('algo_dir', type=str, help='Path to the QSM algorithm')
    parser.add_argument('bids_dir', type=str, help='Path to the BIDS directory')
    parser.add_argument('work_dir', type=str, help='Path to the working directory')
    parser.add_argument('inputs_json', type=str, nargs='?', help='Path to the inputs.json file')
    parser.add_argument('--container_engine', type=str, default='docker', choices=['docker', 'apptainer'], help='Choose between Docker or Apptainer')
    parser.add_argument('--overlay', type=str, help='Path to overlay image (for Apptainer)')
    parser.add_argument('--overlay_size', type=int, default=4096, help='Size of overlay in MB (if using Apptainer)')
    parser.add_argument('--cosmos_runs', type=str, default='1', help='COSMOS runs to process (e.g. "1" or "1,2,5" or "1-3")')
    args = parser.parse_args()
    print(f"[INFO] bids_dir: {args.bids_dir}")
    print(f"[INFO] algo_dir: {args.algo_dir}")
    print(f"[INFO] work_dir: {args.work_dir}")

    client = None
    docker_image, apptainer_image, algo_name, work_dir = setup_environment(args.bids_dir, args.algo_dir, args.work_dir, args.container_engine)

    if args.container_engine == 'apptainer' and args.overlay:
        create_overlay(args.overlay, size_mb=args.overlay_size)

    # Parse BIDS for both Docker and Apptainer
    if not args.inputs_json:
        print("[DEBUG] Parsing BIDS directory...")
        bids_results = list(parse_bids.parse_bids_directory(args.bids_dir))
        print(f"[DEBUG] Found {len(bids_results)} BIDS entries")
        
        # Filter valid groups with MEGRE data
        valid_results = [r for r in bids_results if len(r.get('mag_nii', [])) > 0]
        print(f"[DEBUG] Found {len(valid_results)} valid groups with MEGRE data")
        
        if len(valid_results) == 0:
            print("[ERROR] No valid MEGRE data found!")
            return
        
        # Detect dataset type: COSMOS vs synthetic
        first_group = valid_results[0]
        acq = first_group.get('Acquisition')
        is_cosmos_data = acq and acq.isdigit()
        
        if is_cosmos_data:
            print(f"[DEBUG] Detected COSMOS dataset (numeric acq: {acq})")
            selected_groups = parse_run_selection(args.cosmos_runs, valid_results)
            print(f"[DEBUG] Selected COSMOS runs: {[g.get('Acquisition') for g in selected_groups]}")
        else:
            print(f"[DEBUG] Detected synthetic dataset (named acq: {acq})")
            selected_groups = valid_results

    if args.container_engine == 'docker':
        client = docker.from_env()
        container_names_to_remove = []
        
        if not args.inputs_json:
            for input_json in selected_groups:
                run_num = input_json.get('Acquisition')
                print(f"[DEBUG] Processing run {run_num}")
                cname = run_algo(client, docker_image, apptainer_image, algo_name, args.bids_dir, work_dir, input_json, args.container_engine, args.overlay)
                if cname:
                    container_names_to_remove.append(cname)
        else:
            with open(args.inputs_json, 'r') as json_file:
                input_json = json.load(json_file)
            cname = run_algo(client, docker_image, apptainer_image, algo_name, args.bids_dir, work_dir, input_json, args.container_engine, args.overlay)
            if cname:
                container_names_to_remove.append(cname)

        # Clean up containers
        for cname in container_names_to_remove:
            try:
                container = client.containers.get(cname)
                container.remove()
                print(f"[INFO] Container {cname} removed.")
            except docker.errors.NotFound:
                print(f"[INFO] Container {cname} already removed.")
            except Exception as e:
                print(f"[WARNING] Could not remove container {cname}: {e}")
    
    else:  # Apptainer
        if not args.inputs_json:
            for input_json in selected_groups:
                run_num = input_json.get('Acquisition')
                print(f"[DEBUG] Processing run {run_num}")
                run_algo(None, docker_image, apptainer_image, algo_name, args.bids_dir, work_dir, input_json, args.container_engine, args.overlay)
        else:
            with open(args.inputs_json, 'r') as json_file:
                input_json = json.load(json_file)
            run_algo(None, docker_image, apptainer_image, algo_name, args.bids_dir, work_dir, input_json, args.container_engine, args.overlay)

if __name__ == '__main__':
    main()