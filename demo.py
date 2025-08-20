# Sample Tools
from typing import Dict, Any
import dataclasses as dc

from utils import (
    ToolsRegistry,
    Recorder,
    pretty,
    )
from type import (
    Tool,
    Policy,
    FaultProfile,
    )
from sandbox import Sandbox
from adapter import Adapter

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
    # Minimal policy — allow everything
    policy = Policy(allowed_tools=None, unallowed_tools=None)

    # Recorder to show record capability (writes ./recordings/<id>.json)
    recorder = Recorder(output_dir="recordings")

    # Deterministic latency; set error_rate=0.2 to see injected failures
    fault = FaultProfile(seed=42, min_latency_ms=20, max_latency_ms=120, error_rate=0.0)

    sb = Sandbox(policy=policy, recorder=recorder, registry=build_sample_registry(), fault=fault)

    print("== Tools:", sb.registry.list())

    print("\n-- echo --")
    inv1, r1 = sb.invoke("echo", {"text": "hello world"}, record=True)
    print(pretty(dc.asdict(r1)))

    print("\n-- sum --")
    inv2, r2 = sb.invoke("sum", {"numbers": [1, 2, 3, 4.5]}, record=True)
    print(pretty(dc.asdict(r2)))

    # Sanity Check
    print(pretty(Adapter(sb).describe_tools()))

if __name__ == "__main__":
    demo()