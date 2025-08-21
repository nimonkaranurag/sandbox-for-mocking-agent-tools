from __future__ import annotations

from typing import Dict, Tuple, Any, Optional
import time

from type import (
    Policy,
    ToolCall,
    MockedResponse,
    FaultProfile,
    Fixture,
    FixtureMetaData,
    )
from utils import (
    stable_hash
    )
from recorder import Recorder
from fixtures import FixtureStore
from api_ops_router import APIOperationsRouter
from generator import DataGenerator

class Sandbox:
    def __init__(
            self,
            policy: Policy,
            recorder: Recorder,
            fault: Optional[FaultProfile] = None,
            fixtures: Optional[FixtureStore] = None,
            api_ops_router: Optional[APIOperationsRouter] = None,
            data_generator: Optional[DataGenerator] = None,
    ):
        self.policy = policy
        self.recorder = recorder
        self.fault = fault or FaultProfile()
        self.fixtures = fixtures or FixtureStore()
        self.api_ops_router = api_ops_router or APIOperationsRouter()
        self.data_generator = data_generator or DataGenerator()

    def invoke(
            self,
            tool_name: str,
            args: Dict[str, Any],
            record: Optional[bool] = False
    ) -> Tuple[ToolCall, MockedResponse]:
        
        timestamp = time.time()
        tool_id = stable_hash(tool_name, args)
        latency = self.fault.sample_latency(
            key=tool_id
        )
        
        # Check policy compliance
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
                tool_id=tool_id,
                timestamp=str(timestamp),
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
        
        # Translate a cached fixture into a mocked tool response
        cached_fixture = self.fixtures.load(
                tool_name=tool_name,
                signature=tool_id,
            )
        if cached_fixture:

            response = MockedResponse(
                ok=cached_fixture.ok,
                data=cached_fixture.data,
                error=cached_fixture.error,
                latency_ms=cached_fixture.latency_ms or latency,
            )

            if not response.latency_ms:
                response.latency_ms = latency
            
            time.sleep(response.latency_ms / 1000.0)
            
            invocation = ToolCall(
                tool_name=tool_name,
                args=args,
                tool_id=tool_id,
                timestamp=str(timestamp),
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
        
        # Synthesize response from spec (no cached fixture for this tool)
        try:
            op = self.api_ops_router.get_op(name=tool_name)
        except KeyError as e:
            
            time.sleep(latency / 1000.0)

            response = MockedResponse(
                ok=False,
                error=str(e),
                latency_ms=latency
            )
            invocation = ToolCall(
                tool_name=tool_name,
                args=args,
                tool_id=tool_id,
                timestamp=str(timestamp)
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

        #TODO: Validate args against param schema
        time.sleep(latency / 1000.0)

        if self.fault.should_error(tool_id):
            response = MockedResponse(
                ok=False, 
                error="Injected failure (simulated).", 
                latency_ms=latency
                )
        else:
            data = self.data_generator.generate(
                op.result_schema
            )
            response = MockedResponse(
                ok=True,
                data=data,
                latency_ms=latency,
            )

        invocation = ToolCall(
            tool_name=tool_name,
            args=args,
            tool_id=tool_id,
            timestamp=str(timestamp)
        )
        
        # Cache the generated fixture
        fixture = Fixture(
            ok=response.ok,
            data=response.data,
            error=response.error,
            latency_ms=response.latency_ms,
            metadata=FixtureMetaData(
                created_at=str(timestamp),
                signature=tool_id,
                seed=str(
                    getattr(
                        self.fault,
                        "seed",
                        0
                    )
                )
            )
        )
        self.fixtures.save(
            tool_name=tool_name,
            signature=tool_id,
            fixture=fixture
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