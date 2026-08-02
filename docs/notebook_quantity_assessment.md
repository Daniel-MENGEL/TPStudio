# Évaluation des grandeurs résolues dans un notebook

A69d est la première orchestration d'assessment directement applicable à un
notebook `nbformat` déjà chargé en mémoire. Elle relie les contrats déclaratifs
A69b, la résolution technique A69c et le pipeline métier A69a :

```text
NotebookBindingPlan
→ NotebookBindingResolutionSet
→ bindings QUANTITY résolus
→ QuantityAssessmentResult
→ diagnostics et feedbacks éventuels
```

Cette coordination appartient à `tpstudio.assessment` parce qu'elle combine
l'observation technique du notebook avec l'évaluation métier des quantités.

Ces résultats peuvent désormais alimenter A70b. A69d ne calcule toutefois pas
lui-même En et ne compare pas les productions.

## Résolutions et items quantitatifs

`NotebookQuantityAssessmentSet.resolution_set` conserve intégralement le
résultat A69c, y compris les bindings `PLOT`, `COMPARISON`, `INTERPRETATION`,
`JUSTIFICATION` ou `RELATION`. Seuls les bindings dont la production est
exactement `QUANTITY` deviennent des `NotebookQuantityAssessmentItem`.

Deux statuts décrivent seulement la possibilité de lancer A69a :

- `ASSESSED` : la résolution contient un texte exact, transmis à A69a avec son
  `production_id` ;
- `RESOLUTION_FAILED` : la cellule ou le marqueur est absent ou ambigu, donc
  A69a n'est pas appelé.

Un échec de résolution ne produit aucun `QuantityDiagnostic` ni feedback. Il
ne devient notamment jamais `QUANTITY_MISSING`. À l'inverse, une cellule bien
résolue contenant « Je n’ai pas obtenu de résultat. » est évaluée : A69a peut
alors produire `QUANTITY_MISSING`, car le texte existe mais ne contient pas la
grandeur attendue.

## Exemple complet en mémoire

```python
import nbformat

from tpstudio.assessment import assess_notebook_quantities
from tpstudio.feedback import french_quantity_feedback_catalog

notebook = nbformat.v4.new_notebook(
    cells=[
        nbformat.v4.new_markdown_cell(
            "Déterminer g par la méthode dynamique.\n"
            "Réponse :\n"
            "g = (9,7 ± 0,4) m·s⁻²",
            metadata={"tags": ["answer-gravity-dynamic"]},
        ),
        nbformat.v4.new_markdown_cell(
            "g = 9,8 ± 0,2",
            id="cell-gravity-static",
        ),
        nbformat.v4.new_markdown_cell(
            "TPSTUDIO: gravity_comparison\n"
            "Réponse : les résultats sont compatibles."
        ),
    ]
)

result = assess_notebook_quantities(
    notebook,
    binding_plan,
    quantity_expectation_set,
    uncertainty_expectation_set,
    french_quantity_feedback_catalog(),
)
```

Le résultat observable est alors :

```text
gravity_dynamic
→ RESOLVED
→ ASSESSED
→ aucun diagnostic

gravity_static
→ RESOLVED
→ ASSESSED
→ UNIT_MISSING
→ feedback étudiant éventuel

gravity_comparison
→ RESOLVED
→ présent dans resolution_set
→ non évalué par A69d

cellule absente
→ CELL_NOT_FOUND
→ RESOLUTION_FAILED
→ aucun QuantityAssessmentResult
```

Le catalogue français n'est utilisé ici que parce qu'il est fourni
explicitement. Sans catalogue, les diagnostics restent disponibles et les
feedbacks sont vides. De même, la politique de qualité d'incertitude est
facultative et peut ne couvrir qu'une partie des productions.

## Ordre, identité et pluralité

A69c est appelé exactement une fois. Ses résolutions sont parcourues dans
l'ordre du `NotebookBindingPlan`. Chaque item conserve par identité sa
résolution et la `ScientificProductionSpec` du plan. Les objets A69a sont
également conservés tels quels.

Plusieurs bindings d'une même quantité produisent plusieurs assessments
indépendants. Une même cellule liée à deux quantités déclenche deux appels A69a
avec leurs `production_id` respectifs. Les diagnostics et feedbacks dérivés
sont seulement concaténés dans l'ordre des items : aucun texte n'est fusionné,
aucun résultat préféré et aucun objet dédupliqué.

## Limites

A69d n'ouvre ni ne sauvegarde aucun fichier. Le notebook est déjà chargé ; son
code n'est jamais exécuté, ses outputs ne sont pas inspectés et ses cellules ne
sont pas modifiées. Les productions non quantitatives attendent leurs futurs
pipelines spécialisés. Aucune agrégation multi-cellules, aucun diagnostic de
résolution, aucune note et aucun barème ne sont produits.

A70a permet désormais de [déclarer quelles productions quantitatives devront
être comparées](quantity_comparison_expectations.md), avec leurs seuils et leur
contexte pédagogique. A69d conserve les assessments nécessaires, mais ne
calcule toujours aucune comparaison et ne choisit pas entre plusieurs bindings.
