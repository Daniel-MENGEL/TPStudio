# Rattachement déclaratif des cellules aux productions

A69b permet au professeur de décrire explicitement où une production
scientifique devra être recherchée dans un futur notebook. TPStudio ne tente
pas encore de deviner le rôle d'une cellule : une heuristique implicite serait
fragile et pourrait confondre un énoncé, un exemple et une réponse étudiante.

`NotebookBindingPlan` relie un `ScientificProductionPlan` à une suite ordonnée
de `CellProductionBinding`. Il s'agit uniquement d'une intention pédagogique.
Aucun notebook n'est chargé, aucune cellule n'est résolue et aucun texte n'est
extrait dans A69b.

## Sélecteur et portée textuelle

Le `NotebookCellSelector` décrit comment le futur résolveur identifiera une
cellule. Trois sélecteurs littéraux sont disponibles :

- `CELL_ID` : identifiant stable déclaré par la cellule ;
- `TAG` : tag explicite de ses métadonnées ;
- `SOURCE_MARKER` : chaîne distinctive placée dans son contenu.

Le `CellTextScope` indique séparément quelle partie de la source sera destinée
à l'évaluation :

- `FULL_SOURCE` conserve la source complète ;
- `AFTER_MARKER` désigne la partie située après un marqueur littéral.

Ainsi, `CellTextScope.after_marker("Réponse :")` permettra d'éviter de
transmettre l'énoncé placé avant « Réponse : » au pipeline A69a. A69b ne
cherche toutefois pas ce marqueur et ne découpe encore aucun texte.

L'index numérique d'une cellule n'est pas proposé comme sélecteur : il change
dès qu'une cellule est insérée ou supprimée.

## Stratégie recommandée

1. préférer un `CELL_ID` stable lorsqu'il est disponible ;
2. utiliser sinon un `TAG` explicite ;
3. réserver `SOURCE_MARKER` aux notebooks existants sans identifiant ou tag
   adapté.

La future recherche d'un `SOURCE_MARKER` restera littérale. Sa valeur doit
donc être assez distinctive pour éviter plusieurs correspondances. A69b ne
donne aucune priorité implicite aux trois types de sélecteurs.

## Exemple du pendule

```python
from tpstudio.expectations import (
    CellProductionBinding,
    CellTextScope,
    NotebookBindingPlan,
    NotebookCellSelector,
    NotebookCellSelectorKind,
)

dynamic_cell = NotebookCellSelector(
    NotebookCellSelectorKind.TAG,
    "answer-gravity-dynamic",
)

bindings = NotebookBindingPlan(
    id="pendulum-notebook-bindings",
    title="Rattachements du compte rendu de pendule",
    production_plan=pendulum_production_plan,
    bindings=(
        CellProductionBinding(
            "dynamic-answer",
            "gravity_dynamic",
            dynamic_cell,
            CellTextScope.after_marker("Réponse :"),
        ),
        CellProductionBinding(
            "dynamic-uncertainty-justification",
            "uncertainty_justification",
            dynamic_cell,
            CellTextScope.after_marker("Réponse :"),
        ),
        CellProductionBinding(
            "static-answer",
            "gravity_static",
            NotebookCellSelector(
                NotebookCellSelectorKind.CELL_ID,
                "cell-gravity-static",
            ),
            CellTextScope.full_source(),
        ),
        CellProductionBinding(
            "comparison-answer",
            "gravity_comparison",
            NotebookCellSelector(
                NotebookCellSelectorKind.SOURCE_MARKER,
                "TPSTUDIO: gravity_comparison",
            ),
            CellTextScope.after_marker("Réponse :"),
        ),
    ),
)
```

Le plan scientifique peut aussi contenir `period_plot` et
`final_interpretation` sans leur imposer immédiatement un rattachement.

## Cardinalités et ordre

Une même cellule peut viser plusieurs productions, comme
`gravity_dynamic` et `uncertainty_justification`. Inversement, une production
peut posséder plusieurs bindings, par exemple une cellule de résultat et une
cellule de justification. A69b ne définit pas encore comment plusieurs
cellules seront agrégées ou évaluées.

L'ordre de déclaration est conservé. `in_evaluation_order` regroupe les
bindings suivant `ScientificProductionPlan.evaluation_order`, tout en gardant
l'ordre déclaré entre les bindings d'une même production.

## Limites avant A69c

Un sélecteur ne garantit pas qu'une cellule existe. A69b ne parcourt aucune
cellule, ne cherche ni identifiant, ni tag, ni marqueur, et ne produit aucun
diagnostic lorsqu'une correspondance manque ou apparaît plusieurs fois. La
politique de résolution, de découpage et d'agrégation appartiendra à A69c.

A69b n'appelle pas A69a, n'exécute aucun code, n'inspecte aucune sortie et ne
produit ni feedback, ni score.
