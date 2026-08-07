# Export Snell-Descartes A71f

A71f produit deux artefacts dérivés unitaires à partir d'une copie fournie
explicitement : un notebook `-correction.ipynb` et un HTML `-correction.html`.
Le flux est :

```
A71b configuration → A71c analyse → A71d rapport → A71e annotation → A71f export
```

Le notebook source est chargé en lecture seule, puis sa copie annotée est
validée avec `nbformat`. Le HTML est rendu par l'API Python de `nbconvert`
depuis exactement ce notebook annoté. Les commentaires TPStudio, les sorties
enregistrées, les graphes, les pièces jointes et les formules LaTeX sont ainsi
conservés selon les options de rendu.

Le dossier de sortie est obligatoire dans le script local. Les chemins sont
résolus avant toute écriture : une destination équivalente au notebook source,
y compris par lien symbolique, est refusée. `overwrite` ne concerne qu'une
copie dérivée déjà existante. Le document HTML complet produit par nbconvert
est personnalisé dans sa structure existante : il ne contient qu'un seul
`html`, `head`, `body` et `title`, avec un bandeau TPStudio injecté une seule
fois. Les deux artefacts sont préparés et validés sur des fichiers temporaires,
puis installés avec rollback explicite en cas d'échec ; aucune exécution de
notebook, aucun PDF, aucune note et aucune donnée privée ne sont produits.

Le code et les sorties restent dans le notebook exporté. Ils sont visibles par
défaut dans le HTML et peuvent seulement être masqués au niveau du rendu, sans
modifier le notebook. A71g prendra en charge le traitement par lot ; A72
prendra en charge l'interface.
