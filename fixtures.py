from pathlib import Path
from typing import Union, Optional
import json

from utils import (
    safe_mkdir,
)
from type import (
    Fixture,
)

class FixtureStore:
    """
    File-system backed fixtures organized as:
        fixtures/{tool_name}/{signature}.json
    
    Plug-and-play: users can drop JSON files in the right folder and the sandbox will
    serve them without writing handlers or having real creds.
    """

    def __init__(
            self, 
            root: Union[str, Path] = "fixtures"
            ):
        self.root = safe_mkdir(root)
    
    def _make_tool_dir(self, tool_name: str) -> Path:
        return (
            safe_mkdir(self.root / tool_name)
        )
    
    def get_path_for_fixture(
            self,
            tool_name: str,
            signature: str,
    ) -> Path:
        
        return (
            self._make_tool_dir(tool_name) / f"{signature}.json"
        )
    
    def load(
            self,
            tool_name: str,
            signature: str
    ) -> Optional[Fixture]:
        
        fixture_path = self.get_path_for_fixture(
            tool_name=tool_name,
            signature=signature,
        )
        if not fixture_path.exists():
            return None
        
        with fixture_path.open("r", encoding="utf-8") as f:
            return Fixture.load_from_json(
                fixture=json.load(f)
            )
    
    def save(
            self,
            tool_name: str,
            signature: str,
            fixture: Fixture,
    ) -> Path:
        
        path = self.get_path_for_fixture(
            tool_name=tool_name,
            signature=signature,
        )
        with path.open("w", encoding="utf-8") as f:
            json.dump(
                fixture.to_json(),
                f,
                indent=2,
                ensure_ascii=False,
                sort_keys=True,
            )
        
        return path
