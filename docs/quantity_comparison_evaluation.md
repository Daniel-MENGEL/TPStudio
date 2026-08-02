# Évaluation objective des comparaisons quantitatives

A70b combine les évaluations quantitatives A69d et les déclarations A70a sans
relire le notebook. Il réutilise les `QuantityObservation` sélectionnées par
A69a et calcule exclusivement avec `Decimal` :

```text
En = |x1 - x2| / sqrt(u1² + u2²)
```

Le `Context` Decimal est entièrement explicite, déterministe, de précision au
moins 28 et utilise `ROUND_HALF_EVEN`. Ses traps et limites d'exposants ne
dépendent pas de ceux configurés par l'appelant. Le classement compare les carrés exacts plutôt que
la valeur arrondie affichée : En < 2 est `COHERENT`, 2 <= En < 4 est
`MODERATELY_INCOHERENT`, et En >= 4 est `STRONGLY_INCOHERENT`. En exactement
égal à 2 est donc modérément incohérent ; En exactement égal à 4 est fortement
incohérent. Les seuils configurés en A70a suivent les mêmes frontières.

9,7 ± 0,4 m comparé à 9,8 ± 0,2 m donne En proche de 0,224 et un résultat
`COHERENT`.

## Sélection et non-évaluabilité

Chaque côté doit fournir exactement un item `ASSESSED`. Cet item reste
utilisable avec un binding `RESOLUTION_FAILED` supplémentaire. Plusieurs items
`ASSESSED` concurrents donnent `NOT_EVALUABLE` : aucun résultat n'est choisi et
aucun texte n'est agrégé.

Les raisons structurées couvrent les évaluations indisponibles ou ambiguës,
les observations absentes, les valeurs invalides, les incertitudes absentes ou
non strictement positives, les unités absentes et `UNIT_MISMATCH`. Toutes les
raisons détectables sont conservées dans un ordre déterministe et En n'est pas
calculé si l'une d'elles est présente.

Les unités doivent être littéralement identiques, casse comprise. Aucune
conversion, normalisation ou interprétation dimensionnelle n'est effectuée.

## Référence interne et contexte pédagogique

`normalized_error` est un En de référence interne à TPStudio. Son calcul ne
signifie jamais que l'étudiant a calculé En : A70b ne recherche ni ne valide un
En étudiant, ne compense pas son absence, n'évalue ni sa démarche ni son
interprétation et n'insère rien dans la copie. De futurs jalons pourront
comparer séparément le calcul étudiant à cette référence, puis évaluer sa
conclusion. A70d réalise désormais la première de ces étapes par observation
littérale d'une valeur finale, sans vérifier la formule ni la conclusion.

Le contexte pédagogique est conservé mais n'agit ni sur En ni sur le statut.
Ainsi `METHOD_LIMITATION_EXPECTED` avec En > 4 reste
`STRONGLY_INCOHERENT`. A70b ne produit lui-même ni diagnostic, ni feedback, ni
pénalité, ni score, ni note. A70c peut désormais dériver des diagnostics et
des feedbacks configurables sans recalculer En.
