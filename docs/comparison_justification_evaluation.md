# Évaluation structurelle de la justification d'une comparaison

A70g distingue la conclusion observée par A70e de ses éléments justificatifs.
Le professeur déclare des éléments et leurs phrases littérales : `REQUIRED`
doit être observé, `OPTIONAL` enrichit sans conditionner la complétude, et
`ONE_OF_GROUP` exige au moins un membre du groupe alternatif.
`OPTIONAL` n'est jamais une obligation de complétude. Une attente composée
uniquement d'éléments facultatifs donne `PARTIAL` si au moins l'un d'eux est
observé, et `MISSING` en l'absence d'observation ; elle ne donne jamais
`COMPLETE`.

L'extraction est sensible à la casse et à l'Unicode exact. Elle ne normalise,
ne corrige et n'invente aucun synonyme. Toutes les occurrences exactes sont
conservées, y compris les chevauchements à des offsets distincts. Une seule
source `RESOLVED` est exploitable ; plusieurs sources ne sont jamais réunies
ou départagées.

`COMPLETE` signifie seulement que tous les éléments obligatoires et groupes
alternatifs déclarés sont structurellement présents. Il ne signifie pas que
le En est juste, que le seuil est pertinent, que la cause citée est vraie ou
que la justification est scientifiquement correcte. Une présence incomplète
donne `PARTIAL`, aucune observation dans une source exploitable donne
`MISSING`, et une source indisponible ou ambiguë donne `NOT_EVALUABLE`.

Les évaluations A70d et A70e sont conservées comme données parallèles et ne
modifient pas ce statut. A70g ne relit pas le notebook, ne recalcule pas En,
n'analyse pas librement le raisonnement et ne produit aucun diagnostic,
feedback, score, pénalité ou note. La pertinence scientifique détaillée reste
future.
