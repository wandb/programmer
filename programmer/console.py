import sys
from rich.console import Console as RichConsole
from rich.padding import Padding

# Adjusting import to absolute path
from .settings_manager import SettingsManager

console = RichConsole()


class Console:
    @staticmethod
    def welcome() -> None:
        console.rule("[bold blue]Programmer")
        console.print("Welcome to programmer.\n")

    @staticmethod
    def step_start(name: str, color: str) -> None:
        console.rule(f"[bold {color}]Begin {name} step")

    @staticmethod
    def chat_response_start() -> None:
        pass

    @staticmethod
    def chat_message_content_delta(message_content_delta: str) -> None:
        console.print(message_content_delta, end="")

    @staticmethod
    def chat_response_complete(agent_response: str) -> None:
        console.print("\n")

    @staticmethod
    def tool_call_start(tool_call: str) -> None:
        console.print(f"[bold yellow]Tool call: [/bold yellow]{tool_call}\n")

    @staticmethod
    def tool_call_complete(tool_response: str) -> None:
        lines = tool_response.split("\n")
        if len(lines) > 4:
            lines = lines[:4]
            lines.append("...")
            tool_response = "\n".join(lines)
        console.print(
            Padding.indent(f"{tool_response}\n", 4),
            no_wrap=True,
            overflow="ellipsis",
        )

    @staticmethod
    def user_input_complete(user_input: str) -> None:
        console.print()

    @staticmethod
    def settings_command(command_args):
        if len(command_args) < 2:
            console.print("[red]Invalid settings command[/red]")
            return
        action = command_args[0]
        key = command_args[1]
        if action == "get":
            value = SettingsManager.get_setting(key)
            if value is not None:
                console.print(f"{key} = {value}")
            else:
                console.print(f"[red]Setting '{key}' not found[/red]")
        elif action == "set" and len(command_args) == 3:
            value = command_args[2]
            SettingsManager.set_setting(key, value)
            console.print(f"[green]Setting '{key}' updated to '{value}'[/green]")
        else:
            console.print("[red]Invalid settings command[/red]")


# Example of integrating a basic command line argument parsing
if __name__ == "__main__":
    SettingsManager.initialize_settings()
    if len(sys.argv) > 1 and sys.argv[1] == "settings":
        Console.settings_command(sys.argv[2:])
    else:
        Console.welcome()
