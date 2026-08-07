# Annotation contrôlée Snell-Descartes — A71e

A71e transforme les feedbacks déjà rendus par A71c en commentaires localisés dans une copie mémoire du notebook. Il ne recalcule aucun diagnostic, n'invente aucun feedback et ne modifie jamais la source.

```text
CopyAnalysisResult
        ↓
TeacherCopyReport
        ↓
AnnotationPlan
        ↓
apply_annotation_plan
        ↓
AnnotatedNotebookResult
        ↓
A71f export
```

## Plan et audiences

`build_annotation_plan()` utilise les `production_id`, `comparison_id` et résolutions de cellules déjà établis. Une cible absente ou ambiguë produit un `SkippedAnnotation` ; aucune première cellule arbitraire n'est choisie. Par défaut, seuls les feedbacks `STUDENT` sont annotés. Une copie professeur peut inclure explicitement les feedbacks `TEACHER` et les diagnostics existants. Les limitations sans cible restent signalées comme non applicables.

Un `comparison_id` n'est jamais recherché directement comme identifiant de production. Le plan vérifie la comparaison configurée puis réutilise les sources textuelles canoniques A70d, A70e et A70g. Des sources distinctes rendent la cible ambiguë ; une source absente reste indisponible. Les deux comparaisons Snell-Descartes conservent ainsi leurs cellules pédagogiques propres.

Chaque diagnostic et feedback projeté par A71d conserve une `source_key` métier distincte de son identifiant positionnel d'affichage. Elle combine le type public, le code métier, l'audience, la production ou comparaison et, lorsqu'elle existe, la variante configurée. A71e utilise exclusivement cette clé comme source logique.

Chaque `NotebookAnnotation` possède ainsi un identifiant stable dérivé du projet, du scope non privé, de l'audience, du type, de la `source_key` et de la cellule. Ni le message, ni la position dans le rapport, ni un timestamp, ni un chemin n'entrent dans cet identifiant. Un changement d'ordre ne modifie donc pas l'identité ; un message mis à jour remplace son ancienne version. Avec `--keep-existing`, le même feedback logique déjà présent n'est pas ajouté une seconde fois.

Lorsqu'un `TeacherCopyReport` est fourni au planificateur, il doit être exactement la projection canonique du `CopyAnalysisResult`. Un rapport modifié ne peut donc injecter ni texte, ni feedback, ni diagnostic, ni localisation. Sans rapport fourni, cette projection est reconstruite automatiquement.

Le notebook source ne peut jamais servir de destination, même avec `--overwrite` et même si les chemins utilisent des écritures syntaxiques différentes ou un lien symbolique. `--overwrite` autorise uniquement le remplacement explicite d'une copie dérivée existante.

L'ordre est déterministe par cellule, sévérité de présentation, type, source et identifiant. La sévérité sert uniquement au tri ; elle n'est jamais ajoutée au texte étudiant et ne constitue ni une note ni un score.

## Placement et format

Dans une cellule Markdown, le contenu original est conservé exactement puis un bloc délimité est ajouté :

```markdown
<!-- TPSTUDIO:BEGIN annotation_id=... -->
---
**Retour TPStudio**

Message configuré
<!-- TPSTUDIO:END annotation_id=... -->
```

Après une cellule de code ou raw, A71e crée une cellule Markdown dédiée. Le code, les outputs, `execution_count` et les métadonnées étudiantes restent inchangés. La cellule ajoutée porte des métadonnées `tpstudio.annotation`, `annotation_id`, `kind` et `audience`. Une cellule par annotation est volontairement retenue : cette stratégie favorise une suppression et une mise à jour sûres.

Si `annotate_code_by_adjacent_markdown=False`, une cible code ou raw est explicitement ignorée avec `PLACEMENT_DISABLED`. Les cibles Markdown restent annotables. L'option ne peut donc jamais provoquer l'ajout silencieux d'un commentaire dans le code.

## Idempotence, suppression et remplacement

`find_tpstudio_annotations()` reconnaît uniquement les blocs correctement délimités et les cellules ayant des métadonnées TPStudio valides. Une simple mention étudiante de « TPStudio » n'est pas une annotation.

`remove_tpstudio_annotations()` travaille sur une copie mémoire. Il retire soit toutes les annotations reconnues, soit les identifiants demandés, sans supprimer le reste de la cellule. Avec `replace_existing_tpstudio_annotations=True`, l'application retire les annotations existantes, y compris les orphelines, puis matérialise exactement le plan courant. Avec `False`, les annotations existantes sont conservées et seules les nouvelles sont ajoutées.

L'application répétée d'un même plan produit un notebook structurellement identique : aucun bloc, espace ou cellule supplémentaire n'apparaît.

## Écriture et confidentialité

`write_annotated_notebook()` exige un chemin de sortie explicite et refuse l'écrasement par défaut. `default_annotated_notebook_name()` propose seulement un nom `*-correction.ipynb`. Le script `scripts/annotate_snells_laws_copy.py` n'écrit rien sans `--output` et ne possède aucune option d'exécution.

Les notebooks de test sont synthétiques. Aucun chemin, nom étudiant, résultat privé, note, score, HTML ou PDF n'est produit. A71f prendra en charge les exports ultérieurs.
