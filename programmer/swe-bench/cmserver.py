import docker
import os
import tarfile
from io import BytesIO
from concurrent.futures import ThreadPoolExecutor
import asyncio
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

# DockerContainerManager class
class DockerContainerManager:
    def __init__(self):
        self.client = docker.from_env()
        self.containers = {}
        self.executor = ThreadPoolExecutor()

    async def start_container(self, image_id):
        loop = asyncio.get_event_loop()
        container = await loop.run_in_executor(self.executor, self._run_container, image_id)
        container_id = container.short_id
        self.containers[container_id] = {
            "container": container,
        }
        self.containers[container_id]["container_pwd"] = (await self.run_command(container_id, "pwd")).strip()
        return container_id

    def _run_container(self, image_id):
        return self.client.containers.run(image_id, detach=True, command='tail -f /dev/null')

    async def run_command(self, container_id, command):
        if container_id in self.containers:
            loop = asyncio.get_event_loop()
            container = self.containers[container_id]["container"]
            exec_result = await loop.run_in_executor(self.executor, container.exec_run, command)
            return exec_result.output.decode('utf-8')
        else:
            raise Exception("Container is not running")

    async def write_file(self, container_id, file_path, file_content):
        if container_id in self.containers:
            container = self.containers[container_id]["container"]
            container_pwd = self.containers[container_id]["container_pwd"]
            full_path = os.path.join(container_pwd, file_path)
            tarstream = BytesIO()
            with tarfile.open(fileobj=tarstream, mode='w') as tar:
                tarinfo = tarfile.TarInfo(name=os.path.basename(full_path))
                tarinfo.size = len(file_content)
                tar.addfile(tarinfo, BytesIO(file_content.encode('utf-8')))
            tarstream.seek(0)

            loop = asyncio.get_event_loop()
            await loop.run_in_executor(self.executor, container.put_archive, os.path.dirname(full_path), tarstream)
        else:
            raise Exception("Container is not running")

    async def read_file(self, container_id, file_path):
        if container_id in self.containers:
            container = self.containers[container_id]["container"]
            container_pwd = self.containers[container_id]["container_pwd"]
            full_path = os.path.join(container_pwd, file_path)
            loop = asyncio.get_event_loop()
            bits, _ = await loop.run_in_executor(self.executor, container.get_archive, full_path)
            file_content = BytesIO()
            for chunk in bits:
                file_content.write(chunk)
            file_content.seek(0)
            with tarfile.open(fileobj=file_content) as tar:
                member = tar.getmembers()[0]
                file_data = tar.extractfile(member).read()
            return file_data.decode('utf-8')
        else:
            raise Exception("Container is not running")

    async def stop_container(self, container_id, delete=False):
        if container_id in self.containers:
            container = self.containers[container_id]["container"]
            loop = asyncio.get_event_loop()
            await loop.run_in_executor(self.executor, container.stop)
            if delete:
                await loop.run_in_executor(self.executor, container.remove)
            del self.containers[container_id]
        else:
            raise Exception("Container is not running")

# FastAPI setup
app = FastAPI()
container_manager = DockerContainerManager()

class StartContainerRequest(BaseModel):
    image_id: str

class StopContainerRequest(BaseModel):
    container_id: str

class CommandRequest(BaseModel):
    container_id: str
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
        output = await container_manager.run_command(request.container_id, request.command)
        return {"output": output}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/container/write_file")
async def write_file(request: FileRequest):
    try:
        await container_manager.write_file(request.container_id, request.file_path, request.file_content)
        return {"status": "file written"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/container/read_file")
async def read_file(request: FilePathRequest):
    try:
        file_content = await container_manager.read_file(request.container_id, request.file_path)
        return {"file_content": file_content}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/container/stop")
async def stop_container(request: StopContainerRequest, delete: bool = False):
    try:
        await container_manager.stop_container(request.container_id, delete)
        return {"status": "container stopped"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# To run the server, use:
# uvicorn your_file_name:app --host 0.0.0.0 --port 8000 --workers 4
