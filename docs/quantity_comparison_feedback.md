# Feedback des comparaisons quantitatives

A70c rend les diagnostics au moyen d'un
`QuantityComparisonFeedbackCatalog` explicitement fourni. Aucun catalogue,
même français, n'est activé implicitement.

Les templates distinguent les audiences `STUDENT` et `TEACHER`. Pour un code
et une audience, le catalogue cherche d'abord une variante correspondant
exactement au contexte pédagogique, puis une variante générique. Il n'existe
aucun fallback entre codes ou audiences. Les items suivent l'ordre des
diagnostics, puis l'ordre étudiant/professeur ; leur priorité ne les réordonne
pas.

`FeedbackPriority.HIGH` commande uniquement la visibilité. Elle ne représente
ni une sévérité scientifique, ni un poids de barème, ni une pénalité. Une forte
incohérence peut ainsi être très visible tout en ayant ultérieurement un faible
impact sur une note.

Le catalogue français explicite fournit un message étudiant pour les
incohérences modérées et fortes. Avec `METHOD_LIMITATION_EXPECTED`, il remplace
le message étudiant générique par une variante adaptée et ajoute une note au
professeur. Le diagnostic demeure une forte incohérence. Pour
`NOT_EVALUABLE`, le catalogue ne fournit par défaut qu'un message professeur,
afin de ne pas doubler les diagnostics quantitatifs individuels.

La valeur `normalized_error` reste disponible comme donnée structurée, mais
n'est jamais interpolée automatiquement dans le texte étudiant. Elle est une
référence interne : A70c ne prétend pas que l'étudiant a calculé En, ne vérifie
pas son calcul et n'évalue pas son interprétation. Aucun feedback positif,
score ou note n'est produit.
