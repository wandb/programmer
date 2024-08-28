import requests
import threading
import argparse

# Replace with the actual host and port if different
BASE_URL = "http://127.0.0.1:8000"


def start_container(image_id: str):
    response = requests.post(f"{BASE_URL}/container/start", json={"image_id": image_id})
    if response.status_code == 200:
        return response.json().get("container_id")
    else:
        print(f"Failed to start container: {response.text}")
        return None


def run_command(container_id: str, workdir: str, command: str):
    response = requests.post(
        f"{BASE_URL}/container/run",
        json={"container_id": container_id, "workdir": workdir, "command": command},
    )
    if response.status_code == 200:
        return response.json()
    else:
        print(f"Failed to run command: {response.text}")
        return None


def write_file(container_id: str, file_path: str, file_content: str):
    response = requests.post(
        f"{BASE_URL}/container/write_file",
        json={
            "container_id": container_id,
            "file_path": file_path,
            "file_content": file_content,
        },
    )
    if response.status_code == 200:
        return response.json().get("status")
    else:
        print(f"Failed to write file: {response.text}")
        return None


def read_file(container_id: str, file_path: str):
    response = requests.post(
        f"{BASE_URL}/container/read_file",
        json={"container_id": container_id, "file_path": file_path},
    )
    if response.status_code == 200:
        return response.json().get("file_content")
    else:
        print(f"Failed to read file: {response.text}")
        return None


def stop_container(container_id: str, delete: bool):
    response = requests.post(
        f"{BASE_URL}/container/stop",
        json={"container_id": container_id, "delete": delete},
    )
    if response.status_code == 200:
        return response.json().get("status")
    else:
        print(f"Failed to stop container: {response.text}")
        return None


def manage_container(image_id: str, container_index: int):
    print(f"Starting container {container_index}...")
    container_id = start_container(image_id)
    if not container_id:
        print(f"Failed to start container {container_index}")
        return

    print(f"Started container {container_index} with ID: {container_id}")

    # Run a command inside the container
    output = run_command(container_id, "/", "ls")
    if output:
        print(f"Container {container_index} command output:\n{output}")

    # Write a file inside the container
    file_path = f"test_{container_index}.txt"
    file_content = f"Hello, this is a test for container {container_index}."
    write_status = write_file(container_id, file_path, file_content)
    if write_status:
        print(f"Container {container_index} write file status: {write_status}")

    # Read the file back from the container
    read_content = read_file(container_id, file_path)
    if read_content:
        print(f"Container {container_index} file content:\n{read_content}")

    # Stop the container (and delete it)
    stop_status = stop_container(container_id, delete=True)
    if stop_status:
        print(f"Container {container_index} stop status: {stop_status}")


def run_parallel_tests(image_id: str, parallelism: int):
    threads = []
    for i in range(parallelism):
        thread = threading.Thread(target=manage_container, args=(image_id, i))
        threads.append(thread)
        thread.start()

    for thread in threads:
        thread.join()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Run parallel container tests")
    parser.add_argument(
        "--parallelism",
        type=int,
        default=1,
        help="Number of parallel container operations (default: 1)",
    )
    parser.add_argument(
        "--image-id",
        type=str,
        default="sweb.eval.x86_64.sympy__sympy-20590",
        help="Image ID to test",
    )
    args = parser.parse_args()

    run_parallel_tests(args.image_id, args.parallelism)
