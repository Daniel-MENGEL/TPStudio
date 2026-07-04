# Correction individuelle

La commande `correct-copy` assemble les briques de correction déjà validées par TPStudio.

```bash
tpstudio correct-copy modele.ipynb copie-etudiant.ipynb   --output-dir corrections/
```

Elle crée, sans modifier la copie originale :

```text
corrections/
├── copie-etudiant-correction.ipynb
└── copie-etudiant-correction.md
```

Le notebook corrigé réutilise les diagnostics existants : comparaison au modèle, réponses écrites, code, graphiques, commentaires locaux, couleurs et synthèse globale.

Par sécurité, TPStudio refuse d'écraser une correction existante. Le remplacement doit être explicite :

```bash
--overwrite
```

## Exécution sécurisée

Pour exécuter une copie sans modifier l'original :

```bash
tpstudio execute-copy copie-etudiant.ipynb   --output-dir executions/
```

Options utiles :

```bash
--cell-timeout 60
--kernel-name python3
--continue-on-error
--overwrite
```

Pour exécuter la copie temporaire avant sa correction :

```bash
tpstudio correct-copy modele.ipynb copie-etudiant.ipynb   --output-dir corrections/   --execute-first
```

Le rapport Markdown indique alors le statut de l'exécution, le nombre de cellules tentées et la première erreur détectée.

### Sélection automatique du kernel

Sans `--kernel-name`, TPStudio :

1. utilise le kernel déclaré dans le notebook s'il est disponible ;
2. sinon utilise automatiquement `python3` s'il est disponible ;
3. sinon s'arrête avec la liste des kernels disponibles.

Le rapport indique le kernel déclaré, le kernel utilisé et l'éventuel fallback automatique.

Un `--kernel-name` fourni explicitement reste prioritaire et n'est jamais remplacé silencieusement.

## Sections pédagogiques hors « Réponse : »

TPStudio analyse aussi certaines sections Markdown importantes même lorsqu'elles ne contiennent pas le marqueur `Réponse :`.

A61a couvre d'abord :

- Protocole ;
- Objectifs ;
- Problématique.

Une section fragile ou vide produit un commentaire local et apparaît dans le rapport Markdown.

## Comparaison sémantique du code

A61b compare les cellules de code de la copie au corrigé et ne signale que des écarts à forte confiance :

- constante numérique modifiée dans une formule de même structure ;
- numérateur et dénominateur inversés ;
- opérateur binaire modifié avec les mêmes opérandes.

Les tableaux de mesures et autres conteneurs de données peuvent différer du corrigé sans être signalés.

### Alignement des formules entre notebooks

A61b-bis ne dépend plus du découpage identique des cellules. Les affectations d'une même variable sont rapprochées selon la structure de leur expression.

Cela permet notamment de comparer un corrigé contenant une grosse cellule de code avec une copie où le même calcul a été réparti sur plusieurs petites cellules.

