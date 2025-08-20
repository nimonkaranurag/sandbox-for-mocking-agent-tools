from typing import List, Dict, Any

from sandbox import Sandbox


class Adapter:
    """
    Basic MCP Adapter
    Maps:
        - Tool schema <-> MCP tool schema
        - Invocation envelope <-> JSON RPC / LSP transport
    """
    # TODO: implement server handshake, resource list, tool call, streaming.
    def __init__(
            self,
            sandbox: Sandbox
    ) -> None:
       self.sandbox = sandbox

    def describe_tools(self) -> List[Dict[str, Any]]:

        registry = self.sandbox.registry
        out = []
        for tool_name in registry.list():
            tool = registry.get(tool_name)
            out.append({
                "name": tool.name,
                "description": tool.description,
                "input_schema": tool.param_schema,
                "version": tool.version,
            }
            )
        
        return out