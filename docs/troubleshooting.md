# Problèmes connus — NOVA_CORP

---

## Bug A — Asymmetric bridge (GNS3 Cloud node / ubridge)

**Sévérité :** Moyen — workaround stable actif
**Statut :** Workaround actif, cause racine documentée

### Symptôme

Depuis la GNS3 VM, les paquets sortants passent via `eth1` (lié au Cloud node GNS3) et atteignent le FortiGate. Mais les réponses ARP/IP de retour n'arrivent jamais sur `eth1`. Le comportement survit aux reboots complets.

### Diagnostic

```bash
# Sur la GNS3 VM — capture sur eth1
tcpdump -i eth1 -n arp
# Résultat : ARP requests visibles en sortie, aucune ARP reply en entrée

# Identification des instances ubridge
ps aux | grep ubridge
# Résultat : 4 instances distinctes sur ports 4008, 4128, 3904, 4400
```

Chaque instance ubridge crée un bridge virtuel isolé. Les paquets entrent dans une instance et ne peuvent pas atteindre les autres. L'architecture multi-Cloud-node de GNS3 crée structurellement cette asymétrie.

### Causes éliminées

- Tables de routage (correctes sur tous les équipements)
- Cache ARP (vidé, bug reproduit à chaque reboot)
- Santé VMnet1 (bridge VMware fonctionnel par ailleurs)
- Règles Windows Firewall (désactivées pour test, bug persistant)
- Driver Npcap (réinstallé, aucun changement)

### Workaround actif

Tout l'accès au FortiGate se fait via le lien interne `10.0.0.0/30` (R1 Gi2/0 ↔ FortiGate port2). Ce lien reste entièrement dans GNS3 — aucun Cloud node impliqué. SSH est activé sur port2.

La supervision (SIEM, monitoring) est déployée dans VMware directement (VMnet2), sans dépendre d'aucun Cloud node GNS3.

### Résolution définitive (non encore testée)

Remplacer le Cloud node GNS3 par un bridge VMware direct vers une interface réseau dédiée, en s'assurant qu'une seule instance ubridge est active pour ce bridge.

---

## Bug B — Syslog R1 → FortiGate → SIEM (non résolu)

**Sévérité :** Élevé — la télémétrie réseau de R1 n'atteint pas le SIEM
**Statut :** Non résolu — piste de résolution identifiée, non testée

### Symptôme

R1 envoie ses logs syslog à `10.0.0.1:514` (IP de port2 du FortiGate). Les paquets arrivent bien sur port2 (confirmé par sniffer), mais ne sortent jamais vers syslog-ng à `192.168.66.128:514`.

### Diagnostic complet

```
# Sur FortiGate — sniffer
diagnose sniffer packet port2 "udp port 514" 4
# Résultat : paquets syslog de 10.0.0.2 visibles ✅

diagnose sniffer packet port1 "udp port 514" 4
# Résultat : aucun paquet correspondant ❌

# Debug flow
diagnose debug flow filter addr 10.0.0.2
diagnose debug flow show function-name enable
diagnose debug enable
# Résultat pour chaque paquet :
#   - Nouvelle session créée (session-00000131, 132...) ✅
#   - Route trouvée via port1 ✅
#   - Trace s'arrête après __vf_ip_route_input_rcu ❌
#   - Aucune ligne policy_id / accept / deny ❌
```

### Cause probable

Le trafic à destination de `10.0.0.1` (IP propre de port2) est intercepté par FortiOS **avant** le moteur de policy. FortiOS traite ce trafic comme du trafic local-in (destiné à lui-même), pas comme du trafic à forwarder. Le mécanisme RPF (Reverse Path Forwarding) ou le kernel local-in handler bloque le paquet avant qu'il atteigne la couche de policy.

### Actions déjà tentées (toutes inefficaces)

Toutes ces actions agissent sur le moteur de policy — une couche que le paquet n'atteint jamais.

- Création d'un objet service `SYSLOG` (TCP+UDP/514)
- Ajout de `HOST-R1` (10.0.0.2/32) dans `GRP-INTERNET-ALLOWED`
- Création d'une `local-in-policy` port2 → port1
- Réordonnancement des policies
- Vérification des routes asymétriques

### Piste de résolution (à tester)

Changer la destination syslog sur R1 pour pointer directement vers syslog-ng, sans passer par l'IP du FortiGate :

```
! Sur R1
no logging host 10.0.0.1
logging host 192.168.66.128
```

Dans ce cas, le FortiGate voit le paquet `10.0.0.2 → 192.168.66.128:514` — une destination qui n'est pas sa propre IP. Il le traite comme du trafic à forwarder et l'évalue contre ses policies.

**Prérequis :** vérifier que 192.168.66.128 est bien l'IP courante de la GNS3 VM, et que la policy FortiGate couvre ce flux (port2 → port1, dst 192.168.66.128, service SYSLOG).

### Impact actuel

Les logs de R1 n'atteignent pas Graylog. Les équipements FortiGate eux-mêmes (dont la config syslog pointe vers le SIEM via VMnet2) ne sont pas affectés par ce bug. La supervision SNMP (Zabbix/LibreNMS) fonctionne normalement via un autre chemin.
