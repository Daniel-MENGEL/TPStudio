# Diagnostics de la justification d'une comparaison

A70h transforme les statuts A70g non complets en trois codes structurés :
`JUSTIFICATION_PARTIAL`, `JUSTIFICATION_MISSING` et
`JUSTIFICATION_NOT_EVALUABLE`. Une justification `COMPLETE` ne produit aucun
diagnostic positif et ne devient pas pour autant scientifiquement correcte.

Chaque diagnostic conserve les éléments observés, les éléments `REQUIRED`
manquants, les groupes `ONE_OF_GROUP` satisfaits ou manquants, ainsi que les
statuts parallèles A70d et A70e. Ces listes ne sont ni reconstruites ni
transformées en un diagnostic par détail.

`NOT_EVALUABLE` produit exactement un diagnostic, avec ses raisons structurées.
`MISSING` signifie qu'une source exploitable ne contient aucune phrase
justificative déclarée ; cela ne signifie pas que la conclusion est fausse.
A70h ne recalcule rien et ne produit aucun texte, score, pénalité ou note.
