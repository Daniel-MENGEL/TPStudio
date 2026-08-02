# Diagnostics des comparaisons quantitatives

A70c transforme les résultats objectifs A70b en constats structurés, sans
recalculer En ni modifier leur statut. Trois codes existent :

- `COMPARISON_MODERATELY_INCOHERENT` ;
- `COMPARISON_STRONGLY_INCOHERENT` ;
- `COMPARISON_NOT_EVALUABLE`.

Une comparaison `COHERENT` ne produit aucun diagnostic positif. Chaque autre
comparaison produit exactement un diagnostic, dans l'ordre des évaluations.
Pour `NOT_EVALUABLE`, toutes les raisons A70b restent accessibles dans
`not_evaluable_reasons`, mais ne sont pas transformées en diagnostics séparés.
Cela évite notamment de répéter les constats A68f sur une unité ou une
incertitude individuelle.

Le contexte pédagogique est conservé, sans altérer le constat objectif.
`METHOD_LIMITATION_EXPECTED` ne supprime donc jamais une incohérence forte et
ne la transforme pas en cohérence.

Ces diagnostics ne contiennent aucun texte de présentation, aucune priorité,
aucun score et aucune pénalité.
