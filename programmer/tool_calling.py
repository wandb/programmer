import inspect
import json
import traceback

from typing import Callable, get_type_hints

from openai.types.chat import ChatCompletionMessageToolCall, ChatCompletionToolParam

from .console import Console


def generate_json_schema(func: Callable) -> dict:
    """Given a function, generate an OpenAI tool compatible JSON schema.

    WIP: This function is very basic and hacky. It will not work in many
    scenarios.
    """
    # Extract function signature
    signature = inspect.signature(func)
    parameters = signature.parameters

    # Extract annotations
    type_hints = get_type_hints(func)

    # Initialize the schema structure
    schema = {
        "type": "function",
        "function": {
            "name": func.__name__,
            "description": func.__doc__.split("\n")[0] if func.__doc__ else "",
            "parameters": {
                "type": "object",
                "properties": {},
                "required": [],
            },
        },
    }

    # Process each parameter
    for name, param in parameters.items():
        # Determine if this parameter is required (no default value)
        is_required = param.default == inspect.Parameter.empty

        # Extract parameter type and description
        param_type = type_hints[name].__name__ if name in type_hints else "string"
        if param_type == "str":
            param_type = "string"
        elif param_type == "int":
            param_type = "integer"
        param_desc = ""

        # Attempt to extract description from docstring
        if func.__doc__:
            doc_lines = func.__doc__.split("\n")[1:]
            for line in doc_lines:
                if name in line:
                    param_desc = line.strip().split(":")[-1].strip()
                    break

        # Populate schema for this parameter
        param_schema = {"type": param_type, "description": param_desc}

        # Handle special case for enums
        if hasattr(type_hints[name], "__members__"):  # Check if it's an Enum
            param_schema["enum"] = [e.value for e in type_hints[name]]

        schema["function"]["parameters"]["properties"][name] = param_schema  # type: ignore

        if is_required:
            schema["function"]["parameters"]["required"].append(name)  # type: ignore

    return schema


def chat_call_tool_params(tools: list[Callable]) -> list[ChatCompletionToolParam]:
    chat_tools = [generate_json_schema(tool) for tool in tools]
    return [ChatCompletionToolParam(**tool) for tool in chat_tools]


def get_tool(tools: list[Callable], name: str) -> Callable:
    for t in tools:
        if t.__name__ == name:
            return t
    raise KeyError(f"No tool with name {name} found")


def perform_tool_calls(
    tools: list[Callable], tool_calls: list[ChatCompletionMessageToolCall]
) -> list[dict]:
    messages = []
    for tool_call in tool_calls:
        function_name = tool_call.function.name
        tool = get_tool(tools, function_name)
        function_args = {}
        function_response = None
        tool_call_s = f"{function_name}({tool_call.function.arguments})"
        Console.tool_call_start(tool_call_s)
        try:
            function_args = json.loads(tool_call.function.arguments)
        except json.JSONDecodeError as e:
            print(f"Tool call {tool_call_s} failed to parse arguments: {e}")
            function_response = f"Argument parse error: {str(e)}"
        if not function_response:
            try:
                function_response = tool(**function_args)
            except Exception as e:
                print(f"Error occurred in tool {function_name}:")
                traceback.print_exc()
                function_response = f"Error: {str(e)}"

        additional_message = None
        if isinstance(function_response, tuple):
            additional_message = function_response[1]
            function_response = str(function_response[0])
        else:
            function_response = str(function_response)

        Console.tool_call_complete(function_response)
        messages.append(
            {
                "tool_call_id": tool_call.id,
                "role": "tool",
                "content": function_response,
            }
        )
        if additional_message:
            messages.append(additional_message)
    return messages
