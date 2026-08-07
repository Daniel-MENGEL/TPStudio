# Modèle général des productions scientifiques

```text
A71b Configuration professeur
        ↓
A71c CopyAnalysisResult — analyser et évaluer
        ↓
A71d TeacherCopyReport — présenter
        ↓
A71e annotation contrôlée — future
        ↓
A71f export notebook / HTML — futur
```

La sévérité du rapport est une priorité de présentation, jamais une notation.

L'[audit de la verticale Snell-Descartes](snells_laws_vertical_audit.md)
applique ce modèle à un TP réel et distingue les contrats directement
configurables des adaptateurs encore nécessaires pour le code, les graphes et
l'orchestration. A71a ne modifie aucun contrat A66–A70h.

A71b fournit maintenant la
[configuration professeur Snell-Descartes](snells_laws_teacher_configuration.md)
qui instancie ce plan, ses bindings et ses attentes. Le contrat de graphe reste
local au paquet `projects` afin de ne pas modifier les contrats métier existants.

A68a permet au professeur de décrire la nature des productions scientifiques
attendues sans supposer que leur résultat est connu à l'avance. Un
`ScientificProductionPlan` ordonne des `ScientificProductionSpec` et leurs
dépendances. Il exprime une intention pédagogique, jamais un résultat
d'évaluation.

La chaîne objective de comparaison est désormais :

```text
NotebookQuantityAssessmentSet
→ QuantityComparisonExpectationSet
→ QuantityComparisonEvaluationSet
→ QuantityComparisonDiagnosticSet
→ QuantityComparisonFeedbackSet
→ observations parallèles du calcul étudiant et de sa conclusion
```

Les deux branches étudiantes restent distinctes et indépendantes :

```text
QuantityComparisonEvaluation
        |
        +→ StudentNormalizedErrorEvaluation
        |
        +→ ComparisonInterpretationEvaluation
```

La première compare la valeur finale de En à la référence interne ; la seconde
compare une conclusion littérale déclarée au statut objectif. Aucun des deux
résultats ne modifie l'autre.

La branche de présentation de l'interprétation est :

```text
ComparisonInterpretationEvaluationSet
→ ComparisonInterpretationDiagnosticSet
→ ComparisonInterpretationFeedbackSet
```

Elle ne recalcule aucune donnée. L'évaluation détaillée de la justification
reste future.

La dépendance des trois observations étudiantes est :

```text
QuantityComparisonEvaluation
        |
        +→ StudentNormalizedErrorEvaluation
        |
        +→ ComparisonInterpretationEvaluation
                 |
                 +→ ComparisonJustificationEvaluation
```

La justification A70g est évaluée structurellement à partir d'éléments
déclarés. Sa pertinence scientifique détaillée reste future.

Sa branche de présentation est :

```text
ComparisonJustificationEvaluationSet
→ ComparisonJustificationDiagnosticSet
→ ComparisonJustificationFeedbackSet
```

Elle conserve les données manquantes sous forme structurée ; la pertinence
scientifique détaillée reste future.

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
A68e complète ce niveau avec une
[évaluation intrinsèque de l'incertitude](quantity_uncertainty_evaluation.md),
fondée sur une politique explicite du professeur et sans vérifier son calcul.
A68f fournit la première traduction du niveau 4 vers le niveau 5 avec des
[diagnostics structurés de grandeurs](quantity_diagnostics.md), encore sans
texte étudiant, sévérité, feedback ou score.
Avec A68g, le niveau 5 distingue désormais explicitement le diagnostic
structuré, le [feedback formulé par catalogue](quantity_feedback.md) et la
future notation, qui reste hors périmètre.
A69a fournit la [première orchestration verticale complète](quantity_assessment_pipeline.md)
des cinq niveaux pour une grandeur textuelle. Elle conserve chaque objet
intermédiaire, sans ajouter de logique métier ni valider la valeur scientifique.

A69b place un
[NotebookBindingPlan déclaratif](notebook_production_bindings.md) entre le plan
pédagogique et la future observation du notebook. Il décrit les cellules
destinées aux productions sans charger de notebook, résoudre de cellule ou
extraire de preuve.

A69c complète cette transition en lecture seule :

```text
ScientificProductionPlan
→ NotebookBindingPlan
→ NotebookBindingResolutionSet
→ NotebookQuantityAssessmentSet
→ diagnostics et feedbacks quantitatifs
```

Le jeu de résolutions conserve les bindings par identité et dans leur ordre
d'évaluation, sans transformer encore les fragments observés en évaluations.
A69d réalise désormais cette dernière transition pour les productions
`QUANTITY` résolues, tout en laissant les autres catégories dans le jeu de
résolutions complet pour de futurs pipelines spécialisés.

A70a déclare maintenant les [comparaisons quantitatives attendues](quantity_comparison_expectations.md)
à partir des dépendances du plan :

```text
QUANTITY gravity_dynamic
        \
         → COMPARISON gravity_comparison
        /
QUANTITY gravity_static
```

Les seuils décrivent le futur constat objectif. Le contexte pédagogique reste
une information distincte et ne change ni ce constat, ni sa classification.

A71c agrège désormais une copie sans modifier ce graphe d'identités :

```text
NotebookBindingResolutionSet
→ NotebookQuantityAssessmentSet
→ QuantityComparisonEvaluationSet
   ├→ StudentNormalizedErrorEvaluationSet
   ├→ ComparisonInterpretationEvaluationSet
   └→ ComparisonJustificationEvaluationSet
→ CopyAnalysisResult
```

La conclusion finale possède sa propre observation et ne reçoit pas le statut
d'une comparaison. Les diagnostics et feedbacks restent des vues dérivées sans
score ni note.
