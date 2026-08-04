# Feedback de l'interprétation des comparaisons

Les feedbacks A70f proviennent exclusivement d'un catalogue explicitement
fourni. Aucun catalogue, y compris le catalogue français d'exemple, n'est
activé implicitement. Les templates distinguent les audiences `STUDENT` et
`TEACHER`.

La résolution cherche successivement : contexte et kind exacts, contexte exact
et kind générique, contexte générique et kind exact, puis variante entièrement
générique. Elle ne traverse jamais les codes ou les audiences et ne produit
qu'un message par audience.

Avec `METHOD_LIMITATION_EXPECTED`, les conclusions `INCOHERENT` et
`STRONGLY_INCOHERENT` peuvent recevoir une formulation étudiant spécifique ;
le diagnostic reste inchangé. Une conclusion conforme grâce à
`METHOD_LIMITATION` ne produit aucun feedback positif automatique.

Pour `NOT_EVALUABLE`, le catalogue français ne fournit par défaut qu'un
message professeur. Les raisons détaillées restent structurées. Aucune valeur
de En interne ou étudiant n'est interpolée automatiquement.

`HIGH` indique uniquement une visibilité élevée : il ne réordonne pas les
items et ne représente ni gravité de notation, ni pénalité, ni impact sur une
note. A70f ne valide pas la justification détaillée ; cette évaluation devra
combiner ultérieurement plusieurs critères séparés.
A70g observe désormais la présence d'éléments justificatifs, mais ces messages
ne sont ni créés ni modifiés automatiquement à partir de ce nouveau statut.
Les feedbacks A70h utilisent leur propre catalogue explicite et peuvent lire
le statut A70e uniquement comme axe de sélection d'un message configuré.
