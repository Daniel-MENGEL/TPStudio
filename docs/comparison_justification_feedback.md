# Feedback de la justification d'une comparaison

Les feedbacks A70h utilisent exclusivement un catalogue explicitement fourni.
Le catalogue français n'est jamais activé automatiquement et distingue les
audiences `STUDENT` et `TEACHER`.

Les variantes structurelles sont `GENERIC`, `REQUIRED_ELEMENTS_MISSING`,
`ALTERNATIVE_GROUPS_MISSING`, `REQUIRED_AND_ALTERNATIVE_MISSING` et
`OPTIONAL_ONLY`. La résolution cherche la variante, le contexte et le statut
A70e exacts, puis leurs axes génériques dans l'ordre déclaré ; seul le fallback
de variante vers `GENERIC` est autorisé.

`OPTIONAL_ONLY` rappelle que des preuves facultatives ne suffisent pas à une
justification complète. `METHOD_LIMITATION_EXPECTED` peut adapter le message
relatif à un groupe alternatif manquant, sans modifier A70g ni le diagnostic.
Une conclusion A70e conforme peut recevoir un message spécifique lorsque sa
justification est `MISSING`, montrant que les deux évaluations restent séparées.

Par défaut, `NOT_EVALUABLE` ne produit qu'un message professeur. Aucun En,
identifiant d'élément, groupe ou raison n'est interpolé automatiquement.
`HIGH` signifie seulement forte visibilité et ne change ni l'ordre ni une
note. Aucun feedback positif n'est produit pour `COMPLETE`; la pertinence
scientifique détaillée reste future.
