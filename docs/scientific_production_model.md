# Modèle général des productions scientifiques

A68a permet au professeur de décrire la nature des productions scientifiques
attendues sans supposer que leur résultat est connu à l'avance. Un
`ScientificProductionPlan` ordonne des `ScientificProductionSpec` et leurs
dépendances. Il exprime une intention pédagogique, jamais un résultat
d'évaluation.

## Cinq niveaux distincts

1. **Production attendue** : ce que l'étudiant doit produire — relation,
   quantité, courbe, interprétation, comparaison ou justification. A68a ajoute
   uniquement ce niveau générique.
2. **Spécification détaillée** : propriétés ou critères fournis par le
   professeur. `ExpectedRelation` et `ExpectedConclusion` en sont les premiers
   exemples spécialisés. A68b ajoute `ExpectedQuantity`, première
   spécification détaillée explicitement rattachée au plan général par
   `QuantityExpectationSet`.
3. **Preuve ou observation** : information réellement extraite de la copie,
   du code, des variables ou des figures. A68c implémente ce niveau pour une
   grammaire limitée de quantités écrites dans du texte.
4. **Évaluation** : comparaison future des preuves avec les critères.
5. **Diagnostic et feedback** : interprétation pédagogique puis formulation
   destinée à l'étudiant.

## Bases d'évaluation

Une production peut déclarer plusieurs `EvaluationBasis` :

- `DECLARED_CONTENT` : le professeur fournit explicitement un contenu de
  référence. Cela ne signifie pas que toute réponse sera comparée comme une
  chaîne exacte ; le futur évaluateur déterminera la méthode adaptée.
- `FIXED_REFERENCE` : comparaison future à une référence connue, par exemple
  une valeur théorique ou tabulée.
- `SUBMISSION_DERIVED` : le résultat de référence dépend des données et des
  traitements présents dans la copie ; le professeur ne connaît donc pas
  nécessairement sa valeur numérique.
- `CROSS_PRODUCTION` : comparaison future de plusieurs productions de la même
  copie, par exemple deux méthodes expérimentales.
- `STRUCTURAL` : vérifications futures telles que la présence d'une unité,
  d'une incertitude, d'axes ou de légendes.
- `SEMANTIC` : évaluation future du sens d'une interprétation ou d'une
  justification.

Déclarer une base ne signifie pas que l'évaluateur correspondant existe déjà.
A68a ne fournit aucun évaluateur.

## Exemple : TP de pendule

Le plan suivant décrit un TP où les valeurs de `g` dépendent des mesures de la
copie. Le professeur n'indique ni `gravity_dynamic` ni `gravity_static` sous
forme de valeurs numériques fixes.

```python
from tpstudio.expectations import (
    EvaluationBasis,
    ScientificProductionKind,
    ScientificProductionPlan,
    ScientificProductionSpec,
)

plan = ScientificProductionPlan(
    id="pendulum_results",
    title="Résultats du TP pendule",
    productions=(
        ScientificProductionSpec(
            "period_plot",
            "Courbe de T² en fonction de L",
            ScientificProductionKind.PLOT,
            (EvaluationBasis.STRUCTURAL, EvaluationBasis.SUBMISSION_DERIVED),
        ),
        ScientificProductionSpec(
            "gravity_dynamic",
            "Valeur de g obtenue par ajustement",
            ScientificProductionKind.QUANTITY,
            (EvaluationBasis.STRUCTURAL, EvaluationBasis.SUBMISSION_DERIVED),
            depends_on=("period_plot",),
        ),
        ScientificProductionSpec(
            "gravity_static",
            "Valeur de g obtenue par la méthode statique",
            ScientificProductionKind.QUANTITY,
            (EvaluationBasis.STRUCTURAL, EvaluationBasis.SUBMISSION_DERIVED),
        ),
        ScientificProductionSpec(
            "gravity_comparison",
            "Comparaison des deux valeurs de g",
            ScientificProductionKind.COMPARISON,
            (EvaluationBasis.CROSS_PRODUCTION, EvaluationBasis.SEMANTIC),
            depends_on=("gravity_dynamic", "gravity_static"),
        ),
        ScientificProductionSpec(
            "uncertainty_justification",
            "Justification de l'incertitude associée à g",
            ScientificProductionKind.JUSTIFICATION,
            (EvaluationBasis.SEMANTIC,),
            depends_on=("gravity_dynamic",),
        ),
        ScientificProductionSpec(
            "final_interpretation",
            "Interprétation finale",
            ScientificProductionKind.INTERPRETATION,
            (EvaluationBasis.CROSS_PRODUCTION, EvaluationBasis.SEMANTIC),
            depends_on=("gravity_comparison",),
        ),
    ),
)
```

Le plan valide les dépendances, rejette les cycles et fournit un ordre
topologique stable. Il n'extrait cependant aucune valeur ou incertitude,
n'inspecte aucune courbe et n'exécute aucune comparaison scientifique.

Les critères structurels des deux productions `QUANTITY` peuvent désormais
être décrits séparément avec le
[modèle d'attendus de grandeurs numériques](quantity_expectations.md), sans
ajouter de valeur numérique au plan.
A68d fournit le premier évaluateur du niveau 4 :
[l'évaluation structurelle des grandeurs](quantity_structural_evaluation.md)
consomme les observations A68c sans valider leur contenu scientifique.
