#!/usr/bin/env python3
"""
Run script for LLM User Service
"""
import uvicorn

if __name__ == "__main__":
    uvicorn.run(
    "src.main:app",
    host="localhost",   # change this
    port=8001,
    reload=True
)


