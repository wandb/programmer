import * as readline from "readline";

import { Action, ActionSpec, Environment } from "./environment";

// AdventureInTheHauntedCastle class
export class AdventureInTheHauntedCastle
  implements Environment<{ message: string; won: boolean }>
{
  private rooms: {
    [key: string]: {
      description: string;
      connections: { [direction: string]: string };
      items?: string[];
      locked?: boolean;
      requiresKey?: string;
      secretRevealed?: boolean;
    };
  };
  private currentRoom: string;
  private inventory: string[];
  private won: boolean;
  private itemLocations: { [item: string]: string | null };
  private npcs: {
    [name: string]: {
      location: string;
      dialogue: string;
      requiredItem?: string;
      givesItem?: string;
    };
  };

  constructor() {
    this.rooms = {
      "entrance hall": {
        description:
          "You stand in the grand entrance hall of the haunted castle. Shadows dance on the walls.",
        connections: { north: "library", east: "garden", west: "dungeon" },
      },
      library: {
        description:
          "Rows of ancient books line the walls. A dusty chandelier hangs from above.",
        connections: { south: "entrance hall", east: "tower" },
        items: ["old map"],
      },
      garden: {
        description:
          "An overgrown garden with a fountain that's long since dried up.",
        connections: { west: "entrance hall" },
        items: ["rusty key"],
      },
      dungeon: {
        description: "Dark and damp, the dungeon smells of mold and despair.",
        connections: { east: "entrance hall" },
        locked: true,
        requiresKey: "rusty key",
        items: ["silver sword"],
        secretRevealed: false,
      },
      tower: {
        description:
          "At the top of the tower, the wind howls. An ancient inscription reads: 'Unite the sacred relics to transcend.'",
        connections: { west: "library" },
        locked: true,
        requiresKey: "golden key",
      },
      "secret chamber": {
        description: "A hidden chamber guarded by a shadowy figure.",
        connections: { up: "dungeon" },
        items: [], // Items moved to itemLocations
      },
    };

    this.currentRoom = "entrance hall";
    this.inventory = [];
    this.won = false;
    this.itemLocations = {
      "old map": "library",
      "rusty key": "garden",
      "silver sword": "dungeon",
      "golden key": "secret chamber",
      "ancient tome": "secret chamber",
      "mystic amulet": null, // Given by the NPC
    };

    this.npcs = {
      "ghostly figure": {
        location: "library",
        dialogue:
          "The mystic amulet holds the power to unlock ancient secrets.",
        requiredItem: "old map",
        givesItem: "mystic amulet",
      },
      "shadow guardian": {
        location: "secret chamber",
        dialogue:
          "You shall not take the treasures unless you prove your worth.",
      },
    };
  }

  save = () => {
    return JSON.parse(
      JSON.stringify({
        currentRoom: this.currentRoom,
        inventory: this.inventory,
        won: this.won,
        itemLocations: this.itemLocations,
        rooms: this.rooms,
      })
    );
  };

  load = (state: any) => {
    const loaded = new AdventureInTheHauntedCastle();
    loaded.currentRoom = state.currentRoom;
    loaded.inventory = state.inventory;
    loaded.won = state.won;
    loaded.itemLocations = state.itemLocations;
    loaded.rooms = state.rooms;
    return loaded;
  };

  observe = () => ({ message: this.getDescription(), won: this.won });

  availableActions = () => {
    const room = this.rooms[this.currentRoom];
    const actions: ActionSpec[] = [];

    // Move actions
    const directions = Object.keys(room.connections);
    if (directions.length > 0) {
      actions.push({
        name: "move",
        description: "Move to another room",
        parameters: {
          type: "object",
          properties: {
            direction: { type: "string", enum: directions },
          },
          required: ["direction"],
        },
      });
    }

    // Take actions
    const itemsHere = this.getItemsInCurrentRoom();
    if (itemsHere.length > 0) {
      actions.push({
        name: "take",
        description: "Take an item",
        parameters: {
          type: "object",
          properties: {
            item: { type: "string", enum: itemsHere },
          },
          required: ["item"],
        },
      });
    }

    // Use actions
    if (this.inventory.length > 0) {
      actions.push({
        name: "use",
        description: "Use an item",
        parameters: {
          type: "object",
          properties: {
            item: { type: "string", enum: this.inventory },
          },
          required: ["item"],
        },
      });
    }

    // Talk actions
    const npcsHere = this.getNPCsInCurrentRoom();
    if (npcsHere.length > 0) {
      actions.push({
        name: "talk",
        description: "Talk to someone",
        parameters: {
          type: "object",
          properties: {
            npc: { type: "string", enum: npcsHere },
          },
          required: ["npc"],
        },
      });
    }

    // Examine actions
    actions.push({
      name: "examine",
      description: "Examine the room or an item",
      parameters: {
        type: "object",
        properties: {
          target: { type: "string" },
        },
        required: ["target"],
      },
    });

    return actions;
  };

  act = (actions: Action[]): string[] => {
    const responses: string[] = [];
    for (const action of actions) {
      switch (action.name) {
        case "move":
          responses.push(this.move(action.parameters.direction as string));
          break;
        case "take":
          responses.push(this.take(action.parameters.item as string));
          break;
        case "use":
          responses.push(this.use(action.parameters.item as string));
          break;
        case "talk":
          responses.push(this.talk(action.parameters.npc as string));
          break;
        case "examine":
          responses.push(this.examine(action.parameters.target as string));
          break;
        default:
          responses.push("Unknown action.");
          break;
      }
    }
    return responses;
  };

  private getDescription(): string {
    const room = this.rooms[this.currentRoom];
    let description = room.description;

    const itemsInRoom = this.getItemsInCurrentRoom();
    if (itemsInRoom.length > 0) {
      description += ` You see here: ${itemsInRoom.join(", ")}.`;
    }

    const npcsInRoom = this.getNPCsInCurrentRoom();
    if (npcsInRoom.length > 0) {
      description += ` You notice: ${npcsInRoom.join(", ")}.`;
    }

    description += `\nExits are: ${Object.keys(room.connections).join(", ")}.`;
    return description;
  }

  private getItemsInCurrentRoom(): string[] {
    return Object.entries(this.itemLocations)
      .filter(([_, location]) => location === this.currentRoom)
      .map(([item, _]) => item);
  }

  private getNPCsInCurrentRoom(): string[] {
    return Object.entries(this.npcs)
      .filter(([_, npc]) => npc.location === this.currentRoom)
      .map(([name, _]) => name);
  }

  private move(direction: string): string {
    const room = this.rooms[this.currentRoom];
    const nextRoomName = room.connections[direction];
    if (!nextRoomName) {
      return "You can't go that way.";
    }
    const nextRoom = this.rooms[nextRoomName];

    // Special condition for secret chamber
    if (
      nextRoomName === "secret chamber" &&
      !this.rooms["dungeon"].secretRevealed
    ) {
      return "You don't see a way down from here.";
    }

    if (nextRoom.locked) {
      if (
        nextRoom.requiresKey &&
        this.inventory.includes(nextRoom.requiresKey)
      ) {
        nextRoom.locked = false;
        this.currentRoom = nextRoomName;
        return `You use the ${nextRoom.requiresKey} to unlock the ${direction} door. You move to the ${nextRoomName}.`;
      } else {
        return "The door is locked. You need a key.";
      }
    }

    this.currentRoom = nextRoomName;
    return `You move ${direction} to the ${nextRoomName}.`;
  }

  private take(item: string): string {
    // Special condition for the secret chamber
    if (
      this.currentRoom === "secret chamber" &&
      !this.inventory.includes("silver sword") &&
      (item === "golden key" || item === "ancient tome")
    ) {
      return "A shadowy figure blocks your way. You need a weapon to proceed.";
    }
    if (this.itemLocations[item] === this.currentRoom) {
      this.inventory.push(item);
      this.itemLocations[item] = null;
      return `You take the ${item}.`;
    } else {
      return `There is no ${item} here.`;
    }
  }

  private use(item: string): string {
    if (!this.inventory.includes(item)) {
      return `You don't have a ${item}.`;
    }
    if (
      item === "ancient tome" &&
      this.currentRoom === "tower" &&
      this.inventory.includes("mystic amulet")
    ) {
      this.won = true;
      return "You combine the ancient tome with the mystic amulet. A portal opens, and you step through it to freedom. You win!";
    } else if (item === "ancient tome" && this.currentRoom === "tower") {
      return "You try to use the ancient tome, but something is missing.";
    } else {
      return `You can't use the ${item} here.`;
    }
  }

  private talk(npcName: string): string {
    const npc = this.npcs[npcName];
    if (!npc || npc.location !== this.currentRoom) {
      return `There is no ${npcName} here.`;
    }
    let response = npc.dialogue;
    if (npc.requiredItem && this.inventory.includes(npc.requiredItem)) {
      if (npc.givesItem && !this.inventory.includes(npc.givesItem)) {
        this.inventory.push(npc.givesItem);
        response += ` The ${npcName} gives you a ${npc.givesItem}.`;
      }
    }
    return response;
  }

  private examine(target: string): string {
    if (target === "old map" && this.inventory.includes("old map")) {
      this.rooms["dungeon"].connections["down"] = "secret chamber";
      this.rooms["dungeon"].secretRevealed = true;
      return "You examine the old map and discover a hidden passage in the dungeon.";
    } else if (
      target === "ancient tome" &&
      this.inventory.includes("ancient tome")
    ) {
      return "The ancient tome bears an inscription: 'When amulet and tome unite, the path shall be revealed.'";
    } else if (this.rooms[target]) {
      return this.rooms[target].description;
    } else if (
      this.itemLocations[target] === this.currentRoom ||
      this.inventory.includes(target)
    ) {
      return `It's the ${target}. It might be useful.`;
    } else {
      return "You don't see that here.";
    }
  }
}

// Function to win the game
function winGame() {
  const game = new AdventureInTheHauntedCastle();
  let observation = game.observe();
  console.log(observation.message);

  // Move north to the library
  console.log(game.act([{ name: "move", parameters: { direction: "north" } }]));
  observation = game.observe();
  console.log(observation.message);

  // Take the old map
  console.log(game.act([{ name: "take", parameters: { item: "old map" } }]));
  observation = game.observe();
  console.log(observation.message);

  // Talk to the ghostly figure
  console.log(
    game.act([{ name: "talk", parameters: { npc: "ghostly figure" } }])
  );
  observation = game.observe();
  console.log(observation.message);

  // Move south back to the entrance hall
  console.log(game.act([{ name: "move", parameters: { direction: "south" } }]));
  observation = game.observe();
  console.log(observation.message);

  // Move east to the garden
  console.log(game.act([{ name: "move", parameters: { direction: "east" } }]));
  observation = game.observe();
  console.log(observation.message);

  // Take the rusty key
  console.log(game.act([{ name: "take", parameters: { item: "rusty key" } }]));
  observation = game.observe();
  console.log(observation.message);

  // Move west back to the entrance hall
  console.log(game.act([{ name: "move", parameters: { direction: "west" } }]));
  observation = game.observe();
  console.log(observation.message);

  // Move west to the dungeon
  console.log(game.act([{ name: "move", parameters: { direction: "west" } }]));
  observation = game.observe();
  console.log(observation.message);

  // Take the silver sword
  console.log(
    game.act([{ name: "take", parameters: { item: "silver sword" } }])
  );
  observation = game.observe();
  console.log(observation.message);

  // Examine the old map to reveal the secret chamber
  console.log(
    game.act([{ name: "examine", parameters: { target: "old map" } }])
  );
  observation = game.observe();
  console.log(observation.message);

  // Move down to the secret chamber
  console.log(game.act([{ name: "move", parameters: { direction: "down" } }]));
  observation = game.observe();
  console.log(observation.message);

  // Take the golden key and ancient tome
  console.log(game.act([{ name: "take", parameters: { item: "golden key" } }]));
  console.log(
    game.act([{ name: "take", parameters: { item: "ancient tome" } }])
  );
  observation = game.observe();
  console.log(observation.message);

  // Move up back to the dungeon
  console.log(game.act([{ name: "move", parameters: { direction: "up" } }]));
  observation = game.observe();
  console.log(observation.message);

  // Move east to the entrance hall
  console.log(game.act([{ name: "move", parameters: { direction: "east" } }]));
  observation = game.observe();
  console.log(observation.message);

  // Move north to the library
  console.log(game.act([{ name: "move", parameters: { direction: "north" } }]));
  observation = game.observe();
  console.log(observation.message);

  // Examine the ancient tome in the library
  console.log(
    game.act([{ name: "examine", parameters: { target: "ancient tome" } }])
  );
  observation = game.observe();
  console.log(observation.message);

  // Move east to the tower
  console.log(game.act([{ name: "move", parameters: { direction: "east" } }]));
  observation = game.observe();
  console.log(observation.message);

  // Use the ancient tome in the tower to win the game
  console.log(
    game.act([{ name: "use", parameters: { item: "ancient tome" } }])
  );
  observation = game.observe();
  console.log(observation.message);

  console.log("Game won:", observation.won);
}

// Run the function to win the game
// winGame();

async function interactiveGame() {
  const game = new AdventureInTheHauntedCastle();
  const rl = readline.createInterface({
    input: process.stdin,
    output: process.stdout,
  });

  console.log("Welcome to Adventure in the Haunted Castle!");
  console.log(game.observe().message);

  const promptUser = (): void => {
    rl.question("\nWhat do you want to do? ", (input) => {
      const [actionName, ...args] = input.trim().split(" ");
      const action = game
        .availableActions()
        .find((a) => a.name === actionName.toLowerCase());

      if (!action) {
        console.log("Invalid action. Try again.");
        promptUser();
        return;
      }

      const parameters: any = {};
      switch (action.name) {
        case "move":
          if (args.length === 0) {
            console.log("Please specify a direction to move.");
            promptUser();
            return;
          }
          parameters.direction = args[0];
          break;
        case "take":
          if (args.length === 0) {
            console.log("Please specify an item to take.");
            promptUser();
            return;
          }
          parameters.item = args.join(" ");
          break;
        case "use":
          if (args.length === 0) {
            console.log("Please specify an item to use.");
            promptUser();
            return;
          }
          parameters.item = args.join(" ");
          break;
        case "talk":
          if (args.length === 0) {
            console.log("Please specify someone to talk to.");
            promptUser();
            return;
          }
          parameters.npc = args.join(" ");
          break;
        case "examine":
          if (args.length === 0) {
            console.log("Please specify something to examine.");
            promptUser();
            return;
          }
          parameters.target = args.join(" ");
          break;
        default:
          console.log("Unknown action.");
          promptUser();
          return;
      }

      const responses = game.act([{ name: action.name, parameters }]);
      responses.forEach((response) => console.log(response));
      console.log(game.observe().message);

      if (game.observe().won) {
        console.log("Congratulations! You've won the game!");
        rl.close();
      } else {
        promptUser();
      }
    });
  };

  promptUser();
}

// Run the interactive game
// interactiveGame();
