# Architecture

Ce document explique les choix d'architecture du labo et la logique derrière. Il complète le [README](../README.md) et le [journal des problèmes](known-issues.md).

## L'idée de départ

NOVA_CORP simule une PME d'une vingtaine à une cinquantaine de postes. J'ai cherché le réalisme opérationnel plutôt que l'exhaustivité : chaque décision correspond à ce qu'une petite structure ferait vraiment, avec ses arbitrages entre coût, complexité et sécurité. Ce n'est pas une maquette pour cocher des cases, c'est un réseau qui pourrait tourner.

## Qui fait quoi entre R1 et le FortiGate

La décision structurante du labo tient en une phrase : c'est R1 qui route entre les VLANs, pas le FortiGate.

R1 porte tous les VLANs sur ses sous-interfaces `dot1Q`, de `Fa0/0.10` à `Fa0/0.50`, et sert de passerelle par défaut (`.254`) à chacun. Quand un poste du VLAN Users veut joindre un serveur du VLAN Servers, le trafic monte à R1, redescend vers l'autre sous-interface, et repart — sans jamais toucher le pare-feu.

Le FortiGate, de son côté, tient uniquement la frontière Internet. Tout ce qui sort vers le WAN passe par lui : le trafic arrive sur `port2` (`10.0.0.1`) par le lien `/30`, et ressort sur `port1` après NAT. Mais il ne voit pas le trafic interne.

Ce partage — le routeur gère l'intérieur, le pare-feu garde la porte — est une architecture PME très courante. Je l'ai choisie en connaissance de cause, et elle a un avantage concret : elle libère des emplacements de politique sur un FortiGate dont la licence est justement très limitée.

Le détail de l'adressage :

- `Fa0/0.10`, VLAN 10, `192.168.10.0/24` — Users
- `Fa0/0.20`, VLAN 20, `192.168.20.0/24` — Servers
- `Fa0/0.30`, VLAN 30, `192.168.30.0/24` — Management
- `Fa0/0.40`, VLAN 40, `192.168.40.0/24` — DMZ
- `Fa0/0.50`, VLAN 50, `192.168.50.0/24` — Guests
- `Gi2/0`, lien `/30`, `10.0.0.2` vers le FortiGate

## Le chemin du trafic

Pour sortir vers Internet, un poste emprunte ce trajet : il passe par sa passerelle sur R1, R1 route vers son interface `Gi2/0` (`10.0.0.2`), atteint le FortiGate sur `port2` (`10.0.0.1`), qui NAT et envoie vers Internet par `port1`.

Pour le trafic entre VLANs, c'est plus court : le poste passe par R1, qui route directement d'une sous-interface à l'autre. Le pare-feu n'intervient pas.

Cette distinction a une conséquence pratique importante : une règle FortiGate qui prétendrait filtrer, disons, Users vers Servers ne servirait à rien ici, puisque ce trafic ne remonte jamais jusqu'au pare-feu. C'est le genre de subtilité qu'on ne voit qu'en traçant réellement le chemin des paquets.

## Les politiques FortiGate sous contrainte

La licence invalide plafonne le FortiGate à trois politiques, trois interfaces et trois routes. Il a donc fallu faire tenir six besoins de sécurité initiaux dans trois règles.

La solution passe par les groupes d'adresses. Une première règle, `LAN-to-Internet`, autorise le groupe `GRP-INTERNET-ALLOWED` (qui rassemble les réseaux Users et Servers, plus l'hôte R1) à sortir sur Internet avec les services HTTP, HTTPS, DNS, NTP et syslog, NAT activé. Une deuxième règle donne aux invités un accès Internet volontairement restreint à HTTP, HTTPS et DNS. Le reste — notamment l'isolation des invités vis-à-vis du LAN — est assuré par le deny-all implicite du FortiGate.

Passer de six règles à trois sans perdre l'intention de sécurité, en s'appuyant sur les groupes et le comportement par défaut du pare-feu, est un bon exercice d'optimisation sous contrainte. C'est aussi représentatif : dans la vraie vie, on compose souvent avec des limites qu'on n'a pas choisies.

## Supervision et logs

La chaîne d'observabilité tourne sur des VMs Ubuntu 22.04, sur un réseau dédié (`192.168.60.0/24`) séparé du LAN de production. syslog-ng collecte et route les logs réseau depuis un conteneur Docker qui écoute sur `0.0.0.0:514`. Graylog, adossé à OpenSearch, indexe et permet la recherche. Zabbix couvre les métriques et l'alerting, LibreNMS la cartographie SNMP.

La remontée des logs de R1 vers cette chaîne n'est pas encore fonctionnelle — le blocage se situe au niveau du FortiGate, et il est décrit en détail dans le [journal des problèmes](known-issues.md).

## L'hébergement

Tout tient sur une machine Windows, via VMware Workstation Pro en version gratuite. La GNS3 VM (`192.168.66.128`) héberge R1, le switch L3 et le FortiGate VM 7.6.7. Une VM Ubuntu porte les services de supervision. Des réseaux virtuels VMware distincts séparent la production de la supervision.

Un bug de bridge asymétrique dans le nœud Cloud de GNS3 m'a obligé à contourner : l'accès au FortiGate passe par le lien interne `10.0.0.0/30` de R1. Là encore, les détails sont dans le journal des problèmes.

## Les décisions en résumé

Router l'inter-VLAN sur R1 et laisser le FortiGate en simple passerelle Internet, c'est réaliste pour une PME et ça économise des emplacements de politique sur un pare-feu contraint. Condenser en trois règles via les groupes d'adresses permet de vivre avec la limite de licence sans sacrifier la logique de sécurité. Isoler le réseau de supervision sur son propre sous-réseau sépare le trafic de gestion de la production et évite le conflit qui existait avec le VLAN Guests. Et passer par le lien `/30` interne offre un chemin fiable vers le FortiGate malgré le bug de GNS3.
