# Architecture NOVA_CORP

## Vue d'ensemble

NOVA_CORP simule l'infrastructure réseau d'une PME de 20 à 50 employés. L'objectif est de reproduire une architecture réaliste avec les contraintes d'un home lab sur machine unique : budget RAM limité (16 Go), un seul hôte physique, et des équipements émulés.

---

## Plan d'adressage

| Segment | VLAN | Sous-réseau | Passerelle (SVI) | Rôle |
|---|---|---|---|---|
| Users | 10 | 192.168.10.0/24 | 192.168.10.254 | Postes utilisateurs |
| Servers | 20 | 192.168.20.0/24 | 192.168.20.254 | AD, serveurs applicatifs |
| Management | 30 | 192.168.30.0/24 | 192.168.30.254 | Administration réseau |
| DMZ | 40 | 192.168.40.0/24 | 192.168.40.254 | Services exposés |
| Guests | 50 | 192.168.50.0/24 | 192.168.50.254 | Réseau invités |
| Supervision | — | 192.168.60.0/24 | — | SIEM, monitoring (hors GNS3) |
| Lien R1↔FGT | — | 10.0.0.0/30 | — | WAN interne lab |

> **Note :** Le réseau de supervision a été migré de 192.168.50.0/24 (conflit VLAN 50) vers 192.168.60.0/24. Correction appliquée sur VMnet2, eth2 GNS3 VM (Netplan), Ubuntu VM (ens33), et route statique FortiGate.

---

## Choix d'architecture

### Routage inter-VLAN sur R1

Le routage inter-VLAN est assuré par R1 (router-on-a-stick) via des sous-interfaces dot1Q sur FastEthernet0/0, plutôt que sur le switch L3. Ce choix reflète une topologie courante en PME et permet de démontrer la configuration des subinterfaces Cisco.

```
R1 Fa0/0.10 — encapsulation dot1Q 10 — 192.168.10.1/24
R1 Fa0/0.20 — encapsulation dot1Q 20 — 192.168.20.1/24
R1 Fa0/0.30 — encapsulation dot1Q 30 — 192.168.30.1/24
R1 Fa0/0.40 — encapsulation dot1Q 40 — 192.168.40.1/24
R1 Fa0/0.50 — encapsulation dot1Q 50 — 192.168.50.1/24
R1 Gi2/0    — 10.0.0.2/30 (lien vers FortiGate)
```

### FortiGate en passerelle Internet uniquement

Le FortiGate ne fait pas de routage inter-VLAN. Il assure uniquement la sortie Internet et le filtrage périmétrique. Ce découplage simplifie la topologie et respecte le principe de séparation des rôles.

### 3 policies condensées (contrainte licence évaluation)

La licence d'évaluation FortiGate impose une limite de 3 policies (vdom-max=3). Six besoins de sécurité ont été couverts en 3 règles grâce à :
- Des groupes d'adresses (`GRP-INTERNET-ALLOWED` = NET-USERS + NET-SERVERS)
- L'exploitation du deny-all implicite
- Une politique distincte et restrictive pour les invités (HTTP/HTTPS/DNS uniquement)

```
Policy 1 : GRP-INTERNET-ALLOWED → Internet (ALL services, log)
Policy 2 : NET-GUESTS           → Internet (HTTP/HTTPS/DNS only, log)
Policy 3 : [implicite]          → deny all
```

> **Découverte importante :** lors des tests de la 4e policy, FortiGate n'a PAS retourné d'erreur. La limite de 3 policies pourrait ne pas être appliquée sur cette build spécifique. Tests interrompus par un disk warning — à valider.

### Supervision hors GNS3

Les VM de supervision (Graylog/OpenSearch, Zabbix, LibreNMS) tournent dans VMware directement, sur VMnet2 (192.168.60.0/24). Elles n'utilisent aucun Cloud node GNS3 — décision prise suite au Bug A (voir `known-issues.md`).

---

## Stack logicielle

| Outil | Rôle | Déploiement |
|---|---|---|
| Cisco IOSv | Routeur R1 | GNS3 |
| Cisco IOSvL2 | Switch L3 | GNS3 |
| FortiGate-VM64-KVM 7.6.7 | Pare-feu périmétrique | GNS3 |
| syslog-ng | Collecte syslog (R1, FortiGate) | Docker — GNS3 VM |
| Graylog + OpenSearch | SIEM / indexation | Docker — Ubuntu VM |
| Zabbix | Supervision SNMP/agent | Docker — Ubuntu VM |
| LibreNMS | Découverte et graphes réseau | Docker — Ubuntu VM |
| Windows Server 2022 | Active Directory (novaenterprise.com) | VMware — WIN-FP37U0DSQU8 |
| Windows 11 | Poste client PROD01 | VMware |

---

## Chemins de collecte syslog

Deux chemins coexistent selon la source :

**Hôtes (AD, PROD01)** → agents Wazuh ou syslog direct → Ubuntu VM (Graylog) via VMnet2. Ce chemin ne passe pas par FortiGate.

**Équipements réseau (R1, FortiGate)** → syslog UDP/514 → GNS3 VM (syslog-ng) → Graylog. Ce chemin est actuellement bloqué par le Bug B pour R1 (voir `known-issues.md`).

---

## Accès à FortiGate

Suite au Bug A (bridge asymétrique), le seul chemin fonctionnel vers FortiGate est le lien interne `10.0.0.0/30` via R1. SSH est activé sur port2 (`set allowaccess ping ssh`).

- Accès HTTPS : `https://10.0.0.1` (via SSH tunnel ou depuis R1)
- Accès SSH : `ssh admin@10.0.0.1` (port2, depuis R1)
