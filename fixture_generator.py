from typing import Optional, Tuple, List, Any
from datetime import (
    datetime,
    timezone,
)

from utils import (
    resolve_schema,
)
from type import (
    JSON,
    FixtureBundle,
    OpenAPINormalized,
)
from data_generator import DataGenerator

# Common auth/error packs any enterprise API tends to exhibit.
DEFAULT_ERROR_TEMPLATES = {
            401: {"message": "Unauthorized", "error": "invalid_token"},
            403: {"message": "Forbidden", "error": "insufficient_scope"},
            404: {"message": "Not Found", "error": "resource_missing"},
            409: {"message": "Conflict", "error": "conflict"},
            422: {"message": "Unprocessable Entity", "error": "validation_error", "details": []},
            429: {"message": "Too Many Requests", "error": "rate_limited", "retry_after": 1},
            500: {"message": "Internal Server Error", "error": "server_error"},
        }

class FixtureGenerator:
    """
    Generate seeded, spec-true fixtures from an OpenAPI dict.
    """

    # TODO: Add Postman/HAR ingestion to complement OpenAPI.
    # TODO: Learn behaviors from real traces to augment synthetic examples.
    # TODO: Emit per-operation latency distributions derived from SLAs.

    def __init__(self, data_generator: DataGenerator) -> None:
        self.now = datetime.now(timezone.utc)

        self.default_error_templates = DEFAULT_ERROR_TEMPLATES

        self.data_generator = data_generator
    
    def generate(
            self,
            spec: JSON,
            service_name: str = "default",
            ) -> FixtureBundle:
        
        open_api_spec = OpenAPINormalized.from_dict(spec)
        services: JSON = {
            service_name: {
                "operations": {},
                "collections": {},
                "policies": {},
            }
        }

        op_fixtures, collection_hints = self._build_operation_fixtures(
            open_api_spec
        )
        collections = self._synthesize_collections(
            collection_hints
        )

        services[service_name]["operations"] = op_fixtures
        services[service_name]["collections"] = collections

        profiles = {
            "happy-path": {
                "latency_ms": {
                    "p50": 80, 
                    "p95": 250
                    }, 
                    "flake_5xx_percent": 0.0
                    },
            "chaos-10": {
                "latency_ms": {
                    "p50": 120, 
                    "p95": 400}, 
                    "flake_5xx_percent": 10.0
                    },
        }

        metadata = {
            "seed": self.data_generator.seed, 
            "generated_at": self.now.isoformat(), 
            "generator": "FixtureGenerator/v1"
            }
        
        return FixtureBundle(
            services=services,
            profiles=profiles,
            metadata=metadata,
        )
    
    def _build_operation_fixtures(
            self,
            open_api_spec: OpenAPINormalized
    ) -> Tuple[JSON, List[JSON]]:
        
        ops: JSON = {}
        collection_hints: List[JSON] = []

        for path, methods in open_api_spec.paths.items():
            if not isinstance(methods, dict):
                continue

            for method, op in methods.items():
                method_upper = method.upper()
                if method_upper not in {
                    "GET",
                    "POST",
                    "PUT", 
                    "PATCH", 
                    "DELETE",
                }:
                    continue
                
                key = f"{method_upper} {path}"
                op_id = op.get("operationId") or key # for sparse specs, we synthesize an op ID.

                success_response_body, isSuccess = self._synthesize_success(
                    open_api_spec,
                    op,
                )
                erroneous_response_bodies = self._synthesize_errors(
                    open_api_spec,
                    op,
                )

                ops[key] = {
                    "operation_id": op_id,
                    "success": {
                        "status": isSuccess, 
                        "body": success_response_body
                        },
                    "errors": erroneous_response_bodies,
                    "pagination": self._infer_pagination_meta(op),
                    "auth_required": self._infer_auth_required(open_api_spec),
                }

                if method_upper == "GET" and isinstance(
                    success_response_body, 
                    list
                    ):
                    seg = path.rstrip("/").split("/")[-1]

                    if seg \
                        and seg.endswith("s") \
                        and "{" not in seg:
                        
                        collection_hints.append(
                            {
                                "collection": seg, 
                                "sample": success_response_body
                            }
                        )
                
        return (
            ops,
            collection_hints,
        )
            
    def _synthesize_success(
            self,
            open_api_spec: OpenAPINormalized,
            op: JSON,
    ) -> Tuple[Any, int]:
        
        responses = op.get("responses", {})

        success_code = self._get_success_status(
            responses=responses
        )

        schema = self._extract_json_schema(
            open_api_spec,
            responses.get(
                str(success_code), 
                {}
            ),
        )

        response_body = self.data_generator.generate(
            open_api_spec,
            schema,
        ) if schema else self.data_generator.generate_sensible_default()

        return (
            response_body,
            success_code
        )

    
    def _get_success_status(
        self,
        responses: JSON,
    ) -> int:
        
        if not responses:
            return 200
        
        codes: List[int] = []

        for k in responses.keys():
            if isinstance(k, int) and 200 <= k < 300:
                codes.append(k)
            elif isinstance(k, str) and k.isdigit():

                ki = int(k)
                
                if 200 <= ki < 300:
                    codes.append(ki)

        return min(codes) if codes else 200
    
    def _synthesize_errors(
        self,
        open_api_spec: OpenAPINormalized,
        op: JSON,
    ) -> JSON:
        erroneous_response: JSON = {}
        defined_responses = op.get("responses", {}) or {}

        def _as_int(code: Any) -> Optional[int]:
            if isinstance(code, int):
                return code
            if isinstance(code, str) and code.isdigit():
                return int(code)
            return None  # "default", "2XX", "3XX", etc.

        for status_code, metadata in defined_responses.items():
            code_int = _as_int(status_code)

            if code_int is None:
                # Treat "default" and pattern keys as a generic 500 unless a 4xx/5xx exists later
                schema = self._extract_json_schema(open_api_spec, metadata)
                if schema:
                    erroneous_response.setdefault(
                        500, self.data_generator.generate(open_api_spec, schema)
                    )
                continue

            if 200 <= code_int < 300:
                continue  # success handled elsewhere

            schema = self._extract_json_schema(open_api_spec, metadata)
            if schema:
                erroneous_response[code_int] = self.data_generator.generate(open_api_spec, schema)
            else:
                erroneous_response[code_int] = self.default_error_templates.get(
                    code_int, {"message": "Error"}
                )

        for code_int, template in self.default_error_templates.items():
            erroneous_response.setdefault(code_int, template)

        return erroneous_response

    
    def _extract_json_schema(
            self,
            open_api_spec: OpenAPINormalized,
            response_or_params: JSON,
    ) -> Optional[JSON]:
        
        content = response_or_params.get("content", {})
        if not content:
            return None
        
        # Prefer application/json; otherwise pick the first */*+json vendor type; finally any json-ish
        schema = None
        if "application/json" in content:
            schema = content["application/json"].get("schema")
        
        if not schema:
            # find vendor-specific json types, e.g., application/vnd.github+json
            for mt, body in content.items():
                if isinstance(mt, str) and mt.endswith("+json"):
                    schema = (body or {}).get("schema")
                    if schema:
                        break
        if not schema:
            # last resort: any media type whose name contains 'json'
            for mt, body in content.items():
                if isinstance(mt, str) and "json" in mt:
                    schema = (body or {}).get("schema")
                    if schema:
                        break

        if not schema:
            return None

        return resolve_schema(
            open_api_spec, 
            schema
            )
    
    def _synthesize_collections(
            self,
            hints: List[JSON],
    ) -> JSON:
        output: JSON = {}
        for hint in hints:
            name = hint["collection"]
            sample = hint.get("sample") or []
            items = []
            template = sample[0] if sample else {}

            for _ in range(max(3, len(sample))):
                if isinstance(template, dict):
                    obj=dict(template)
                    obj.setdefault(
                        "id", 
                        self.data_generator.generate_id()
                        )
                    items.append(obj)
                else:
                    items.append({
                        "id": self.data_generator.generate_id(),
                        "title": "Auto Item", 
                        "state": "open",
                    })
            
            output[name] = {
                "items": items,
                "cursor": None,
                "next_id": self.data_generator.generate_id()
            }
        
        return output
    
    def _infer_pagination_meta(
            self,
            op: JSON,
    ) -> Optional[JSON]:
        params = op.get(
            "parameters",
            []
        )
        names = {
            param.get("name") \
            for param in params \
            if isinstance(param, dict)
        }

        if {
            "page", 
            "per_page"
            } & names:

            return {
                "style": "page",
                "params": [
                    "page",
                    "per_page"
                ]
            }
        if {
            "limit", 
            "cursor"
            } & names:

            return {
                "style": "cursor", 
                "params": [
                    "limit", 
                    "cursor"
                    ]
                }

        return None
    
    def _infer_auth_required(self, open_api_spec: OpenAPINormalized) -> bool:
        
        components = getattr(
            open_api_spec, 
            "components", 
            {}
            )

        return bool(
            components.get("securitySchemes")
            )

            


        
        


        

