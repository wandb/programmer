import { Action, Environment } from "./environment";
import fs from "fs";
import { exec, ExecException } from "child_process";
import { promisify } from "util";
import { IOContext } from "./ioContext";

const execAsync = promisify(exec);

export class EnvShell implements Environment<string> {
  constructor(private readonly ioContext: IOContext) {}

  save = () => {
    throw new Error("Not implemented");
  };
  load = () => {
    throw new Error("Not implemented");
  };
  observe = () => {
    return "";
  };
  availableActions = () => {
    return [
      {
        name: "read_file",
        description: "Read file contents as a string",
        parameters: {
          type: "object",
          properties: {
            path: { type: "string" },
          },
          required: ["path"],
        },
      },
      {
        name: "write_file",
        description: "Write file contents as a string",
        parameters: {
          type: "object",
          properties: {
            path: { type: "string" },
            content: { type: "string" },
          },
          required: ["path", "content"],
        },
      },
      {
        name: "list_files",
        description: "List files in the directory at the given path",
        parameters: {
          type: "object",
          properties: {
            path: { type: "string" },
          },
          required: ["path"],
        },
      },
      {
        name: "run_command",
        description: "Run a command in the shell",
        parameters: {
          type: "object",
          properties: {
            command: { type: "string" },
          },
          required: ["command"],
        },
      },
    ];
  };

  async act(actions: Action[]): Promise<string[]> {
    const results: string[] = [];

    for (const action of actions) {
      switch (action.name) {
        case "read_file":
          results.push(await this.actionReadFile(action.parameters.path));
          break;
        case "write_file":
          results.push(
            await this.actionWriteFile(
              action.parameters.path,
              action.parameters.content
            )
          );
          break;
        case "list_files":
          results.push(await this.actionListFiles(action.parameters.path));
          break;
        case "run_command":
          results.push(await this.actionRunCommand(action.parameters.command));
          break;
        default:
          results.push(`Unknown action: ${action.name}`);
      }
    }

    return results;
  }

  async actionReadFile(path: string): Promise<string> {
    try {
      return await this.ioContext.readFile(path);
    } catch (err) {
      throw new Error(`Error reading file: ${err}`);
    }
  }

  async actionWriteFile(path: string, content: string): Promise<string> {
    try {
      await this.ioContext.writeFile(path, content);
      return "File written successfully";
    } catch (err) {
      throw new Error(`Error writing file: ${err}`);
    }
  }

  async actionListFiles(path: string): Promise<string> {
    const lsCommandResult = await this.ioContext.runCommand(`ls ${path}`);
    if (lsCommandResult.returnCode !== 0) {
      throw new Error(`Error listing files: ${lsCommandResult.output}`);
    }
    return lsCommandResult.output;
  }

  async actionRunCommand(command: string): Promise<string> {
    const commandResult = await this.ioContext.runCommand(command);
    return JSON.stringify(commandResult);
  }
}
