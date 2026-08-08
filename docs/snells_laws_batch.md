# Lot Snell-Descartes A71g

A71g applique séquentiellement la verticale unitaire A71f à une liste
explicitement sélectionnée de copies. Il ne scanne pas un dossier et ne déduit
aucune identité étudiante : les `source_id` sont fournis par l'appelant ou,
dans le script local, générés comme `copy-001`, `copy-002`, etc.

```
Copies sélectionnées → BatchPlan → A71f → BatchCopyResult
                                      ↓
                               BatchRunResult → rapport de lot
```

Les copies sont traitées dans l'ordre, sans concurrence. Une erreur produit un
résultat `FAILED` isolé et n'empêche pas les suivantes lorsque
`continue_on_error=True`. A71f conserve sa transaction notebook/HTML : une
copie échouée n'annonce aucun artefact. Les collisions de basename sont
désambiguïsées avec le `source_id`, et `overwrite` est appliqué copie par
copie.

`BatchPlan.planned_outputs` est l'autorité des destinations : ces deux chemins
sont transmis explicitement à A71f, qui conserve la transaction et les
protections source/output. Les messages d'erreur publics sont réduits à des
formulations anonymisées ; aucun chemin brut n'apparaît dans les résultats,
résumés ou rapports. `requires_human_review` reste indéterminé (`None`) lorsque
la seule sortie A71f ne transporte pas cette information. Toute exception
applicative d'une copie est isolée et devient `FAILED`; `KeyboardInterrupt`,
`SystemExit` et `GeneratorExit` ne sont jamais absorbés. Dans les résumés,
`True`, `False` et `None` sont respectivement rendus « oui », « non » et
« indéterminée ». `human_review_count` compte uniquement les revues confirmées.
Un lot est `success` seulement si toutes ses copies sont `SUCCESS` : un lot
entièrement `SKIPPED` n'est donc pas un succès complet. Les destinations
explicites reçues par A71f restent confinées canoniquement dans `output_dir`.
Le script retourne donc zéro uniquement pour un lot entièrement réussi, et un
code non nul dès qu'une copie est `FAILED` ou `SKIPPED`. Un `BatchRunResult`
final ne contient jamais `PENDING`; `BatchPlan` vérifie la correspondance
structurelle entre sources et sorties avant l'exécution.

`BatchCopySource.output_stem`, lorsqu'il est fourni par une couche appelante
(par exemple l'interface A72), est un simple stem logique : non vide, sans
espaces périphériques, séparateurs de chemin, NUL ni suffixe `.ipynb` ou
`.html`. Il ne contient jamais un chemin ni un nom de fichier complet. Sans
ce champ, le nommage historique A71g reste inchangé ; A71g ne lit ni
n'interprète l'identité des étudiants.

Les résumés et rapports n'affichent que les identifiants anonymes et les
basenames d'artefacts. Aucun notebook n'est exécuté, aucun PDF, aucune note et
aucune donnée privée ne sont produits. A72 pourra fournir la sélection
multiple et la progression graphique.
