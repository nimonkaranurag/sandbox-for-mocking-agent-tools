from __future__ import annotations

from typing import Dict, Tuple, Any, Optional
import time

from type import (
    Policy,
    ToolCall,
    MockedResponse,
    FaultProfile
    )
from utils import (
    Recorder,
    ToolsRegistry,
    stable_hash
    )

class Sandbox:
    def __init__(
            self,
            policy: Policy,
            recorder: Recorder,
            registry: ToolsRegistry,
            fault: Optional[FaultProfile] = None,
    ):
        self.policy = policy
        self.recorder = recorder
        self.registry = registry
        self.fault = fault or FaultProfile()

    def invoke(
            self,
            tool_name: str,
            args: Dict[str, Any],
            record: Optional[bool] = False
    ) -> Tuple[ToolCall, MockedResponse]:
        
        allowed, reason = self.policy.is_allowed(tool_name)
        if not allowed:
            response = MockedResponse(
                ok=False,
                error=reason,
                latency_ms=0
            )
            invocation = ToolCall(
                tool_name=tool_name,
                args=args,
                tool_id=stable_hash(tool_name, args),
                timestamp=time.time()
            )

            if record and self.recorder:
                self.recorder.record(
                    invocation=invocation,
                    response=response
                )
            
            return (
                invocation,
                response
            )
        
        tool = self.registry.get(tool_name)
        tool_id = stable_hash(tool_name, args)

        latency = self.fault.sample_latency(tool_id)
        time.sleep(latency / 1000.0)

        if self.fault.should_error(tool_id):
            response = MockedResponse(
                ok=False, 
                error="Injected failure (simulated).", 
                latency_ms=latency, 
                tool_version=tool.version
                )
        else:
            try:
                data = tool.invoke(args)
                response = MockedResponse(
                    ok=True,
                    data=data,
                    latency_ms=latency,
                    tool_version=tool.version
                )
            except Exception as e:
                response = MockedResponse(
                    ok=False,
                    error=f"Handler Error: {e}",
                    latency_ms=latency,
                    tool_version=tool.version,
                )
        
        invocation = ToolCall(
            tool_name=tool_name,
            args=args,
            tool_id=tool_id,
            timestamp=time.time()
        )

        if record and self.recorder:
            self.recorder.record(
                invocation=invocation,
                response=response
            )
        
        return (
            invocation,
            response
        )