import { Action, Environment } from "./environment";
import fs from "fs";
import { exec, ExecException } from "child_process";
import { promisify } from "util";
import { IOContext } from "./ioContext";

export class EnvShellPatch implements Environment<string> {
  constructor(
    private readonly ioContext: IOContext,
    private readonly actionWhitelist?: string[]
  ) {}

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
    const actions = [
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
        name: "apply_patch",
        description: "Apply a patch in the given directory",
        parameters: {
          type: "object",
          properties: {
            directory: { type: "string" },
            unified_diff: { type: "string" },
          },
          required: ["directory", "unified_diff"],
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
    const actionWhitelist = this.actionWhitelist;
    if (actionWhitelist) {
      return actions.filter((action) => actionWhitelist.includes(action.name));
    }
    return actions;
  };

  async act(actions: Action[]): Promise<string[]> {
    const results: string[] = [];

    for (const action of actions) {
      switch (action.name) {
        case "read_file":
          results.push(await this.actionReadFile(action.parameters.path));
          break;
        case "apply_patch":
          results.push(
            await this.actionApplyPatch(
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

  async actionApplyPatch(
    directory: string,
    unified_diff: string
  ): Promise<string> {
    try {
      // Generate a random file name
      const randomFileName = `patch_${Math.random()
        .toString(36)
        .substring(7)}.diff`;
      const tempFilePath = `/tmp/${randomFileName}`;

      // Write the unified diff to the temporary file
      await this.ioContext.writeFile(tempFilePath, unified_diff);

      // Run the patch command
      const patchCommand = `patch -p1 -d ${directory} < ${tempFilePath}`;
      const patchResult = await this.ioContext.runCommand(patchCommand);

      // Check if the patch was applied successfully
      if (patchResult.returnCode !== 0) {
        throw new Error(`Patch application failed: ${patchResult.output}`);
      }

      // Clean up the temporary file
      await this.ioContext.runCommand(`rm ${tempFilePath}`);

      return "Patch applied successfully";
    } catch (err) {
      throw new Error(`Error applying patch: ${err}`);
    }
  }

  async actionListFiles(path: string): Promise<string> {
    const lsCommandResult = await this.ioContext.runCommand(`ls ${path}`);
    if (lsCommandResult.returnCode !== 0) {
      return `Error listing files: ${lsCommandResult.output}`;
    }
    return lsCommandResult.output;
  }

  async actionRunCommand(command: string): Promise<string> {
    const commandResult = await this.ioContext.runCommand(command);
    return JSON.stringify(commandResult);
  }
}
