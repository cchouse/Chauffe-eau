# Pilotage ballon (Home Assistant) — version 0.1.0

Décale l'allumage du **chauffe-eau** en heures creuses pour qu'il finisse de chauffer **juste avant la fin des heures creuses** : moins de pertes de chaleur pendant la nuit, eau chaude assurée le matin. Aucun capteur de température n'est nécessaire : tout se déduit de la **puissance** de la prise. Par défaut : **mode conseil**, la prise n'est pas pilotée.

## Installation
1. Marketplace → « Ajouter grâce à un lien » → `https://github.com/cchouse/Chauffe-eau` (dépôt public) → installer, redémarrer Home Assistant.
2. Ajouter l'intégration « Pilotage ballon » : choisir la **prise** du ballon (interrupteur) et son **capteur de puissance** (W).
3. Ajouter la carte « Pilotage ballon » au tableau de bord (entité « État du ballon »), sur toute la largeur de la vue.
4. « Configurer » : début et fin des heures creuses (22:00 – 06:00 par défaut), marge avant la fin, seuils de puissance.

## Comment ça marche
- **Détection** : la résistance chauffe quand la puissance dépasse 200 W ; le thermostat a coupé quand elle reste sous 50 W pendant 5 min. Les seuils se règlent.
- **Apprentissage** : à chaque chauffe complète (précédée d'au moins 3 h de repos), la durée et l'énergie sont enregistrées. La durée retenue est le **80e centile** des dernières chauffes (prudent), plus 15 % de marge.
- **Repli sûr** : tant que 3 chauffes complètes n'ont pas été observées, la chauffe est conseillée dès le début des heures creuses.
- **Plan** : heure d'allumage = fin des heures creuses − 30 min − durée prévue. L'heure et la raison sont écrites sur la carte, avec les étapes de la nuit (début des heures creuses, allumage, fin de chauffe estimée, fin des heures creuses).
- **Correction quotidienne** : si une chauffe déborde des heures creuses, l'allumage est avancé de 20 min pour les nuits suivantes (jusqu'à 90 min), puis reculé doucement quand la marge revient.
- **Forcer** : « Chauffer maintenant » allume la prise et s'arrête quand le thermostat coupe (ou après 5 h). Si la puissance ne monte pas en 30 min, le ballon était déjà chaud. « Arrêter / annuler » éteint la prise et annule l'allumage prévu pour la nuit.

## Allumage automatique (désactivé par défaut)
Activez l'interrupteur « Allumage automatique » : la prise est alors éteinte au début des heures creuses puis allumée à l'heure calculée, et reste allumée jusqu'à la fin de la chauffe. Garde-fous : arrêt de sécurité d'une chauffe commandée (6 h), jamais de commande répétée en moins de 10 min, rien n'est envoyé si la prise est indisponible. Option « Couper la prise en heures pleines » (désactivée par défaut).

## Limites de cette version
- Testé par des tests automatiques uniquement ; à valider sur votre installation (les seuils de puissance dépendent de votre ballon).
- La puissance est la seule mesure : le volume d'eau chaude tirée n'est pas connu, la durée apprise en tient compte indirectement.
- Pas de gestion solaire (choix volontaire).
