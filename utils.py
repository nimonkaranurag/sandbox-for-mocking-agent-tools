from __future__ import annotations

from pathlib import Path
from typing import Union, Any, Dict, TYPE_CHECKING
import hashlib
import json
import re

JSON = Dict[str, Any]
if TYPE_CHECKING:
    from type import OpenAPINormalized

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

def resolve_schema(
            open_api_spec: "OpenAPINormalized",
            schema: JSON,
    ) -> JSON:
        
        if "$ref" not in schema:
            return schema
        
        ref = schema["$ref"]
        
        # Simple $ref resolver for #/components/schemas/*
        # $ref is usually a JSON Pointer string: `/components/schemas/Issue`
        # The regex #/components/schemas/(?P<name>.+) pulls out "Issue"
        m = re.match(r"#/components/schemas/(?P<name>.+)", ref)
        if not m:
            return schema
        
        name = m.group("name")
        resolved = open_api_spec.schemas.get(name)
        
        return resolved or schema # fall back to returning the original {"$ref": ...}
        
