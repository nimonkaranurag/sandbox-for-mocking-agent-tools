# Sample Tools
from typing import Dict, Any
import dataclasses as dc

from utils import (
    ToolsRegistry,
    pretty,
    )
from type import (
    Tool,
    FaultProfile,
    )
from sandbox import Sandbox

def echo_handler(args: Dict[str, Any]) -> Dict[str, Any]:
    text = args.get("text", "")

    return {
        "echo": text, 
        "length": len(text)
        }

def sum_handler(args: Dict[str, Any]) -> Dict[str, Any]:

    nums = args.get("numbers", [])

    if not isinstance(nums, list) \
        or not all(isinstance(n, (int, float)) \
                   for n in nums):
        
        raise ValueError("`numbers` must be a list of ints/floats.")
    
    return {
        "sum": float(sum(nums)), 
        "count": len(nums)
        }

def build_sample_registry() -> ToolsRegistry:
    reg = ToolsRegistry()

    reg.register(
        Tool(
            name="echo",
            description="Return the same text with metadata.",
            parameters_schema={"type": "object", "properties": {"text": {"type": "string"}}, "required": ["text"]},
            handler=echo_handler,
            version="v1",
        )
    )

    reg.register(
        Tool(
            name="sum",
            description="Sum a list of numbers.",
            parameters_schema={
                "type": "object",
                "properties": {"numbers": {"type": "array", "items": {"type": "number"}}},
                "required": ["numbers"],
            },
            handler=sum_handler,
            version="v1",
        )
    )
    return reg


def demo() -> None:

    sb = Sandbox(
        build_sample_registry(), 
        FaultProfile(
            seed=42,
            min_latency_ms=20,
            max_latency_ms=120,
            error_rate=0.0
        )
        )
    
    print("== Tools:", sb.registry.list())

    print("\n-- echo --")
    r1 = sb.invoke("echo", {"text": "hello world"})
    print(pretty(dc.asdict(r1)))

    print("\n-- sum --")
    r2 = sb.invoke("sum", {"numbers": [1, 2, 3, 4.5]})
    print(pretty(dc.asdict(r2)))

if __name__ == "__main__":
    demo()