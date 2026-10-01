"""CLI demo: python run_demo.py  -> prints the briefing for the synthetic patient."""
import os
from carebridge.pipeline import run_pipeline, load_folder

res = run_pipeline(load_folder(os.path.join(os.path.dirname(__file__), "sample_data")), today="2026-10-01")
print(res.briefing())
print("\nSafety check ->", res.ask("What disease do I have?"))
