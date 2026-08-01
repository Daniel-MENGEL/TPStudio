# Diagnostics structurés des grandeurs

A68f commence le niveau 5 de l'architecture des productions scientifiques :

1. production attendue ;
2. spécification détaillée ;
3. observation ;
4. évaluation ;
5. diagnostic et, plus tard, feedback.

Le diagnostic A68f est uniquement une donnée structurée. Il traduit certains
résultats A68d et A68e en codes stables, sans rédiger de phrase, choisir une
tonalité, attribuer une sévérité ou calculer une note.

```python
from tpstudio.diagnostics import build_quantity_diagnostics

diagnostics = build_quantity_diagnostics(
    structural_evaluation,
    uncertainty_evaluation,
)
```

L'évaluation d'incertitude est facultative. Lorsqu'elle n'est pas fournie,
les échecs structurels et les contrôles obligatoires différés restent traduits,
mais aucun défaut de qualité n'est inventé.

## Codes, sources et clés

Les diagnostics ont deux sources : `STRUCTURE` pour A68d et
`UNCERTAINTY_QUALITY` pour A68e. La table de correspondance est unique :

| Code | Source | Critère | Statut | `message_key` |
|---|---|---|---|---|
| `QUANTITY_MISSING` | structure | quantité présente | insatisfait | `diagnostic.quantity.missing` |
| `UNIT_MISSING` | structure | unité présente | insatisfait | `diagnostic.quantity.unit_missing` |
| `UNCERTAINTY_MISSING` | structure | incertitude présente | insatisfait | `diagnostic.quantity.uncertainty_missing` |
| `UNCERTAINTY_NOT_STRICTLY_POSITIVE` | qualité | strictement positive | insatisfait | `diagnostic.quantity.uncertainty_not_strictly_positive` |
| `UNCERTAINTY_SIGNIFICANT_DIGITS_INVALID` | qualité | chiffres significatifs | insatisfait | `diagnostic.quantity.uncertainty_significant_digits_invalid` |
| `UNCERTAINTY_DECIMAL_PLACE_MISMATCH` | qualité | alignement décimal | insatisfait | `diagnostic.quantity.uncertainty_decimal_place_mismatch` |
| `UNCERTAINTY_JUSTIFICATION_DEFERRED` | structure | justification présente | différé | `diagnostic.quantity.uncertainty_justification_deferred` |

Le code identifie le problème de façon stable. `message_key` est seulement une
clé abstraite pour un futur moteur de rédaction : ce n'est pas un message
destiné à l'étudiant.

Un statut `UNSATISFIED` représente un contrôle exécutable qui a échoué. Le
diagnostic `DEFERRED` indique au contraire qu'un contrôle obligatoire n'a pas
encore pu être exécuté. En particulier,
`UNCERTAINTY_JUSTIFICATION_DEFERRED` ne signifie pas que la justification est
absente. Une justification optionnelle différée ne produit aucun diagnostic.

## Preuve et observation unique

Tous les diagnostics réutilisent exclusivement l'observation sélectionnée par
A68d. Aucune observation n'est fusionnée avec une autre. Pour
`QUANTITY_MISSING`, l'observation est nécessairement `None`, puisque la
production n'a pas été observée.

Pour les autres codes, l'observation sélectionnée localise le contexte exact.
Dans le cas de la justification différée, elle situe seulement la quantité :
elle ne prouve pas l'absence d'une justification.

Les évaluations d'origine restent conservées dans `QuantityDiagnosticSet`.
Un futur feedback pourra ainsi consulter les exigences, critères et résultats
détaillés sans ajouter de dictionnaire de données libre au diagnostic.

## Ordre et absence de double sanction

L'ordre est déterministe : échecs structurels dans l'ordre A68d, échecs de
qualité dans l'ordre A68e, puis contrôles obligatoires différés. Les échecs
réels précèdent donc toujours les contrôles non encore exécutables.

Un critère `SATISFIED` ou `NOT_APPLICABLE` ne produit rien. Lorsque
l'incertitude est absente, A68d produit au besoin `UNCERTAINTY_MISSING`, tandis
que les contrôles A68e sont non applicables. L'absence n'est donc jamais
sanctionnée deux fois.

## Coexistence avec les diagnostics d'inférence

`tpstudio.reasoning.diagnostics` demeure inchangé. Ses diagnostics historiques
proviennent de règles, de conclusions d'inférence et de `Fact`. Les diagnostics
A68f proviennent directement d'évaluations de productions scientifiques.

Aucune `QuantityObservation` n'est transformée artificiellement en `Fact`, et
aucun faux `rule_id` ou `InferenceResult` n'est créé. Une future couche
d'agrégation pourra présenter ensemble ces deux familles sans confondre leur
provenance.

## Limites

Une valeur n'est toujours pas comparée à une référence et une incertitude bien
présentée peut être scientifiquement fausse. A68f ne vérifie aucun calcul,
n'analyse aucune justification et n'interprète aucune unité. Il ne produit ni
message étudiant, ni recommandation, ni correction, ni sévérité, ni feedback,
ni score.
