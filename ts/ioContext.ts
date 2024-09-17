import fs from "fs";
import { exec, ExecException } from "child_process";
import { promisify } from "util";
import { spawn } from "child_process";
import shlex from "shell-quote";

import { Api as ContainerApi } from "./containerServerApi";

export interface IOContext {
  writeFile(path: string, content: string): Promise<void>;
  readFile(path: string): Promise<string>;
  runCommand(command: string): Promise<{ returnCode: number; output: string }>;
}

export class LocalIOContext implements IOContext {
  constructor(private readonly directory: string) {}

  async writeFile(path: string, content: string): Promise<void> {
    const fullPath = this.resolvePath(path);
    await fs.promises.writeFile(fullPath, content);
  }

  async readFile(path: string): Promise<string> {
    const fullPath = this.resolvePath(path);
    return await fs.promises.readFile(fullPath, "utf8");
  }

  async runCommand(
    command: string
  ): Promise<{ returnCode: number; output: string }> {
    return new Promise((resolve, reject) => {
      const process = spawn(command, { shell: true });

      let output = "";

      // Capture stdout and stderr interleaved
      process.stdout.on("data", (data) => {
        output += data.toString();
      });

      process.stderr.on("data", (data) => {
        output += data.toString();
      });

      process.on("close", (code) => {
        resolve({
          returnCode: code || 0,
          output,
        });
      });

      process.on("error", (error) => {
        reject({
          returnCode: 1,
          output: error.message,
        });
      });
    });
  }

  private resolvePath(path: string): string {
    return path.startsWith("/") ? path : `${this.directory}/${path}`;
  }
}

export class RemoteContainerIOContext implements IOContext {
  constructor(
    private readonly api: ContainerApi<null>,
    private readonly directory: string,
    private readonly commandPrefix: string,
    private readonly containerId: string
  ) {}

  async writeFile(path: string, content: string): Promise<void> {
    const fullPath = this.resolvePath(path);
    await this.api.container.writeFileContainerWriteFilePost({
      container_id: this.containerId,
      file_path: fullPath,
      file_content: content,
    });
  }

  async readFile(path: string): Promise<string> {
    const fullPath = this.resolvePath(path);
    const response = await this.api.container.readFileContainerReadFilePost({
      container_id: this.containerId,
      file_path: fullPath,
    });
    return (await response.json()).file_content;
  }

  async runCommand(
    command: string
  ): Promise<{ output: string; returnCode: number }> {
    command = `${this.commandPrefix}${command}`;
    command = `bash -c ${shlex.quote([command])}`;
    const response = await this.api.container.runCommandContainerRunPost({
      container_id: this.containerId,
      workdir: this.directory,
      command,
    });
    const result = await response.json();
    return {
      returnCode: result.exit_code,
      output: result.output,
    };
  }

  private resolvePath(path: string): string {
    return path.startsWith("/") ? path : `${this.directory}/${path}`;
  }

  async stopContainer(): Promise<void> {
    await this.api.container.stopContainerContainerStopPost({
      container_id: this.containerId,
      delete: true,
    });
  }
}

export class RemoteContainerServer {
  private readonly api: ContainerApi<null>;
  private readonly directory: string;
  private readonly commandPrefix: string;

  constructor(
    private readonly baseUrl: string,
    directory: string,
    commandPrefix: string
  ) {
    this.api = new ContainerApi({ baseUrl });
    this.directory = directory;
    this.commandPrefix = commandPrefix;
  }

  async startContainer(imageId: string): Promise<RemoteContainerIOContext> {
    const response = await this.api.container.startContainerContainerStartPost({
      image_id: imageId,
    });
    const containerId = (await response.json()).container_id;
    return new RemoteContainerIOContext(
      this.api,
      this.directory,
      this.commandPrefix,
      containerId
    );
  }
}
