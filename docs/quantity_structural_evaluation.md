# Évaluation structurelle des grandeurs

A68d introduit le quatrième niveau de l'architecture des productions
scientifiques, uniquement pour les grandeurs textuelles simples :

1. la **production attendue** décrit ce que l'étudiant doit produire ;
2. la **spécification détaillée** `ExpectedQuantity` déclare sa structure ;
3. l'**observation** conserve ce qui a été extrait de la copie ;
4. l'**évaluation** confronte cette observation aux exigences structurelles ;
5. le **diagnostic et le feedback** traduiront ultérieurement le résultat.

`QuantityStructuralEvaluator` reçoit une `QuantityDetection` A68c et le
`QuantityExpectationSet` correspondant. Il retourne une
`QuantityStructuralEvaluation` immuable, sans message ni note.

```python
from tpstudio.evaluation import evaluate_quantity_structure
from tpstudio.reasoning import extract_expected_quantity

detection = extract_expected_quantity(
    "g = (9,7 ± 0,4) m·s⁻²",
    gravity_expectation,
)
evaluation = evaluate_quantity_structure(detection, quantity_expectation_set)
```

## Critères et statuts

Quatre critères sont toujours conservés dans cet ordre : présence de la
quantité, de l'unité, de l'incertitude et de la justification de
l'incertitude. Le symbole n'est pas séparé : A68c ne produit une observation
que pour un symbole explicitement déclaré.

- `SATISFIED` : le contrôle applicable est satisfait ;
- `UNSATISFIED` : un élément exigé et observable est absent ;
- `NOT_APPLICABLE` : le contrôle est ignoré ou aucune quantité ne permet de
  l'appliquer ;
- `DEFERRED` : l'exigence existe, mais l'observation nécessaire n'existe pas.

`UNSATISFIED` et `DEFERRED` sont distincts. Une unité obligatoire absente est
observable et donc insatisfaite. Une justification reste différée car A68d ne
dispose d'aucun extracteur de justification. Ces statuts sont internes et ne
sont pas encore des diagnostics pédagogiques.

`OPTIONAL` accepte l'absence tout en conservant l'observation éventuelle.
`IGNORE` désactive le contrôle : son statut est `NOT_APPLICABLE` et sa
propriété `observed` vaut `None`.

Une production générique facultative et absente satisfait le critère de
présence. Les autres critères sont alors non applicables. Pour une production
obligatoire absente, seule sa présence est insatisfaite.

## Une observation cohérente

Lorsque plusieurs observations existent, une seule est sélectionnée. Le
choix maximise d'abord le nombre d'éléments `REQUIRED` présents parmi l'unité
et l'incertitude, puis celui des éléments `OPTIONAL`. À qualité égale,
l'observation la plus tôt dans le texte est retenue, puis celle dont la fin
est la plus précoce.

Deux observations ne sont jamais fusionnées. Une unité trouvée dans l'une ne
peut donc pas compléter l'incertitude trouvée dans une autre.

## Lecture du résultat

`failures` conserve les contrôles `UNSATISFIED`, `deferred` tous les contrôles
différés et `required_deferred` seulement ceux qui sont obligatoires.
`is_complete` exige qu'aucun contrôle ne soit différé ;
`is_required_complete` ignore les contrôles optionnels différés. Enfin,
`satisfied` est vrai seulement sans échec ni contrôle obligatoire différé.
Une justification optionnelle différée rend donc l'évaluation incomplète,
mais pas insatisfaite.

## Limites

`SATISFIED` ne signifie pas que la valeur est scientifiquement correcte. Une
unité présente est seulement une chaîne déclarée reconnue littéralement : sa
dimension n'est pas validée et elle n'est pas convertie. Une incertitude
présente n'est jugée ni positive, ni raisonnable, ni correctement arrondie.
La justification reste différée lorsqu'elle doit être contrôlée.

A68d ne compare aucune référence ou méthode, ne recalcule rien depuis les
données et ne produit ni `Fact`, ni règle, ni diagnostic, ni feedback, ni
score.

A68d vérifie seulement la présence de l'incertitude. Lorsqu'elle est présente,
[A68e examine certaines propriétés intrinsèques de sa présentation](quantity_uncertainty_evaluation.md)
en réutilisant exactement l'observation sélectionnée ici.

Les échecs structurels et les contrôles obligatoires différés peuvent désormais
être traduits en [diagnostics structurés A68f](quantity_diagnostics.md), sans
devenir encore des messages destinés à l'étudiant.
