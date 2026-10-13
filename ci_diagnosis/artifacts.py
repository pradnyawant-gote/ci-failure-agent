"""Atomic Python data artifacts and a bounded reader that executes no file code.

Checksums detect accidental corruption, not adversarial authenticity. The reader
extracts literal payload assignments with AST and validates bounded compressed
JSON. Existing source files are never eligible for automatic replacement.
"""

from __future__ import annotations

import ast
import base64
import hashlib
import json
import math
import os
import tempfile
import zlib
from dataclasses import dataclass
from pathlib import Path
from typing import Any,NoReturn

from .probability import ValidationError
from .records import plain

MAGIC='"""Generated CI diagnosis data artifact, schema 2.'
LEGACY_MAGIC='"""Complete versioned evaluation ledger, compressed'


@dataclass(frozen=True)
class ArtifactLimits:
    source_bytes: int=32*1024*1024
    payload_bytes: int=128*1024*1024

    def __post_init__(self) -> None:
        if any(type(v) is not int or v<=0 for v in (self.source_bytes,self.payload_bytes)):
            raise ValidationError("artifact limits must be positive integers")


def _encode_special(value: Any) -> Any:
    if isinstance(value,float) and not math.isfinite(value):
        if math.isnan(value):
            raise ValidationError("NaN cannot be exported")
        return {"__infinite_metric__":1 if value>0 else -1}
    if isinstance(value,dict):
        if "__infinite_metric__" in value:
            raise ValidationError("reserved metric encoding key")
        return {k:_encode_special(v) for k,v in value.items()}
    if isinstance(value,(tuple,list)):
        return [_encode_special(v) for v in value]
    return value


def _pairs(pairs: list[tuple[str,Any]]) -> Any:
    result: dict[str,Any]={}
    for key,value in pairs:
        if key in result:
            raise ValidationError("duplicate JSON field")
        result[key]=value
    if "__infinite_metric__" in result:
        sign=result["__infinite_metric__"]
        if len(result)!=1 or type(sign) is not int or sign not in (-1,1):
            raise ValidationError("invalid infinite metric encoding")
        return math.inf*sign
    return result


def _invalid_constant(value: str) -> NoReturn:
    raise ValidationError("nonstandard JSON numeric constant")


def decode_payload(encoded: str, checksum: str, limits: ArtifactLimits | None=None) -> dict[str,Any]:
    limits=limits or ArtifactLimits()
    if not isinstance(encoded,str) or len(encoded)>limits.source_bytes:
        raise ValidationError("encoded artifact exceeds size limit")
    if not isinstance(checksum,str) or len(checksum)!=64:
        raise ValidationError("invalid artifact checksum")
    try:
        compressed=base64.b85decode(encoded)
        decoder=zlib.decompressobj()
        payload=decoder.decompress(compressed,limits.payload_bytes+1)
        if len(payload)>limits.payload_bytes or decoder.unconsumed_tail or not decoder.eof or decoder.unused_data:
            raise ValidationError("truncated, oversized or trailing compressed artifact")
        if hashlib.sha256(payload).hexdigest()!=checksum:
            raise ValidationError("artifact checksum mismatch")
        result=json.loads(payload,object_pairs_hook=_pairs,parse_constant=_invalid_constant)
    except (ValueError,TypeError,zlib.error,RecursionError,UnicodeError) as exc:
        raise ValidationError("invalid artifact payload") from exc
    if not isinstance(result,dict):
        raise ValidationError("artifact root must be an object")
    return result


def encode_python_artifact(result: object, limits: ArtifactLimits | None=None) -> str:
    limits=limits or ArtifactLimits()
    try:
        payload=json.dumps(_encode_special(plain(result)),ensure_ascii=True,sort_keys=True,
                           separators=(",",":"),allow_nan=False).encode("utf-8")
    except (TypeError,ValueError,RecursionError) as exc:
        raise ValidationError("result cannot be serialized") from exc
    if len(payload)>limits.payload_bytes:
        raise ValidationError("result exceeds payload limit")
    checksum=hashlib.sha256(payload).hexdigest()
    encoded=base64.b85encode(zlib.compress(payload,9)).decode("ascii")
    chunks="\n".join("    "+repr(encoded[i:i+120]) for i in range(0,len(encoded),120))
    text=(MAGIC+'\nSynthetic outcomes/costs are declared assumptions.\n"""\n'
          'from ci_diagnosis.artifacts import decode_payload\n\n'
          'PAYLOAD_SHA256 = '+repr(checksum)+'\n_ENCODED = (\n'+chunks+'\n)\n'
          'EVALUATION = decode_payload(_ENCODED, PAYLOAD_SHA256)\n')
    if len(text.encode("utf-8"))>limits.source_bytes:
        raise ValidationError("result exceeds source size limit")
    return text


def read_python_artifact(path: str | Path, limits: ArtifactLimits | None=None) -> dict[str,Any]:
    limits=limits or ArtifactLimits()
    path=Path(path)
    try:
        if path.stat().st_size>limits.source_bytes:
            raise ValidationError("artifact source exceeds size limit")
        tree=ast.parse(path.read_text(encoding="utf-8"),filename=str(path))
    except (OSError,SyntaxError,UnicodeError,RecursionError) as exc:
        raise ValidationError("cannot read artifact data") from exc
    values: dict[str,str]={}
    for node in tree.body:
        if isinstance(node,ast.Assign) and len(node.targets)==1 and isinstance(node.targets[0],ast.Name):
            name=node.targets[0].id
            if name in {"_ENCODED","PAYLOAD_SHA256"}:
                if name in values or not isinstance(node.value,ast.Constant) or not isinstance(node.value.value,str):
                    raise ValidationError("artifact payload assignments must be unique string literals")
                values[name]=node.value.value
    if set(values)!={"_ENCODED","PAYLOAD_SHA256"}:
        raise ValidationError("missing artifact payload metadata")
    # Other source statements are never executed, even in a tampered Python file.
    return decode_payload(values["_ENCODED"],values["PAYLOAD_SHA256"],limits)


def write_python_artifact(path: str | Path, result: object, limits: ArtifactLimits | None=None) -> None:
    path=Path(path)
    if path.suffix!=".py" or path.is_symlink():
        raise ValidationError("artifact target must be a regular .py data file")
    if path.exists():
        try:
            with path.open("r",encoding="utf-8") as existing:
                first=existing.readline(256)
        except (OSError,UnicodeError) as exc:
            raise ValidationError("cannot inspect existing artifact target") from exc
        if not first.startswith((MAGIC,LEGACY_MAGIC)):
            raise ValidationError("refusing to replace an existing source/project file")
    text=encode_python_artifact(result,limits)
    temporary: Path | None=None
    try:
        path.parent.mkdir(parents=True,exist_ok=True)
        parent=path.parent.resolve()
        with tempfile.NamedTemporaryFile(mode="w",encoding="utf-8",newline="\n",dir=parent,
                                          prefix=f".{path.name}.",suffix=".py",delete=False) as stream:
            temporary=Path(stream.name)
            if temporary.resolve().parent!=parent:
                raise ValidationError("temporary artifact escaped destination directory")
            stream.write(text)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary,path.resolve())
    except OSError as exc:
        raise ValidationError("artifact publication failed") from exc
    finally:
        if temporary is not None and temporary.exists():
            temporary.unlink()

