from typing import Union
from pathlib import Path

from type import (
    ToolCall,
    MockedResponse,
    Recording,
)
from utils import (
    safe_mkdir,
)

class Recorder:
    def __init__(
            self,
            output_dir: Union[str, Path] = "recordings",      
    ):
        self.output_dir = safe_mkdir(output_dir)
    
    def record(
            self,
            invocation: ToolCall,
            response: MockedResponse,
    ) -> Path:
        
        recording = Recording(
            tool_id=invocation.tool_id,
            tool_name=invocation.tool_name,
            args=invocation.args,
            response=response,
            timestamp=invocation.timestamp
        )

        return recording.save(self.output_dir)