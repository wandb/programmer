import os
import tarfile
from io import BytesIO
from concurrent.futures import ThreadPoolExecutor
import asyncio
import docker
from docker.errors import NotFound
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel


# DockerContainerManager class
class DockerContainerManager:
    def __init__(self):
        self.client = docker.from_env()
        self.executor = ThreadPoolExecutor()

    async def start_container(self, image_id: str):
        loop = asyncio.get_event_loop()
        container = await loop.run_in_executor(
            self.executor, self._run_container, image_id
        )
        return container.short_id

    def _run_container(self, image_id: str):
        return self.client.containers.run(
            image_id, detach=True, command="tail -f /dev/null"
        )

    def _get_container(self, container_id: str):
        return self.client.containers.get(container_id)

    async def run_command(self, container_id: str, workdir: str, command: str):
        loop = asyncio.get_event_loop()
        exec_result = await loop.run_in_executor(
            self.executor, self._exec_run, container_id, command, workdir
        )
        return {
            "exit_code": exec_result.exit_code,
            "output": exec_result.output.decode("utf-8"),
        }

    def _exec_run(self, container_id: str, command: str, workdir: str):
        container = self._get_container(container_id)
        return container.exec_run(command, workdir=workdir)

    async def write_file(self, container_id: str, file_path: str, file_content: str):
        file_path = os.path.join("/", file_path)
        container = self._get_container(container_id)
        tarstream = BytesIO()
        encoded_content = file_content.encode("utf-8")
        with tarfile.open(fileobj=tarstream, mode="w") as tar:
            tarinfo = tarfile.TarInfo(name=os.path.basename(file_path))
            tarinfo.size = len(encoded_content)
            tar.addfile(tarinfo, BytesIO(encoded_content))
        tarstream.seek(0)

        loop = asyncio.get_event_loop()
        await loop.run_in_executor(
            self.executor,
            container.put_archive,
            os.path.dirname(file_path),
            tarstream,
        )

    async def read_file(self, container_id: str, file_path: str):
        container = self._get_container(container_id)
        loop = asyncio.get_event_loop()
        bits, _ = await loop.run_in_executor(
            self.executor, container.get_archive, file_path
        )
        file_content = BytesIO()
        for chunk in bits:
            file_content.write(chunk)
        file_content.seek(0)
        with tarfile.open(fileobj=file_content) as tar:
            member = tar.getmembers()[0]
            extract_result = tar.extractfile(member)
            if extract_result is None:
                raise Exception(f"Unexpected tar.extractfile result for: {file_path}")
            file_data = extract_result.read()
        return file_data.decode("utf-8")

    async def stop_container(self, container_id: str, delete: bool = False):
        container = self._get_container(container_id)
        loop = asyncio.get_event_loop()
        await loop.run_in_executor(self.executor, container.stop)
        if delete:
            await loop.run_in_executor(self.executor, container.remove)


# FastAPI setup
app = FastAPI()
container_manager = DockerContainerManager()


class StartContainerRequest(BaseModel):
    image_id: str


class StopContainerRequest(BaseModel):
    container_id: str
    delete: bool


class CommandRequest(BaseModel):
    container_id: str
    workdir: str
    command: str


class FileRequest(BaseModel):
    container_id: str
    file_path: str
    file_content: str


class FilePathRequest(BaseModel):
    container_id: str
    file_path: str


@app.post("/container/start")
async def start_container(request: StartContainerRequest):
    try:
        container_id = await container_manager.start_container(request.image_id)
        return {"container_id": container_id}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/container/run")
async def run_command(request: CommandRequest):
    try:
        result = await container_manager.run_command(
            request.container_id, request.workdir, request.command
        )
        return {"exit_code": result["exit_code"], "output": result["output"]}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/container/write_file")
async def write_file(request: FileRequest):
    try:
        await container_manager.write_file(
            request.container_id, request.file_path, request.file_content
        )
        return {"status": "file written"}
    except NotFound as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/container/read_file")
async def read_file(request: FilePathRequest):
    try:
        file_content = await container_manager.read_file(
            request.container_id, request.file_path
        )
        return {"file_content": file_content}
    except NotFound as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/container/stop")
async def stop_container(request: StopContainerRequest):
    try:
        await container_manager.stop_container(request.container_id, request.delete)
        return {"status": "container stopped"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# To run the server, use:
# uvicorn your_file_name:app --host 0.0.0.0 --port 8000 --workers 4
