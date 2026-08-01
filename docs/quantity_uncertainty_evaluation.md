# Évaluation intrinsèque de l'incertitude

A68e reste au niveau 4, **évaluation**, de l'architecture des productions
scientifiques. Le professeur décrit explicitement sa politique avec
`UncertaintyQualitySpec`, puis `QuantityUncertaintyEvaluator` l'applique à
l'observation déjà sélectionnée par A68d.

```python
from tpstudio.evaluation import evaluate_quantity_uncertainty
from tpstudio.expectations import (
    UncertaintyQualityExpectationSet,
    UncertaintyQualitySpec,
)

policies = UncertaintyQualityExpectationSet(
    quantity_expectation_set,
    (UncertaintyQualitySpec("gravity_dynamic"),),
)
result = evaluate_quantity_uncertainty(structural_evaluation, policies)
```

La politique par défaut demande une incertitude strictement positive, autorise
un ou deux chiffres significatifs et impose le même rang décimal à la valeur
centrale et à l'incertitude. Chaque contrôle peut être configuré ; le contrôle
des chiffres significatifs est désactivé avec `None`.

## Trois contrôles intrinsèques

`STRICTLY_POSITIVE` vérifie uniquement `uncertainty > 0`. Une incertitude
nulle ou négative échoue à ce critère, sans empêcher l'évaluation des deux
autres.

`SIGNIFICANT_DIGITS` utilise le `Decimal` construit par A68c, sans appeler
`normalize()`. Le signe et les zéros avant le premier chiffre non nul ne
comptent pas, tandis que les zéros finaux explicitement écrits sont conservés :

- `Decimal("0.4")` contient un chiffre significatif ;
- `Decimal("0.40")` et `Decimal("0.0040")` en contiennent deux ;
- `Decimal("4.00E-3")` en contient trois ;
- zéro, quelle que soit sa présentation, compte conventionnellement pour un
  chiffre significatif.

`DECIMAL_PLACE_ALIGNMENT` compare directement
`value.as_tuple().exponent` et `uncertainty.as_tuple().exponent`. Il vérifie
donc le rang de présentation observé, sans comparer les valeurs numériques ni
normaliser leur écriture.

## Exemples

Avec la politique par défaut :

- `9,7 ± 0,4` satisfait les trois contrôles ;
- `9,70 ± 0,40` contient deux chiffres significatifs et reste aligné ;
- `9,70 ± 0,4` échoue seulement à l'alignement des rangs ;
- `9,7 ± 0,456` échoue au nombre de chiffres significatifs ;
- `9,7 ± -0,4` échoue à la positivité, mais les autres contrôles restent
  applicables indépendamment.

## Articulation avec A68d

A68e reçoit une `QuantityStructuralEvaluation`, jamais une
`QuantityDetection`. Il réutilise exclusivement `selected_observation` et ne
refait donc ni sélection ni fusion entre occurrences.

Si la quantité ou son incertitude est absente, les trois critères A68e sont
`NOT_APPLICABLE`. L'absence a déjà été traitée par A68d : A68e ne crée pas un
second échec. Dans ce cas, `is_applicable` est faux et `satisfied` est vrai de
façon vacuelle ; cela ne signifie pas que l'incertitude est scientifiquement
satisfaisante.

## Limites

Une incertitude bien présentée peut être scientifiquement fausse. A68e ne
vérifie ni son calcul, ni sa propagation, ni son adéquation aux données du
poste, ni une incertitude relative. Il n'analyse aucune justification, ne
compare aucune référence ou méthode et n'interprète aucune unité.

Les résultats restent internes : aucun `Fact`, diagnostic, feedback ou score
n'est produit.
