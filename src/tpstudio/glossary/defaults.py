"""The small, high-confidence scientific glossary bundled with TPStudio."""

from __future__ import annotations

from .models import Glossary, ScientificTerm


def default_scientific_glossary() -> Glossary:
    """Return the built-in vocabulary used by the existing physics diagnostics."""

    return Glossary(
        id="physics-core",
        title="Glossaire scientifique de physique — noyau",
        terms=(
            ScientificTerm("refraction", "réfraction", "phenomenon", aliases=("refraction",), domains=("optics",), diagnostic_groups=("protocol-optical-quantity",)),
            ScientificTerm("snell-descartes", "Snell-Descartes", "phenomenon", aliases=("Snell", "Descartes", "loi de Snell", "loi de Descartes"), domains=("optics",)),
            ScientificTerm("indice", "indice", "quantity", domains=("optics",)),
            ScientificTerm("angle", "angle", "quantity", aliases=("angles",), domains=("optics",), expected_units=("°", "rad"), diagnostic_groups=("protocol-optical-quantity",)),
            ScientificTerm("incidence", "incidence", "quantity", domains=("optics",), diagnostic_groups=("protocol-optical-quantity",)),
            ScientificTerm("plexiglas", "plexiglas", "instrument", domains=("optics",), diagnostic_groups=("protocol-medium",)),
            ScientificTerm("dioptre", "dioptre", "instrument", domains=("optics",), diagnostic_groups=("protocol-medium",)),
            ScientificTerm("laser", "laser", "instrument", domains=("optics",), diagnostic_groups=("protocol-instrument",)),
            ScientificTerm("rayon", "rayon", "instrument", aliases=("rayon lumineux",), domains=("optics",), diagnostic_groups=("protocol-instrument",)),
            ScientificTerm("disque", "disque", "instrument", aliases=("disque gradué",), domains=("optics",), diagnostic_groups=("protocol-instrument",)),
            ScientificTerm("rapporteur", "rapporteur", "instrument", domains=("optics",), diagnostic_groups=("protocol-instrument",)),
            ScientificTerm("mesure", "mesure", "method", aliases=("mesures",), domains=("experimental",), diagnostic_groups=("protocol-measurement",)),
            ScientificTerm("tableau", "tableau", "method", aliases=("tableaux",), domains=("experimental",), diagnostic_groups=("protocol-measurement",)),
            ScientificTerm("experimental", "expérimental", "method", aliases=("experimentale", "expérimentale", "experimentaux", "expérimentaux", "experimentales", "expérimentales"), domains=("experimental",)),
            ScientificTerm("incertitude", "incertitude", "quantity", aliases=("incertitudes",), domains=("experimental",), diagnostic_groups=("protocol-measurement",)),
            ScientificTerm("ecart-normalise", "écart normalisé", "method", aliases=("ecart normalise",), domains=("experimental",)),
            ScientificTerm("pente", "pente", "quantity", domains=("analysis",)),
            ScientificTerm("droite", "droite", "method", aliases=("aligné", "alignée", "alignes", "alignées"), domains=("analysis",)),
            ScientificTerm("regression-lineaire", "régression linéaire", "method", aliases=("regression lineaire",), domains=("analysis",)),
            ScientificTerm("sinus", "sin", "method", aliases=("sinus",), domains=("analysis",)),
            ScientificTerm("loi", "loi", "phenomenon", aliases=("théorique", "theorique"), domains=("analysis",)),
        ),
    )
