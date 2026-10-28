#!/usr/bin/env python3
"""Recreate selected Census CSV without modifying raw input or overwriting output."""
import argparse,csv
from pathlib import Path
p=argparse.ArgumentParser();p.add_argument("raw");p.add_argument("output");a=p.parse_args()
rows=list(csv.DictReader(Path(a.raw).open(encoding="utf8",newline="")))
rows=sorted((x for x in rows if x["SUMLEV"]=="040"),key=lambda x:x["STATE"])
with Path(a.output).open("x",encoding="utf8",newline="") as f:
 w=csv.DictWriter(f,fieldnames=["state","name","region","population_start","population_end"]);w.writeheader()
 for x in rows:w.writerow(dict(state=x["STATE"],name=x["NAME"],region=x["REGION"],population_start=int(x["POPESTIMATE2024"]),population_end=int(x["POPESTIMATE2025"])))
