# Feedback configurable des grandeurs

A68g produit les premiers éléments présentables du niveau 5 de l'architecture :

1. production attendue ;
2. spécification détaillée ;
3. observation ;
4. évaluation ;
5. diagnostic structuré, feedback formulé et, plus tard, notation.

Le diagnostic A68f décrit objectivement un résultat d'évaluation. Le feedback
A68g associe à son code un texte choisi explicitement. Modifier une
formulation, son destinataire ou sa priorité ne modifie jamais le diagnostic.

## Catalogue explicite

`QuantityFeedbackCatalog` contient au plus un `QuantityFeedbackTemplate` par
code. Chaque template fournit un texte statique exact, une audience et une
priorité. Le renderer ne contient aucun catalogue implicite : l'appelant doit
toujours en fournir un.

```python
from tpstudio.feedback import (
    french_quantity_feedback_catalog,
    render_quantity_feedback,
)

feedback = render_quantity_feedback(
    diagnostic_set,
    french_quantity_feedback_catalog(),
)
```

Lorsqu'un code est absent du catalogue, aucun item n'est produit. Il n'existe
ni fallback, ni texte inventé, ni feedback positif automatique. Omettre un
code permet donc de supprimer volontairement sa présentation.

`message_key` reste l'identifiant abstrait porté par le diagnostic. `text` est
la formulation exacte du catalogue. A68g n'interprète aucun placeholder et ne
substitue aucune donnée dans le texte. Le `production_label`, récupéré depuis
le plan scientifique, est exposé séparément ; une future interface pourra le
combiner avec le texte.

## Audience et priorité

`FeedbackAudience.STUDENT` désigne un message susceptible d'être montré à
l'étudiant. `FeedbackAudience.TEACHER` conserve une note de contrôle ou de
revue réservée au professeur. Les propriétés `student_items` et
`teacher_items` maintiennent cette séparation dans l'ordre original.

Le contrôle `UNCERTAINTY_JUSTIFICATION_DEFERRED` ne prouve aucune erreur de
l'étudiant. Tout template associé doit donc viser `TEACHER`. Le catalogue
français formule seulement : « La justification de l’incertitude doit encore
être vérifiée. »

`FeedbackPriority.LOW`, `NORMAL` et `HIGH` sont des métadonnées de présentation
ou de traitement. Une priorité n'est ni une sévérité scientifique, ni une
pénalité, ni un nombre de points. Elle ne réordonne pas les items : l'ordre des
diagnostics A68f reste la référence.

## Provenance conservée

Chaque `QuantityFeedbackItem` conserve son `QuantityDiagnostic` complet et le
template exact utilisé. L'observation sélectionnée par A68d, le critère, le
statut et la source restent ainsi accessibles. Le renderer ne fusionne ni ne
déduplique des diagnostics distincts et ne modifie aucune entrée.

## Catalogue français d'exemple

`french_quantity_feedback_catalog()` retourne à chaque appel un nouveau
catalogue immuable couvrant les sept codes A68f. Il contient six formulations
étudiant et une note professeur pour la justification différée. Ce catalogue
est une configuration d'exemple et n'est jamais activé automatiquement.

Plusieurs langues pourront être proposées par plusieurs catalogues. A68g ne
traduit aucun texte automatiquement et ne dépend d'aucun service externe.

## Limites

Les textes sont statiques et configurés, jamais générés. A68g ne calcule
aucune note, n'applique aucun barème, ne déduit aucun point, ne produit aucune
appréciation et ne propose pas de solution scientifique. Une future couche de
notation restera distincte du diagnostic, du texte et de sa priorité.
