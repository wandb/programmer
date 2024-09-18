import * as fs from "fs";
import * as path from "path";
import * as csv from "csv-parse/sync";
import { exec } from "child_process";
import { promisify } from "util";
import { EnvShell } from "../envShell";
import {
  LocalIOContext,
  RemoteContainerServer,
  RemoteContainerIOContext,
} from "../ioContext";
import { LLM } from "../llm";
import { Trajectory } from "../trajectory";
import { EnvironmentObservationType, EnvironmentType } from "../environment";
import { Stepper, SequentialRunner, AgentFn } from "../agent";
import { AdventureInTheHauntedCastle } from "../complexGame";
import { Action, ActionSpec, Environment, Observation } from "../environment";

// TODO: clean up containers

const execAsync = promisify(exec);

interface SWEBenchInstance {
  repo_name: string;
  instance_id: string;
  base_commit: string;
  patch: string;
  test_patch: string;
  problem_statement: string;
  hints_text: string;
  created_at: Date;
  version: string;
  FAIL_TO_PASS: string;
  PASS_TO_PASS: string;
  environment_setup_commit: string;
}

type SWEBenchDataset = SWEBenchInstance[];

interface SWEBenchTestSpec {
  instance_id: string;
  repo: string;
  version: string;
  repo_script_list: string;
  eval_script_list: string;
  env_script_list: string;
  arch: string;
  FAIL_TO_PASS: string;
  PASS_TO_PASS: string;
  setup_env_script: string;
  eval_script: string;
  install_repo_script: string;
  base_image_key: string;
  env_image_key: string;
  instance_image_key: string;
}

type SWEBenchTestSpecDataset = SWEBenchTestSpec[];

export function verifiedDataset(
  filePath: string = "swebench-verified.csv"
): SWEBenchDataset {
  try {
    const fullPath = path.resolve(filePath);
    const fileContent = fs.readFileSync(fullPath, "utf-8");
    const records = csv.parse(fileContent, {
      columns: true,
      skip_empty_lines: true,
    });
    return records;
  } catch (error) {
    console.error(`Error loading verified dataset: ${error}`);
    return [];
  }
}

function verifiedTestSpecs(
  filePath: string = "swebench-verified_test_specs.csv"
): SWEBenchTestSpecDataset {
  try {
    const fullPath = path.resolve(filePath);
    const fileContent = fs.readFileSync(fullPath, "utf-8");
    const records = csv.parse(fileContent, {
      columns: true,
      skip_empty_lines: true,
    });
    return records;
  } catch (error) {
    console.error(`Error loading verified dataset: ${error}`);
    return [];
  }
}

const getDatasetInstance = (dataset: SWEBenchDataset, instanceId: string) => {
  return dataset.find((instance) => instance.instance_id === instanceId);
};

const getTestSpecInstance = (
  dataset: SWEBenchTestSpecDataset,
  instanceId: string
) => {
  return dataset.find((instance) => instance.instance_id === instanceId);
};

const runInstance = async (
  containerServer: RemoteContainerServer,
  instance: SWEBenchInstance,
  agent: AgentFn<string>
) => {
  const ioContext = await containerServer.startContainer(
    `sweb.eval.x86_64.${instance.instance_id}`
  );
  const runEnv = new EnvShell(ioContext);
  const trajectory: Trajectory = [
    {
      role: "user",
      content: `Perform this task: ${instance.problem_statement}`,
    },
  ];
  const result = await agent.run({ trajectory, env: runEnv });
  const diffResult = await ioContext.runCommand("git diff");
  return {
    result,
    diffResult,
  };
};

export const scoreInstance = async (
  containerServer: RemoteContainerServer,
  instance: SWEBenchInstance,
  patch: string
) => {
  const result = {
    patch_successfully_applied: false,
    resolved: false,
    test_output: "",
    report: null,
  };
  const testSpec = getTestSpecInstance(
    verifiedTestSpecs(),
    instance.instance_id
  );
  // console.log("TEST SPEC", testSpec);
  if (!testSpec) {
    throw new Error(`Test spec ${instance.instance_id} not found`);
  }
  // console.log("STARTING CONTAINER");
  return await containerServer.withContainer(
    `sweb.eval.x86_64.${instance.instance_id}`,
    async (ioContext) => {
      // console.log("WRITING PATCH");
      await ioContext.writeFile("/tmp/patch.diff", patch);
      // console.log("DOING PATCH");
      let patchResult = await ioContext.runCommand(
        "git apply -v /tmp/patch.diff"
      );
      if (patchResult.returnCode !== 0) {
        // console.log("git apply failed, trying patch");
        patchResult = await ioContext.runCommand(
          "patch --batch --fuzz=5 -p1 -i /tmp/patch.diff"
        );
      }
      if (patchResult.returnCode === 0) {
        result.patch_successfully_applied = true;
      }

      // console.log("WRITING EVAL SCRIPT");
      await ioContext.writeFile("/eval.sh", testSpec.eval_script);
      // console.log("RUNNING EVAL SCRIPT");
      const testCommandResults = await ioContext.runCommand(
        "chmod +x /eval.sh && /eval.sh"
      );
      const tcOutput = testCommandResults.output;
      result.test_output = tcOutput;

      // console.log("PARSING TEST RESULTS");
      // Write test output to a temporary file
      const tempOutputFile = `/tmp/swebench_test_output_${Date.now()}.txt`;
      await fs.promises.writeFile(tempOutputFile, tcOutput);

      try {
        // Call the Python script to parse the test results
        const { stdout } = await execAsync(
          `python swebench_testparse.py ${instance.instance_id} ${tempOutputFile}`
        );
        const parseResult = JSON.parse(stdout);
        result.report = parseResult.report;
        result.resolved = parseResult.resolved;
      } catch (error) {
        console.error("Error parsing test results:", error);
      } finally {
        // Clean up the temporary file
        await fs.promises.unlink(tempOutputFile);
      }

      // console.log("DONE");

      return result;
    }
  );
};

async function main() {
  const verifiedData = verifiedDataset();
  const instanceId = "django__django-11099";
  //   const instanceId = "django__django-11066";
  const instance = getDatasetInstance(verifiedData, instanceId);
  if (!instance) {
    throw new Error(`Instance ${instanceId} not found`);
  }
  const remoteContainerServer = new RemoteContainerServer(
    "http://localhost:8000",
    "/testbed",
    "source /opt/miniconda3/bin/activate && conda activate testbed && "
  );
  return await remoteContainerServer.withContainer(
    `sweb.eval.x86_64.${instanceId}`,
    async (ioContext) => {
      const runEnv = new EnvShell(ioContext);

      const agent = new LLM(
        "Perform tasks",
        "gpt-4o-2024-08-06",
        0.7,
        (inputs: {
          trajectory: Trajectory;
          availableActions: ActionSpec[];
          observation: EnvironmentObservationType<typeof runEnv>;
        }) => ({
          messages: [
            {
              role: "system",
              content: "you are an autonomous agent",
            },
            ...inputs.trajectory,
          ],
          tools: inputs.availableActions.map((actionSpec) => ({
            type: "function",
            function: actionSpec,
          })),
        })
      );
      const stepper = new Stepper(agent);
      const stopFn = (
        trajectory: Trajectory,
        env: EnvironmentType<typeof runEnv>
      ) => {
        const lastMessage = trajectory[trajectory.length - 1];
        if (
          lastMessage.role === "assistant" &&
          lastMessage.tool_calls == null
        ) {
          return true;
        }
        return false;
      };
      const runner = new SequentialRunner(stepper, 10, stopFn);
      const result = await runInstance(remoteContainerServer, instance, runner);
      console.log("SCORING");
      const scoreResult = await scoreInstance(
        remoteContainerServer,
        instance,
        result.diffResult.output
      );
      console.log(scoreResult);
    }
  );
}

// main().catch(console.error);
