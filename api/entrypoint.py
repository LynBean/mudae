#!/usr/bin/env python3
import uvicorn

from src import app

__all__ = ["app"]

if __name__ == "__main__":
    uvicorn.run(app, host="localhost", port=5000)
