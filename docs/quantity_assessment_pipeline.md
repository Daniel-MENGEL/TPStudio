# Orchestration complète d'une grandeur textuelle

A69a introduit `tpstudio.assessment`, la première chaîne verticale complète
pour une production `QUANTITY`. Le package orchestre les composants A68b à
A68g ; il ne contient aucune nouvelle règle d'extraction, d'évaluation, de
diagnostic ou de feedback.

## Une chaîne auditable

`QuantityAssessmentPipeline.assess()` traite une seule production par appel :

1. il récupère l'`ExpectedQuantity` correspondant au `production_id` ;
2. il appelle l'extracteur A68c et obtient une `QuantityDetection` ;
3. il appelle l'évaluateur structurel A68d ;
4. si une politique existe pour cette production, il appelle A68e ;
5. il construit le `QuantityDiagnosticSet` avec A68f ;
6. si un catalogue est fourni, il rend le `QuantityFeedbackSet` avec A68g.

Le `QuantityAssessmentResult` immuable conserve le jeu d'attendus, l'attendu
sélectionné et chacun de ces objets intermédiaires. Les liens d'identité
garantissent qu'une même détection et une même évaluation circulent dans toute
la chaîne sans reconstruction d'objets équivalents.

Le texte étudiant intégral n'est pas stocké dans le résultat. Seuls les
fragments utiles, déjà portés par les `QuantityObservation`, sont conservés.

## Exemple complet

```python
from tpstudio.assessment import assess_quantity_text
from tpstudio.feedback import french_quantity_feedback_catalog

result = assess_quantity_text(
    "g = (9,7 ± 0,4) m·s⁻²",
    "gravity_dynamic",
    quantity_expectation_set,
    uncertainty_expectation_set,
    french_quantity_feedback_catalog(),
)

assert result.has_observation
assert result.is_structurally_satisfied
assert result.diagnostics == ()
assert result.student_feedback == ()
```

Un résultat satisfait ne déclenche aucun feedback positif automatique. Le
catalogue français est ici demandé explicitement ; il n'est jamais choisi par
le pipeline.

Avec `g = 9,7 ± 0,4`, la chaîne conserve la provenance suivante :

```text
QuantityDetection
→ QuantityStructuralEvaluation (unité absente)
→ QuantityDiagnosticSet (UNIT_MISSING)
→ QuantityFeedbackSet (si le catalogue contient ce code)
```

Le catalogue français produit alors « Précisez l’unité de la valeur
indiquée. » Un catalogue incomplet omet simplement les codes non configurés.
Sans catalogue, `feedback_set` vaut `None` et les diagnostics restent
disponibles.

## Politique d'incertitude facultative

Le `UncertaintyQualityExpectationSet` est facultatif et doit référencer
exactement le `QuantityExpectationSet` évalué. Lorsqu'il est absent, ou
lorsqu'il ne contient aucune spécification pour la production demandée,
`uncertainty_evaluation` vaut `None`. Les diagnostics structurels sont tout de
même construits et aucun diagnostic de qualité n'est inventé.

L'absence d'incertitude observée rend les contrôles de qualité non applicables.
Elle ne produit donc pas de double sanction en plus de `UNCERTAINTY_MISSING`.

## Portée scientifique

`is_structurally_satisfied` délègue seulement au résultat A68d. Elle ne
signifie pas que la valeur expérimentale est correcte. A69a ne vérifie ni le
calcul, ni une référence théorique, ni une justification, et ne produit ni
score ni barème.

Deux productions partageant le symbole `g`, par exemple `gravity_dynamic` et
`gravity_static`, doivent être évaluées séparément avec leur propre
`production_id`. Le pipeline n'attache pas de cellules de notebook aux
productions et n'exécute aucun notebook.

A69b prépare désormais, avec un
[plan déclaratif de rattachement](notebook_production_bindings.md), la future
fourniture du texte et du `production_id` à A69a. Il ne résout pas encore cette
liaison et n'appelle pas le pipeline d'évaluation.

A69c produit un texte résolu et son `production_id` depuis un notebook déjà
chargé, sans appeler lui-même A69a.

A69d fournit désormais automatiquement à A69a le `text` exact et le
`production_id` de chaque [binding QUANTITY résolu](notebook_quantity_assessment.md).
Les résolutions échouées et les productions non quantitatives ne déclenchent
aucun appel à ce pipeline.
