# Observation et évaluation du En étudiant

A70d observe la valeur finale de En écrite dans le texte résolu d'une
production `COMPARISON`. L'étudiant doit normalement effectuer ce calcul : le
`normalized_error` A70b reste une référence interne et ne lui est jamais
attribué.

Le professeur déclare explicitement les labels acceptés, par exemple
`("E_n", "En", "Eₙ")`, ainsi qu'une tolérance absolue `Decimal`. Il n'existe
aucune tolérance implicite. La frontière est inclusive : une différence égale
à la tolérance produit `MATCHES_REFERENCE`.

La recherche est littérale, sensible à la casse et sans normalisation. Elle
accepte `=` ou `≈`, les signes, le point ou la virgule décimale et une notation
scientifique simple. Elle observe une valeur finale comme `E_n = 2,2`, mais
pas une formule telle que `En = abs(g1-g2)/sqrt(u1**2+u2**2)`.
Une valeur numérique doit être complète : un préfixe appartenant à une
expression comme `En = 2*x` n'est pas une valeur finale. La détection conservée
est liée exactement au fragment textuel de la source résolue.
Une ponctuation accolée à la continuation d'un nombre ou d'une expression ne
constitue pas davantage une terminaison valide.
Les continuations `%`, `√` ou une multiplication implicite sont également des
expressions, pas des valeurs finales. Les littéraux numériques manifestement
pathologiques sont ignorés afin de garantir une évaluation déterministe et sûre.

Une seule résolution `RESOLVED` doit exister pour la comparaison. Un binding
échoué supplémentaire n'empêche pas son utilisation ; plusieurs sources
résolues sont ambiguës et ne sont jamais concaténées. Dans la source retenue,
une seule valeur doit être observée. Aucune première source ou première valeur
n'est choisie arbitrairement.

Exemple : une référence interne `2.236...`, une valeur étudiante `E_n = 2,2`
et une tolérance `0.1` donnent `MATCHES_REFERENCE`.

Ce statut signifie uniquement une concordance numérique. Il ne garantit ni
que la formule est correctement établie, ni que les étapes sont présentes, ni
que la conclusion est scientifiquement correcte. A70d n'inspecte aucune
variable ou output, ne relit pas le notebook et n'analyse pas la conclusion.
Il ne produit ni diagnostic, ni feedback, ni score, ni note.

A70e observe désormais séparément une conclusion littérale déclarée. Son
statut reste indépendant de la concordance numérique A70d : un En différent
peut accompagner une conclusion conforme, et réciproquement.
