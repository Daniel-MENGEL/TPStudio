# Résolution des rattachements dans un notebook chargé

A69c résout un `NotebookBindingPlan` dans un véritable notebook `nbformat`
déjà chargé en mémoire. Il n'accepte aucun chemin et n'ouvre aucun fichier.
Son rôle est une observation technique en lecture seule : trouver les cellules
demandées et extraire exactement le fragment déclaré.

## Cinq statuts techniques

Chaque `CellProductionBinding` produit exactement une
`NotebookBindingResolution` :

- `RESOLVED` : une cellule unique et un fragment extractible ;
- `CELL_NOT_FOUND` : aucune cellule ne correspond ;
- `CELL_AMBIGUOUS` : plusieurs cellules correspondent ;
- `TEXT_MARKER_NOT_FOUND` : la cellule est unique, mais le marqueur du scope
  est absent ;
- `TEXT_MARKER_AMBIGUOUS` : la cellule est unique, mais ce marqueur apparaît
  plusieurs fois.

L'absence et l'ambiguïté sont distinctes. Le résolveur ne choisit jamais la
première cellule ou la première occurrence arbitrairement. Ces situations
métier sont des résultats structurés, pas des exceptions. Elles ne constituent
pas encore des diagnostics destinés à l'étudiant ou au professeur.

`candidate_indices` conserve les indices de toutes les cellules candidates
dans l'ordre du notebook. L'index est ici une observation auditable ; il reste
interdit comme sélecteur déclaratif A69b, car il est trop fragile.

## Sélecteurs littéraux

Les trois recherches sont exactes et sensibles à la casse :

- `CELL_ID` compare `cell.get("id")` à la valeur déclarée ;
- `TAG` cherche cette valeur dans `cell.metadata.tags` ;
- `SOURCE_MARKER` cherche littéralement la chaîne dans `cell.source`.

Aucune normalisation, expression régulière ou modification de casse n'est
appliquée. Plusieurs occurrences d'un `SOURCE_MARKER` dans une même cellule
identifient toujours une seule cellule ; le sélecteur désigne la cellule, pas
une occurrence.

Les cellules standard `markdown`, `code` et `raw` sont traitées de la même
façon. Les outputs et `execution_count` ne sont jamais consultés.

## Scopes textuels

Avec `FULL_SOURCE`, `text` reproduit exactement `cell.source`, avec les bornes
`0` et `len(cell.source)`. Une source vide est donc une résolution réussie.

Avec `AFTER_MARKER`, le marqueur est recherché littéralement : zéro occurrence
ou plusieurs occurrences produisent les statuts dédiés. Pour une occurrence
unique, `text_start` se situe immédiatement après le marqueur et `text_end` à
la fin de la source. Aucun `strip`, `lstrip` ou `rstrip` n'est appliqué.
Espaces, accents, caractères Unicode et retours à la ligne sont conservés. Un
fragment vide après le marqueur reste `RESOLVED`.
Les positions de départ littérales sont comptées séparément : des occurrences
chevauchantes produisent donc `TEXT_MARKER_AMBIGUOUS`.

## Exemple nbformat en mémoire

```python
import nbformat

from tpstudio.notebooks import resolve_notebook_bindings

notebook = nbformat.v4.new_notebook(
    cells=[
        nbformat.v4.new_markdown_cell(
            "Introduction",
            id="intro-cell",
        ),
        nbformat.v4.new_markdown_cell(
            "Résultat statique\n\ng = (9,8 ± 0,2) m·s⁻²",
            id="cell-gravity-static",
        ),
        nbformat.v4.new_markdown_cell(
            "Déterminer g par la méthode dynamique.\n\n"
            "Réponse :\ng = (9,7 ± 0,4) m·s⁻²",
            metadata={"tags": ["answer-gravity-dynamic"]},
        ),
        nbformat.v4.new_markdown_cell(
            "TPSTUDIO: gravity_comparison\n"
            "Réponse :\nLes deux résultats sont compatibles."
        ),
    ]
)

result = resolve_notebook_bindings(notebook, binding_plan)
dynamic = result.get("binding-gravity-dynamic")

assert dynamic is not None
assert dynamic.production_id == "gravity_dynamic"
assert dynamic.status.value == "resolved"
assert dynamic.cell is not None and dynamic.cell.index == 2
assert dynamic.text == "\ng = (9,7 ± 0,4) m·s⁻²"
```

`NotebookCellReference` conserve l'index, le type, l'id et les tags observés,
mais jamais la source complète, les outputs, l'objet cellule mutable ou un
chemin. Le fragment utile reste séparé dans la résolution avec ses bornes
Python `[text_start:text_end]`.

## Ordre, identité et limites

`NotebookBindingResolutionSet` contient exactement une résolution par binding,
dans `NotebookBindingPlan.in_evaluation_order`, et conserve l'identité des
objets déclaratifs A69b. Plusieurs bindings peuvent résoudre la même cellule et
une production peut produire plusieurs résolutions, sans aucune agrégation de
leurs textes.

A69c ne modifie ni le notebook ni ses cellules, n'exécute aucun code et
n'inspecte aucun output. Il n'appelle pas lui-même A69a.

A69d [consomme désormais ces résolutions](notebook_quantity_assessment.md)
sans modifier A69c : le jeu complet reste disponible, tandis que chaque
résolution `QUANTITY` réussie est transmise à A69a.
