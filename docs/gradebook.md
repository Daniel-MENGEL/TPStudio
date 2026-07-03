# Suivi de séance de TP avec TPStudio

Ce document résume le workflow recommandé pour contrôler les copies de TP et générer les fichiers de suivi.

## Commande recommandée

```bash
tpstudio export-gradebook-bundle "$DOSSIER" \
  --session "Séance n°2" \
  --tp-name "Lois de Snell Descartes" \
  --kholle-week "25" \
  --students-file data_private/liste_etudiants_pcsi2.csv \
  --check-first \
  --summary-md \
  --summary-html
```

## Fichiers générés

La commande crée automatiquement quatre fichiers dans le dossier de copies :

```text
<tp>-semaine-<n>-suivi.csv
<tp>-semaine-<n>-anomalies.csv
<tp>-semaine-<n>-rapports-non-rendus.csv
<tp>-semaine-<n>-bilan.md
<tp>-semaine-<n>-bilan.html
```

## Rôle des fichiers

- `*-suivi.csv` : fichier principal pour saisir les notes.
- `*-anomalies.csv` : noms présents dans les notebooks mais non reconnus dans la liste officielle.
- `*-rapports-non-rendus.csv` : étudiants de la liste officielle sans copie détectée.
- `*-bilan.md` : synthèse lisible de la séance au format Markdown.
- `*-bilan.html` : synthèse lisible de la séance au format HTML.

## Contrôle préalable

L’option `--check-first` lance un contrôle avant l’export.

Sont bloquants :

- les noms non reconnus ;
- les identités absentes.

Ne sont pas bloquants :

- les rapports non rendus, car tous les étudiants ne sont pas forcément présents à chaque séance de TP.

Pour forcer l’export malgré une anomalie bloquante :

```bash
--allow-issues
```

## Contrôle rapide sans export

```bash
tpstudio check-gradebook "$DOSSIER" \
  --session "Séance n°2" \
  --tp-name "Lois de Snell Descartes" \
  --kholle-week "25" \
  --students-file data_private/liste_etudiants_pcsi2.csv
```


## Ouverture automatique

Pour ouvrir automatiquement le bilan généré :

```bash
--open-summary
```

TPStudio ouvre en priorité le bilan HTML s'il a été généré, sinon le bilan Markdown.

Pour ouvrir le dossier contenant les exports :

```bash
--open-folder
```
