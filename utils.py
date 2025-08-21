from __future__ import annotations

from pathlib import Path
from typing import Union, Any
import hashlib
import json

def safe_mkdir(
        path: Union[str, Path]
) -> Path:
    
    if isinstance(path, str):
        path = Path(path)

    path.mkdir(
        parents=True,
        exist_ok=True
    )
    
    return path

def stable_hash(*parts: Any) -> str:
    
    payload = json.dumps(
        parts,
        separators=(",", ":"),
        sort_keys=True,
        default=str
    )

    return hashlib.sha256(
        payload.encode("utf-8")
        ).hexdigest()[:16]
        
        
