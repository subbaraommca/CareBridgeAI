def normalize_concept_display(display: str) -> str:
    # TODO: Replace with terminology service backed normalization and synonym handling.
    return " ".join(display.strip().split()).title()

