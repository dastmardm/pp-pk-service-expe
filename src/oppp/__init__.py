"""oppp — decomposed natural-language to machine-query translator.

Pipeline: decompose (Stage 1) -> per-field translate (Stage 2) -> aggregate
(Stage 3). See docs/ for the full design. Every step is pluggable and isolatable
for evaluation.
"""

__version__ = "0.1.0"
