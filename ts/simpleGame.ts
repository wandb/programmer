import { Action, Environment } from "./environment";

export class SimpleTextAdventure
  implements Environment<{ message: string; won: boolean }>
{
  private rooms: {
    [key: string]: {
      description: string;
      connections: { [direction: string]: string };
    };
  };
  private itemLocations: { [item: string]: string | null };
  private currentRoom: string;
  private inventory: string[];
  private won: boolean;

  constructor() {
    this.rooms = {
      start: {
        description:
          "You are in a dimly lit room. There are doors to the north and east.",
        connections: { north: "hallway", east: "library" },
      },
      hallway: {
        description:
          "You are in a long hallway. There are doors to the south and east.",
        connections: { south: "start", east: "treasure" },
      },
      library: {
        description: "You are in a dusty library. There's a door to the west.",
        connections: { west: "start" },
      },
      treasure: {
        description:
          "You are in a room with a large treasure chest. There's a door to the west.",
        connections: { west: "hallway" },
      },
    };
    this.itemLocations = {
      "golden key": "library",
    };
    this.currentRoom = "start";
    this.inventory = [];
    this.won = false;
  }

  save = () => {
    return JSON.parse(
      JSON.stringify({
        currentRoom: this.currentRoom,
        inventory: this.inventory,
        won: this.won,
        itemLocations: this.itemLocations,
      })
    );
  };

  load = (state: {
    currentRoom: string;
    inventory: string[];
    won: boolean;
    itemLocations: { [item: string]: string | null };
  }) => {
    const loaded = new SimpleTextAdventure();
    loaded.currentRoom = state.currentRoom;
    loaded.inventory = state.inventory;
    loaded.won = state.won;
    loaded.itemLocations = state.itemLocations;
    return loaded;
  };

  observe = () => ({ message: this.getDescription(), won: this.won });

  availableActions = () => [
    {
      name: "move",
      description: "Move in a direction",
      parameters: {
        type: "object",
        properties: {
          direction: {
            type: "string",
            enum: Object.keys(this.rooms[this.currentRoom].connections),
          },
        },
        required: ["direction"],
      },
    },
    {
      name: "take",
      description: "Take an item",
      parameters: {
        type: "object",
        properties: {
          item: { type: "string" },
        },
        required: ["item"],
      },
    },
    {
      name: "use",
      description: "Use an item",
      parameters: {
        type: "object",
        properties: {
          item: { type: "string" },
        },
        required: ["item"],
      },
    },
  ];

  act = (actions: Action[]): string[] => {
    const actionResponses = [];
    for (const action of actions) {
      switch (action.name) {
        case "move":
          actionResponses.push(
            this.move(action.parameters.direction as string)
          );
          break;
        case "take":
          actionResponses.push(this.take(action.parameters.item as string));
          break;
        case "use":
          actionResponses.push(this.use(action.parameters.item as string));
          break;
      }
    }
    return actionResponses;
  };

  private getDescription(): string {
    const room = this.rooms[this.currentRoom];
    let description = room.description;
    const itemsInRoom = Object.entries(this.itemLocations)
      .filter(([_, location]) => location === this.currentRoom)
      .map(([item, _]) => item);
    if (itemsInRoom.length > 0) {
      description += ` There is a ${itemsInRoom.join(", ")} here.`;
    }
    if (this.inventory.length > 0) {
      description += ` You are carrying: ${this.inventory.join(", ")}.`;
    }
    return description;
  }

  private move(direction: string): string {
    const nextRoom = this.rooms[this.currentRoom].connections[direction];
    if (nextRoom) {
      this.currentRoom = nextRoom;
      return `You moved to the ${nextRoom} room.`;
    } else {
      return "You can't go that way.";
    }
  }

  private take(item: string): string {
    if (this.itemLocations[item] === this.currentRoom) {
      if (this.inventory.includes(item)) {
        throw new Error("Programming error: item already in inventory.");
      }
      this.inventory.push(item);
      this.itemLocations[item] = null;
      return `You took the ${item}.`;
    } else {
      return "There's no such item here.";
    }
  }

  private use(item: string): string {
    if (
      this.inventory.includes(item) &&
      this.currentRoom === "treasure" &&
      item === "golden key"
    ) {
      this.won = true;
      return "You used the golden key to open the treasure chest. You win!";
    } else {
      return "You can't use that here.";
    }
  }
}

async function main() {
  const game = new SimpleTextAdventure();
  console.log(game.observe());

  game.act([{ name: "move", parameters: { direction: "east" } }]);
  console.log(game.observe());

  game.act([{ name: "take", parameters: { item: "golden key" } }]);
  console.log(game.observe());

  game.act([{ name: "move", parameters: { direction: "west" } }]);
  console.log(game.observe());

  game.act([{ name: "move", parameters: { direction: "north" } }]);
  console.log(game.observe());

  game.act([{ name: "move", parameters: { direction: "east" } }]);
  console.log(game.observe());

  game.act([{ name: "use", parameters: { item: "golden key" } }]);
  console.log(game.observe());

  console.log("Game won:", game.observe().won);

  // Test save and load
  const savedState = game.save();
  console.log("Saved state:", savedState);

  const loadedGame = game.load(savedState);
  console.log("Loaded game state:", loadedGame.observe());
}

// main().catch(console.error);
