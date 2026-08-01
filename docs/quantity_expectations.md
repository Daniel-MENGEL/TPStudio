# Attendus de grandeurs numériques

`ExpectedQuantity` décrit la structure d'une grandeur attendue : son symbole,
les écritures explicitement acceptées pour ce symbole, son unité et les
exigences futures concernant l'unité, l'incertitude et sa justification. Le
professeur ne connaît pas nécessairement la valeur obtenue par l'étudiant et
aucune valeur numérique n'est stockée dans ce modèle.

`production_id` rattache chaque détail à une `ScientificProductionSpec` de
type `QUANTITY`. `QuantityExpectationSet` valide ce rattachement à un
`ScientificProductionPlan`, conserve l'ordre déclaré et offre aussi la vue
`in_evaluation_order` induite par les dépendances du plan.

## Exigences de présence

`PresenceRequirement` possède trois politiques déclaratives :

- `REQUIRED` indique qu'un futur évaluateur devra exiger l'élément ;
- `OPTIONAL` autorise son absence mais permettra de le vérifier s'il existe ;
- `IGNORE` désactive le futur contrôle de présence.

Ces politiques ne réalisent encore aucun contrôle. Une incertitude obligatoire
n'est ni extraite ni vérifiée, et sa justification n'est ni détectée ni
évaluée.

Les symboles et unités restent des chaînes littérales. Aucune dimension,
équivalence ou conversion d'unité n'est calculée. Une variante n'est acceptée
que parce que le professeur l'a déclarée.

## Exemple du pendule

Les valeurs de `g` ci-dessous seront calculées plus tard depuis les données de
chaque copie et pourront différer d'un poste à l'autre :

```python
from tpstudio.expectations import (
    ExpectedQuantity,
    PresenceRequirement,
    QuantityExpectationSet,
)

quantities = QuantityExpectationSet(
    plan=pendulum_plan,
    quantities=(
        ExpectedQuantity(
            production_id="gravity_dynamic",
            canonical_symbol="g",
            accepted_symbols=("g_exp",),
            canonical_unit="m·s⁻²",
            accepted_units=("m.s^-2", "m/s²"),
            unit_requirement=PresenceRequirement.REQUIRED,
            uncertainty_requirement=PresenceRequirement.REQUIRED,
            uncertainty_justification_requirement=PresenceRequirement.REQUIRED,
        ),
        ExpectedQuantity(
            production_id="gravity_static",
            canonical_symbol="g",
            canonical_unit="m·s⁻²",
            accepted_units=("m.s^-2", "m/s²"),
            unit_requirement=PresenceRequirement.REQUIRED,
            uncertainty_requirement=PresenceRequirement.OPTIONAL,
        ),
    ),
)
```

Le plan `pendulum_plan` contient notamment `period_plot` (`PLOT`),
`gravity_dynamic` (`QUANTITY`, dépendant de la courbe), `gravity_static`
(`QUANTITY`) et `gravity_comparison` (`COMPARISON`, dépendant des deux
quantités).

Une copie pourrait produire, à titre illustratif,
`g = (9,7 ± 0,4) m·s⁻²`. Cette valeur ne figure pas dans `ExpectedQuantity` :
elle devra provenir de la copie et de ses mesures.

A68c fournit désormais une
[observation textuelle limitée de ces quantités](quantity_observations.md).
Cette extraction ne modifie pas les attentes et ne constitue encore aucune
validation scientifique.
Ces observations peuvent ensuite alimenter
[l'évaluation structurelle A68d](quantity_structural_evaluation.md), qui
applique les exigences de présence sans valider la valeur scientifique.
A68e permet en complément de déclarer une
[politique de présentation de l'incertitude](quantity_uncertainty_evaluation.md)
sans ajouter de valeur de référence ni de formule de propagation.
