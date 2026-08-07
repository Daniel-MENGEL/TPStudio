# Rapport professeur Snell-Descartes — A71d

Le rapport peut désormais alimenter le plan A71e pour localiser les commentaires, sans transformer ses priorités ni ses conseils agrégés en nouveaux feedbacks.

A71d transforme le `CopyAnalysisResult` A71c en restitution professeur immuable. A71c analyse et évalue ; A71d présente les objets déjà obtenus. Le builder ne relit aucune cellule, ne relance aucun moteur et ne produit aucune nouvelle conclusion scientifique.

## Contenu et priorités

`TeacherCopyReport` conserve la synthèse, les priorités, l'état technique enregistré, les dix-neuf productions, les valeurs et leur provenance, les quantités et incertitudes, les relations, le graphe, les deux comparaisons, les diagnostics, les feedbacks configurés, la conclusion finale, les limitations et les raisons de revue humaine.

La sévérité `INFO`, `ATTENTION`, `IMPORTANT` ou `BLOCKING` règle uniquement l'affichage. Elle n'est ni une note ni un score et ne modifie aucun statut scientifique. L'ordre est déterministe : sévérité, ordre pédagogique, identifiant stable.

Chaque comparaison sépare les résultats quantitatifs, le En objectif A70b, le En étudiant A70d, l'interprétation A70e et la justification A70g. La conclusion finale demeure indépendante. Une limitation, notamment celle des unités sans dimension, n'est jamais transformée en faute étudiante.

## Markdown et script local

`render_teacher_report_markdown()` produit la représentation textuelle canonique. Les audiences professeur et étudiant restent distinctes et aucun feedback n'est inventé. Les preuves sont de courts extraits déjà disponibles ; chemin, identité, réponses complètes, images et métadonnées privées sont exclus.

`scripts/report_snells_laws_copy.py COPY.ipynb` analyse en lecture seule et affiche un résumé compact. `--output REPORT.md` demande explicitement l'écriture ; `--force` est requis pour remplacer un rapport existant. Aucune option d'exécution n'existe.

## Continuité avec le prototype A61

A61 avait démontré l'intérêt d'une synthèse rapide, de priorités, de diagnostics localisés, de la cohérence numérique, du graphe et de conseils ciblés. A71d reprend cette ergonomie avec une architecture différente :

```text
configuration professeur
→ analyse A71c
→ évaluations typées
→ diagnostics configurés
→ feedbacks configurés
→ rapport A71d
```

Les conseils ciblés dédupliquent uniquement les feedbacks étudiant existants. Les heuristiques historiques ne redeviennent pas l'autorité scientifique.

## Confidentialité et limites

Le rapport utilise `source_id`, jamais le chemin local. Il n'exécute ni ne modifie le notebook, n'analyse aucun pixel et ne produit ni HTML, ni PDF, ni commentaire inséré, ni notation. A71e prendra en charge l'annotation contrôlée ; A71f, les exports notebook et HTML. La validation humaine reste explicite.
A71f complète le rapport par l'export du notebook annoté et de son rendu HTML ;
la restitution scientifique reste celle d'A71d.
