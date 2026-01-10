#!/usr/bin/env python3
"""
Wrapper script to run the extraction worker.

Usage:
    python run_worker.py                    # Single worker
    python run_worker.py --workers 4        # Multiple workers
"""

import sys
import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Add server directory to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from ryumem_server.worker import main

if __name__ == "__main__":
    main()
