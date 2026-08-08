# Interface web locale TPStudio — A72c

A72a fournit un premier écran Streamlit local pour sélectionner plusieurs
notebooks, régler les options principales et préparer un `BatchPlan` A71g.
Cette étape ne lance aucune correction.

```text
Navigateur local
      ↓
Interface Streamlit A72
      ↓
Adaptateur web
      ↓
BatchPlan A71g
      ↓
[pas encore exécuté en A72a]
```

Lancement local :

```bash
/opt/anaconda3/bin/python3 -m streamlit run src/tpstudio/web/app.py --server.address localhost
```

Les uploads sont matérialisés dans un workspace temporaire contrôlé par
TPStudio, sous un dossier par copie (`copy-001/tp.ipynb`). Le basename original
est ainsi conservé, tandis que les chemins canoniques restent distincts. Les
identifiants `copy-001`, `copy-002`, etc. suivent l'ordre de sélection et ne
déduisent aucune identité étudiante. Les noms de sorties et les collisions
restent exclusivement décidés par A71g ; l'interface affiche
`BatchPlan.planned_outputs`.

Chaque sélection porte une empreinte SHA-256 du contenu pour invalider un plan
si le fichier change, y compris à taille identique. Les erreurs affichées sont
réduites à des messages non sensibles ; les chemins internes du workspace ne
sont jamais présentés.

## Identité des copies

L'identité est lue d'abord dans les premières cellules Markdown du notebook,
avec quelques libellés explicites (`Noms`, `Étudiants`, `Binôme`). Le nom du
fichier n'est qu'un indice secondaire ; un fichier CSV pourra devenir une
source de référence ultérieure, mais n'est pas implémenté ici. Une identité
absente ou divergente reste « À vérifier » et n'est jamais inventée.

Lorsqu'elle est confirmée, l'interface propose un stem déterministe du type
`Lois-de-Snell-Descartes-Jules-BERNARD-Daniel-MENGEL`. Ce stem est transmis à
A71g via son extension générique `output_stem`, qui reste l'autorité des
sorties et de leurs collisions.

Le plan est invalidé si les sélections, options, identités ou dossier de sortie
changent. Depuis A72b, une identité `CONFIRMED` est requise pour lancer le lot ;
les états « À vérifier » et « Non renseignée » bloquent l'action. Le bouton
`Corriger le lot` délègue exclusivement à `run_snells_laws_batch()` : aucune
cellule n'est exécutée, les erreurs restent isolées par copie et les artefacts
notebook/HTML produits par A71f sont téléchargeables. `overwrite` reste géré
par le moteur. Le bouton Réinitialiser nettoie uniquement le workspace
temporaire de la session.

## Confort A72c

Le champ « Dossier des corrections » est proposé avec un chemin local basé sur
`Path.home()` : `~/Documents/Sup/TP/Notebooks-corrigés/`. Il peut être modifié,
est résolu avant le lancement et n'est créé qu'au moment de produire les
artefacts. Le dossier ne peut pas être un fichier et les protections de
confinement A71f restent actives.

Les annotations conservent leur message et leur sévérité métier, avec une
présentation visuelle centralisée : vert doux pour `info`, bleu pour
`important`, ambre pour `attention` et rouge doux pour `blocking`. Chaque
annotation porte aussi un libellé textuel (« Très bien », « Remarque », « À
vérifier », « Problème »), afin de rester compréhensible sans couleur et à
l'impression. Le HTML embarque ces styles sans ressource réseau.

Le chargeur A71 normalise uniquement en mémoire les identifiants de cellules
vides ou dupliqués et les formes de `source` héritées ; le fichier uploadé reste
inchangé byte-for-byte.
