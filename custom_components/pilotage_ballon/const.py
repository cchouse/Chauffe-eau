"""Constantes de l'intégration Pilotage ballon."""
DOMAIN = "pilotage_ballon"
VERSION = "0.1.0"
URL_CARTE = "/pilotage_ballon/pilotage-ballon-card.js"

CONF_PRISE = "prise"            # interrupteur de la prise (ex. Tapo)
CONF_PUISSANCE = "puissance"    # capteur de puissance en W de cette prise
CONF_NOTIF = "notification"     # entité notify (facultatif)

OPTIONS_DEFAUT = {
    "hc_debut": "22:00:00",     # début des heures creuses
    "hc_fin": "06:00:00",       # fin des heures creuses
    "marge_fin": 30,            # minutes : le ballon doit être chaud avant la fin des heures creuses
    "marge_duree": 1.15,        # marge de prudence sur la durée de chauffe apprise
    "duree_defaut": 240,        # minutes : durée supposée tant que rien n'est appris
    "seuil_marche": 200,        # W : au-dessus, la résistance chauffe
    "seuil_arret": 50,          # W : en dessous (5 min), le thermostat a coupé
    "marche_max": 360,          # minutes : arrêt de sécurité d'une chauffe commandée
    "couper_hp": False,         # couper la prise en heures pleines (sinon on n'y touche pas)
}

TICK_S = 60
ECHANTILLON_S = 300
HISTO_MAX = 288                 # 24 h à 5 min
JOURNAL_MAX = 30
DEBOUNCE_MARCHE_S = 120         # puissance haute depuis 2 min = début de chauffe
DEBOUNCE_ARRET_S = 300          # puissance basse depuis 5 min = fin de chauffe
ATTENTE_PUISSANCE_S = 1800      # forçage : si la puissance ne monte pas en 30 min, le ballon est déjà chaud
FORCE_MAX_S = 5 * 3600
CYCLES_FIABLES = 3              # nombre de chauffes complètes observées avant de décaler l'allumage
