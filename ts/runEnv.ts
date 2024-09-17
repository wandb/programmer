import * as readline from "readline";
import { EnvShell } from "./envShell";
import { AdventureInTheHauntedCastle } from "./complexGame";
import { Action, ActionSpec, Environment, Observation } from "./environment";

function promptUser(
  input: string,
  availableActions: ActionSpec[]
): Action | null {
  const parts = tokenizeInput(input);

  if (parts.length === 0) {
    console.log("No input provided.");
    return null;
  }

  const actionName = parts[0];
  const actionSpec = availableActions.find(
    (action) => action.name === actionName
  );

  if (!actionSpec) {
    console.log(`Unknown action: ${actionName}`);
    return null;
  }

  const parameters: Record<string, string> = {};
  const requiredParams = (actionSpec.parameters as any).required || [];
  let paramIndex = 0;

  for (let i = 1; i < parts.length; i++) {
    if (paramIndex >= requiredParams.length) {
      console.log(`Too many parameters provided for action: ${actionName}`);
      return null;
    }

    const paramName = requiredParams[paramIndex];
    parameters[paramName] = parts[i];
    paramIndex++;
  }

  if (paramIndex < requiredParams.length) {
    console.log(`Not enough parameters provided for action: ${actionName}`);
    return null;
  }

  return {
    name: actionName,
    parameters: parameters,
  };
}

function tokenizeInput(input: string): string[] {
  const tokens: string[] = [];
  let currentToken = "";
  let inQuotes = false;
  let escapeNext = false;

  for (let i = 0; i < input.length; i++) {
    const char = input[i];

    if (escapeNext) {
      currentToken += char;
      escapeNext = false;
    } else if (char === "\\") {
      escapeNext = true;
    } else if (char === '"' && !inQuotes) {
      inQuotes = true;
    } else if (char === '"' && inQuotes) {
      inQuotes = false;
      if (currentToken) {
        tokens.push(currentToken);
        currentToken = "";
      }
    } else if (char === " " && !inQuotes) {
      if (currentToken) {
        tokens.push(currentToken);
        currentToken = "";
      }
    } else {
      currentToken += char;
    }
  }

  if (currentToken) {
    tokens.push(currentToken);
  }

  if (inQuotes) {
    console.log("Warning: Unclosed quote in input");
  }

  return tokens;
}

async function runInteractiveEnvironment<O extends Observation>(
  env: Environment<O>,
  stopFn?: (env: Environment<O>) => boolean
) {
  const rl = readline.createInterface({
    input: process.stdin,
    output: process.stdout,
  });

  console.log("Welcome to the interactive environment!");
  console.log(
    "Available actions:",
    env
      .availableActions()
      .map((action) => action.name)
      .join(", ")
  );

  while (true) {
    const observation = env.observe();
    console.log("Observation:", observation);

    const input = await new Promise<string>((resolve) =>
      rl.question("\nAction: ", resolve)
    );

    const availableActions = env.availableActions();
    const action = promptUser(input, availableActions);

    if (action) {
      try {
        const responses = await env.act([action]);
        responses.forEach((response) => console.log(response));
      } catch (error) {
        if (error instanceof Error) {
          console.error("Error executing action:", error.message);
        } else {
          console.error("An unknown error occurred");
        }
      }
    }

    if (stopFn && stopFn(env)) {
      console.log("Stopping condition met. Exiting...");
      break;
    }
  }

  rl.close();
}

// Example usage
async function main() {
  //   const env = new EnvShell();
  const env = new AdventureInTheHauntedCastle();
  await runInteractiveEnvironment(env);
}

main().catch(console.error);
