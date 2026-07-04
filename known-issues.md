# Problèmes rencontrés et diagnostics

Ce fichier tient le journal des problèmes croisés dans NOVA_CORP, résolus ou non. L'idée n'est pas de cacher ce qui coince mais de garder une trace du raisonnement : les symptômes observés, ce que j'ai testé, ce que ça a éliminé. Un labo qui documente honnêtement ses impasses est plus utile qu'un labo qui prétend que tout a marché du premier coup.

Les adresses citées sont celles du labo, en plages privées. Rien de sensible n'est exposé.

## Routage syslog R1 vers le SIEM — toujours ouvert

C'est le problème le plus tenace du labo. Les logs de R1 devraient remonter jusqu'au conteneur syslog-ng en transitant par le FortiGate, selon ce chemin :

```
R1 (10.0.0.2) → FortiGate port2 (10.0.0.1) → port1 (WAN/NAT) → syslog-ng (192.168.66.128:514)
```

Sur le papier tout est en place, et la connectivité de base répond. Le lien R1 ↔ FortiGate est bon : ping à 100 %, ARP résolue, l'aller-retour est complet au sniffer. Le FortiGate atteint Internet sans souci. Le conteneur syslog-ng tourne et écoute bien sur `0.0.0.0:514` en UDP et TCP. Et quand un paquet syslog arrive, le FortiGate lui trouve bien une route vers `port1`.

Et pourtant, rien ne sort.

En regardant de près un paquet syslog `10.0.0.2:57556 → 192.168.66.128:514`, voici ce qui se passe : il arrive bien sur `port2` (le sniffer le confirme, de façon reproductible), une session est allouée, une route est trouvée — mais aucune ligne `out` vers `port1` n'apparaît jamais. Ni dans le sniffer FortiOS, ni dans une capture Wireshark faite indépendamment sur le câble Cloud1 ↔ FortiGate. Le paquet entre et disparaît.

Le sniffer est sans ambiguïté sur ce point :

```
port2 in 10.0.0.2.57556 -> 192.168.66.128.514: udp 110
port2 in 10.0.0.2.57556 -> 192.168.66.128.514: udp 108
port2 in 10.0.0.2.57556 -> 192.168.66.128.514: udp 112
port2 in 10.0.0.2.57556 -> 192.168.66.128.514: udp 82
```

Quatre paquets entrent, zéro ne ressort.

Le détail qui oriente tout le reste : le trace `diagnose debug flow` s'arrête systématiquement juste après le routage, sans jamais afficher de décision de politique — pas de `policy_id`, pas d'`accept` ni de `deny`. Même comportement sur huit paquets d'affilée. Autrement dit, le paquet semble intercepté *avant* d'atteindre le moteur de règles normal.

J'ai testé plusieurs pistes sans que ça débloque quoi que ce soit. J'ai d'abord soupçonné que le service syslog manquait dans la règle, donc j'ai créé un objet service `SYSLOG` (TCP et UDP sur 514) que j'ai ajouté à `LAN-to-Internet` : sans effet. J'ai ensuite pensé que R1 lui-même n'était pas couvert par la source de la règle, donc j'ai créé un objet `HOST-R1` (`10.0.0.2/32`) ajouté au groupe `GRP-INTERNET-ALLOWED` : toujours rien. J'ai aussi essayé une `local-in-policy` pour accepter explicitement le trafic entrant, puis vérifié l'ordre d'évaluation des règles — mais l'ordre ne peut pas être en cause, la règle voisine pointe vers une autre interface de destination et ne peut pas absorber ce paquet.

La config, une fois vérifiée, est correcte :

```
config firewall address
    edit "HOST-R1"
        set subnet 10.0.0.2 255.255.255.255
    next
end

config firewall policy
    edit 1
        set name "LAN-to-Internet"
        set srcintf "port2"
        set dstintf "port1"
        set action accept
        set srcaddr "GRP-INTERNET-ALLOWED"
        set dstaddr "all"
        set service "HTTP" "HTTPS" "DNS" "NTP" "SYSLOG"
        set logtraffic all
        set nat enable
    next
end
```

À ce stade, mon hypothèse de travail est que le paquet est capté par un mécanisme FortiOS en amont du moteur de politique, ce qui expliquerait pourquoi le trace de flux ne montre jamais de décision. Les pistes à creuser : un traitement de session ou local, un effet de bord du double-NAT du labo, ou une conséquence de la licence invalide qui plafonne le nombre de policies, d'interfaces et de routes. Le diagnostic continue.

## Bridge asymétrique dans GNS3 — contourné

Le nœud Cloud de GNS3, qui relie `eth1`/VMnet au FortiGate, bridge le trafic dans un seul sens. Les requêtes ARP partent bien de la GNS3 VM vers le FortiGate — le sniffer les voit — mais les réponses ne reviennent jamais vers `eth1`, ce que `tcpdump` confirme. Le bug est structurel : il survit à un redémarrage complet.

J'ai tenté plusieurs choses : forcer `noPromisc=FALSE` dans le `.vmx`, recréer le nœud Cloud de zéro (deux fois), relancer le processus `ubridge`, fouiller du côté du mode promiscuous. Rien n'y a fait.

Le contournement retenu est simple et fiable : passer par le lien interne `10.0.0.0/30` de R1 pour joindre le FortiGate. C'est ce lien qui porte aujourd'hui tout le trafic LAN vers le pare-feu, et il fonctionne parfaitement.

## Conflit de sous-réseau sur la supervision — résolu

Au départ, le réseau de supervision utilisait `192.168.50.0/24` — le même sous-réseau que le VLAN 50 (Guests) géré par R1. Résultat : des conflits ARP.

Je l'ai migré vers `192.168.60.0/24`, en propageant le changement sur les quatre composants concernés : le Virtual Network Editor de VMware (VMnet2), l'interface `eth2` de la GNS3 VM via Netplan, l'interface `ens33` de la VM Ubuntu, et la route statique correspondante sur le FortiGate.

## Corruption disque sur le FortiGate — résolue

Un `execute disk scan 17` a réglé l'alerte de corruption. Effet de bord bienvenu : le DHCP sur `port1`, qui affichait `0.0.0.0`, s'est remis à fonctionner dans la foulée.

## Licence FortiGate — bloquée

L'activation de la licence d'évaluation via `execute vm-license` reste coincée sur « Requesting FortiCare Trial license ». Le double-NAT du labo bloque très probablement le flux HTTPS d'enregistrement. Cela dit, même une licence d'évaluation valide garderait la limite dure de trois policies, trois interfaces et trois routes — c'est donc une contrainte que j'assume dans l'architecture plutôt qu'un blocage à lever absolument.
