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

        out: List[Dict[str, Any]] = []
        for name in self.sandbox.api_ops_router.list_ops():

            op = self.sandbox.api_ops_router.get_op(name)
            out.append(
                {
                    "name": op.name,
                    "description": getattr(op, "description", ""),
                    "input_schema": op.param_schema,
                    "result_schema": op.result_schema,
                    "version": getattr(op, "version", "v1"),
                }
            )
            
        return out