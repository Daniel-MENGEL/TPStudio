# Attendus de comparaisons quantitatives

A70a permet au professeur de déclarer qu'une production scientifique
`COMPARISON` compare deux productions `QUANTITY`. Cette déclaration décrit
l'intention, les seuils objectifs et le contexte pédagogique ; elle ne calcule
encore rien. A70b met désormais en œuvre le calcul objectif dans un contrat
d'évaluation séparé, sans modifier la déclaration.

## Écart normalisé futur

La seule méthode déclarable dans A70a est `NORMALIZED_ERROR`. Un futur
évaluateur calculera :

```text
En = |x1 - x2| / sqrt(u1² + u2²)
```

Les seuils par défaut sont exactement `Decimal("2")` et `Decimal("4")` :

- `En < 2` : résultats cohérents ;
- `2 <= En < 4` : incohérence modérée ;
- `En >= 4` : incohérence forte.

`NormalizedErrorThresholds` permet de configurer ces deux limites avec des
`Decimal` strictement positifs, finis et ordonnés. Il ne contient aucune
méthode de calcul ou de classement.

## Résultat objectif et contexte pédagogique

`ComparisonPedagogicalContext` apporte une information distincte du futur
résultat objectif :

- `OPEN` : aucune attente particulière ;
- `COHERENCE_EXPECTED` : une cohérence est normalement attendue ;
- `INCOHERENCE_POSSIBLE` : une incohérence est expérimentalement plausible ;
- `METHOD_LIMITATION_EXPECTED` : une incohérence peut révéler la limitation
  connue ou la faible fiabilité d'une méthode.

Même avec `METHOD_LIMITATION_EXPECTED`, une valeur `En >= 4` restera classée
objectivement comme une incohérence forte. Le contexte ne la transforme pas en
cohérence, ne supprime aucun futur signalement et ne produit ni pénalité ni
note. La conclusion rédigée par l'étudiant sera évaluée séparément.

## Exemple du pendule

```python
from decimal import Decimal

from tpstudio.expectations import (
    ComparisonPedagogicalContext,
    ExpectedQuantityComparison,
    NormalizedErrorThresholds,
    QuantityComparisonExpectationSet,
    QuantityComparisonMethod,
)

comparison = ExpectedQuantityComparison(
    production_id="gravity_comparison",
    left_quantity_id="gravity_dynamic",
    right_quantity_id="gravity_static",
    method=QuantityComparisonMethod.NORMALIZED_ERROR,
    thresholds=NormalizedErrorThresholds(
        coherence_limit=Decimal("2"),
        strong_incoherence_limit=Decimal("4"),
    ),
    pedagogical_context=(
        ComparisonPedagogicalContext.METHOD_LIMITATION_EXPECTED
    ),
    context_note=(
        "La méthode statique peut être peu fiable avec ce montage."
    ),
)

comparison_expectations = QuantityComparisonExpectationSet(
    production_plan=production_plan,
    quantity_expectation_set=quantity_expectation_set,
    comparisons=(comparison,),
)
```

Dans le `ScientificProductionPlan`, `gravity_comparison` doit être une
production `COMPARISON` dépendant au minimum de `gravity_dynamic` et
`gravity_static`, toutes deux `QUANTITY` et présentes dans le
`QuantityExpectationSet`. Des dépendances supplémentaires restent permises.
La déclaration ne présume pas de la valeur numérique qui sera obtenue.

## Cardinalités et limites

Deux productions `COMPARISON` distinctes peuvent comparer la même paire, y
compris dans l'ordre inverse ou avec des contextes différents. Une quantité
peut participer à plusieurs comparaisons.

A70a référence seulement les `production_id`. Il ne choisit pas entre
plusieurs bindings A69d d'une même quantité, ne fusionne aucun résultat et ne
lit ni observation ni assessment. Cette politique appartiendra au futur A70b.

A70a ne compare ou ne convertit aucune unité, n'impose ni symbole identique ni
dimension physique, et ne calcule aucune compatibilité. Il ne produit aucun
diagnostic, feedback, poids, score ou note, et n'ouvre aucun notebook.
