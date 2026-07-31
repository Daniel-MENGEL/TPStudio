# Glossaire scientifique

TPStudio embarque un glossaire scientifique minimal et extensible. Il permet
aux diagnostics rédactionnels de reconnaître un vocabulaire pertinent sans
déduire, à lui seul, la validité scientifique d'une réponse.

## Rôle actuel

Le glossaire est utilisé par :

- le diagnostic des zones `Réponse :` ;
- le diagnostic des sections `Protocole`.

Les correspondances sont déterministes, insensibles à la casse et aux accents.
Elles utilisent des limites de mots et ne confondent donc pas, par exemple,
`angle` avec `angleur`. Une seule occurrence est retournée par terme, dans
l’ordre d’apparition du texte. Les positions publiées désignent toujours le
texte original, même lorsque les espaces ou la ligature `œ` sont normalisés.
Elles couvrent notamment le vocabulaire d'optique déjà reconnu par TPStudio :
réfraction, indice, angles, instruments, mesures, incertitudes et analyse de
résultats.

L'absence d'un terme n'est pas une erreur scientifique : elle reste un indice
de rédaction destiné à attirer l'attention du professeur.

## Extension par domaine

Un appelant Python peut fournir un `Glossary` explicite aux fonctions de
diagnostic :

```python
from tpstudio.glossary import Glossary, ScientificTerm
from tpstudio.response_diagnostics import diagnose_response

electricity = Glossary(
    "electricity",
    "Électricité",
    (ScientificTerm("conductivite", "conductivité", "quantity"),),
)

diagnosis = diagnose_response(response, glossary=electricity)
```

Un terme possède un identifiant stable en ASCII, un libellé, une catégorie, des alias,
ainsi que des métadonnées de domaine, de TP, de relations et d'unités
attendues. `GlossaryRegistry` permet de composer plusieurs glossaires en
vérifiant l'unicité de leurs identifiants de termes. Un `Glossary` refuse
aussi directement les identifiants dupliqués.

## Relation avec le moteur de raisonnement

Le sous-package `tpstudio.reasoning` n'est pas encore un moteur d'inférence.
Le glossaire ne dépend donc pas de lui. Ses correspondances peuvent toutefois
devenir des `Fact` localisés lorsqu'un évaluateur de `Rule` et `Condition` sera
introduit dans un jalon ultérieur.

## Limites connues

Le glossaire ne comprend pas encore de chargement depuis un fichier de
configuration, de désambiguïsation contextuelle, ni de validation des unités
ou relations scientifiques. Il ne remplace pas la comparaison de code, de
graphes ou de résultats numériques.

## Compatibilité des diagnostics historiques

Le glossaire intégré conserve les variantes intentionnelles de l’ancien détecteur,
notamment les formes autonomes `Snell` et `Descartes`, les pluriels courants et
`sinus`. Les correspondances accidentelles à l’intérieur d’un autre mot ne sont
pas conservées. Pour le diagnostic des protocoles, les termes peuvent partager
un même groupe pédagogique afin de maintenir les quatre familles historiques.
