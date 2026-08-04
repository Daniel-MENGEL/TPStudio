# Diagnostics de l'interprétation des comparaisons

A70f transforme les statuts A70e en diagnostics structurés sans relancer
l'extraction et sans réévaluer la conclusion. Trois codes existent :

- `INTERPRETATION_PARTIALLY_MATCHES` ;
- `INTERPRETATION_CONTRADICTS` ;
- `INTERPRETATION_NOT_EVALUABLE`.

Une conclusion `MATCHES_OBJECTIVE_CLASSIFICATION` ne produit aucun diagnostic
positif. Une interprétation non évaluable produit exactement un diagnostic,
même lorsque plusieurs raisons sont conservées dans
`not_evaluable_reasons`.

Le diagnostic conserve séparément le classement objectif A70b, le statut du
En étudiant A70d lorsqu'il existe, et la conclusion A70e. Il ne recalcule En,
ne conclut rien sur le calcul étudiant et ne contient aucun texte, score,
pénalité ou note.
L'évaluation structurelle A70g de la justification reste une branche distincte
et ne modifie aucun diagnostic A70f.
Les diagnostics A70h portent uniquement sur sa complétude structurelle et ne
modifient pas davantage les diagnostics d'interprétation.
