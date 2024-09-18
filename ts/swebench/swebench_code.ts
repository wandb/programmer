import { init, op, Dataset, Evaluation } from "weave";
import { RemoteContainerServer } from "../ioContext";
import { LLM, LLMBasicMessages } from "../llm";
import { Trajectory } from "../trajectory";
import { EnvironmentObservationType } from "../environment";
import { Stepper } from "../agent";
import { ActionSpec } from "../environment";
import { EnvShell } from "../envShell";

import { verifiedDataset, scoreInstance } from "./swebench";

// Function to extract modified file paths from a patch
function getModifiedFilePaths(patch: string): string[] {
  const lines = patch.split("\n");
  const modifiedFiles: string[] = [];

  for (const line of lines) {
    if (line.startsWith("diff --git")) {
      const match = line.match(/diff --git a\/(.*) b\//);
      if (match && match[1]) {
        modifiedFiles.push(match[1]);
      }
    }
  }

  return modifiedFiles;
}

const swebenchEasy10 = () => {
  const instance_ids = [
    "django__django-16569",
    "django__django-11099",
    "scikit-learn__scikit-learn-12585",
    "django__django-13658",
    "django__django-9296",
    "astropy__astropy-14309",
    "django__django-12155",
    "django__django-16527",
    "sympy__sympy-24213",
    "django__django-11066",
  ];
  const rawDs = verifiedDataset().filter((row) =>
    instance_ids.includes(row.instance_id)
  );
  return new Dataset({
    id: `SWEBenchVerified-easy10`,
    rows: rawDs,
  });
};

const swebenchEasy3 = () => {
  const instance_ids = [
    "django__django-16569",
    "django__django-11099",
    "scikit-learn__scikit-learn-12585",
  ];
  const rawDs = verifiedDataset().filter((row) =>
    instance_ids.includes(row.instance_id)
  );
  return new Dataset({
    id: `SWEBenchVerified-easy3`,
    rows: rawDs,
  });
};

const sweBenchSeed42 = (limit: number) => {
  const instance_ids = [
    "django__django-14672",
    "sphinx-doc__sphinx-10449",
    "django__django-11299",
    "django__django-14493",
    "django__django-11551",
    "django__django-12143",
    "pydata__xarray-6938",
    "django__django-15916",
    "django__django-12193",
    "pytest-dev__pytest-5262",
    "sphinx-doc__sphinx-8459",
    "sphinx-doc__sphinx-9281",
    "django__django-13012",
    "django__django-16082",
    "sympy__sympy-20916",
    "django__django-11749",
    "scikit-learn__scikit-learn-14629",
    "django__django-14631",
    "django__django-15930",
    "django__django-7530",
    "sympy__sympy-14248",
    "pylint-dev__pylint-4551",
    "pallets__flask-5014",
    "sphinx-doc__sphinx-7440",
    "astropy__astropy-14096",
    "sympy__sympy-17655",
    "django__django-17084",
    "django__django-16485",
    "django__django-16901",
    "django__django-15957",
    "django__django-13809",
    "django__django-14608",
    "django__django-16263",
    "django__django-11239",
    "matplotlib__matplotlib-25332",
    "astropy__astropy-8872",
    "sympy__sympy-13551",
    "django__django-11999",
    "django__django-16454",
    "django__django-14351",
    "scikit-learn__scikit-learn-14710",
    "django__django-16116",
    "django__django-14404",
    "django__django-15103",
    "sphinx-doc__sphinx-7985",
    "django__django-14017",
    "django__django-14053",
    "pylint-dev__pylint-6903",
    "django__django-15037",
    "django__django-14792",
  ];
  const rawDs = verifiedDataset()
    .filter((row) => instance_ids.includes(row.instance_id))
    .slice(0, limit);
  return new Dataset({
    id: `SWEBenchVerified-seed42-${limit}`,
    rows: rawDs,
  });
};

const swebenchFirst = (n: number) => {
  const rawDs = verifiedDataset().slice(0, n);
  return new Dataset({
    id: `SWEBenchVerified-first${n}`,
    rows: rawDs,
  });
};

async function main() {
  await init("programmerjs-swebenchcode1");

  const remoteContainerServer = new RemoteContainerServer(
    "http://localhost:8000",
    "/testbed",
    "source /opt/miniconda3/bin/activate && conda activate testbed && "
  );

  // const limit = 2;
  const ds = sweBenchSeed42(10);
  const evaluation = new Evaluation({
    dataset: ds,
    scorers: [
      op(function scoreSwebench(modelOutput, input) {
        const patch = modelOutput.patch;
        return scoreInstance(remoteContainerServer, input, patch);
      }),
    ],
  });

  const agentGpt4o = new LLM(
    "Perform tasks",
    "gpt-4o-2024-08-06",
    // "o1-preview-2024-09-12",
    0.7,
    (inputs: {
      trajectory: Trajectory;
      availableActions: ActionSpec[];
      observation: any;
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

  const agentO1 = new LLMBasicMessages(
    "Perform tasks",
    "o1-preview-2024-09-12",
    1,
    (inputs: {
      trajectory: Trajectory;
      availableActions: ActionSpec[];
      observation: any;
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

  const agent = agentO1;

  const stepper = new Stepper(agent);

  const model = op(async function myModel(input) {
    const instanceId = input.instance_id;
    return await remoteContainerServer.withContainer(
      `sweb.eval.x86_64.${instanceId}`,
      async (ioContext) => {
        // Extract modified file paths from the solution patch
        const solutionPatch = input.patch;

        const modifiedFiles = getModifiedFilePaths(solutionPatch);
        const fileContents = await Promise.all(
          modifiedFiles.map((file) => ioContext.readFile(file))
        );

        // Build the prompt with file contents using XML-like tags
        let prompt = "Given the following files:\n\n";
        for (let i = 0; i < modifiedFiles.length; i++) {
          prompt += `<file path="${modifiedFiles[i]}">\n`;
          prompt += `${fileContents[i]}\n`;
          prompt += "</file>\n\n";
        }
        prompt += "and the following problem statement:\n\n";
        prompt += `<problem_statement>\n${input.problem_statement}\n</problem_statement>\n\n`;
        prompt +=
          "Please analyze the files and the problem statement, and make the necessary changes to the files using write_file tool.";

        const runEnv = new EnvShell(ioContext, ["write_file"]);
        const trajectory: Trajectory = [
          {
            role: "user",
            content: prompt,
          },
        ];
        const result = await stepper.run({ trajectory, env: runEnv });
        const diffResult = await ioContext.runCommand("git diff");
        return {
          patch: diffResult.output,
        };
      }
    );
  });

  const results = await evaluation.evaluate({ model, maxConcurrency: 10 });
  console.log(JSON.stringify(results, null, 2));
}

main().catch(console.error);
