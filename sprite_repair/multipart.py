"""Minimal multipart/form-data parser (no cgi dependency)."""

from __future__ import annotations

from typing import Any


def parse_multipart(content_type: str, body: bytes) -> dict[str, Any]:
    if "multipart/form-data" not in content_type:
        raise ValueError("expected multipart/form-data")
    boundary = None
    for part in content_type.split(";"):
        part = part.strip()
        if part.startswith("boundary="):
            boundary = part.split("=", 1)[1].strip().strip('"')
            break
    if not boundary:
        raise ValueError("missing boundary")
    delim = b"--" + boundary.encode("ascii", errors="ignore")
    out: dict[str, Any] = {}
    for chunk in body.split(delim):
        if not chunk or chunk in (b"--", b"--\r\n", b"--\n"):
            continue
        if chunk.startswith(b"--"):
            continue
        if chunk.startswith(b"\r\n"):
            chunk = chunk[2:]
        elif chunk.startswith(b"\n"):
            chunk = chunk[1:]
        if chunk.endswith(b"\r\n"):
            chunk = chunk[:-2]
        elif chunk.endswith(b"\n"):
            chunk = chunk[:-1]
        if b"\r\n\r\n" in chunk:
            header_blob, data = chunk.split(b"\r\n\r\n", 1)
        elif b"\n\n" in chunk:
            header_blob, data = chunk.split(b"\n\n", 1)
        else:
            continue
        if data.endswith(b"\r\n"):
            data = data[:-2]
        elif data.endswith(b"\n"):
            data = data[:-1]
        headers = {}
        for line in header_blob.decode("utf-8", errors="replace").splitlines():
            if ":" in line:
                k, v = line.split(":", 1)
                headers[k.strip().lower()] = v.strip()
        disp = headers.get("content-disposition", "")
        name = None
        filename = None
        for piece in disp.split(";"):
            piece = piece.strip()
            if piece.startswith("name="):
                name = piece.split("=", 1)[1].strip().strip('"')
            elif piece.startswith("filename="):
                filename = piece.split("=", 1)[1].strip().strip('"')
        if not name:
            continue
        if filename is not None:
            out[name] = {"filename": filename, "data": data}
        else:
            out[name] = data.decode("utf-8", errors="replace")
    return out
