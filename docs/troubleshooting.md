# Troubleshooting — NOVA_CORP

Problèmes rencontrés, diagnostics et résolutions. Divisé en deux sections : problèmes résolus et problèmes ouverts.

---

## Problèmes résolus

### Phase 1 — Switch L3

Aucun incident majeur documenté. Configuration VLAN, trunk, SVIs et SNMP déployés sans problème.

---

### Phase 2 — Routeur R1

Aucun incident majeur documenté. Configuration subinterfaces dot1Q, routage inter-VLAN et SSH déployés sans problème.

---

### Phase 3 — FortiGate VM 7.6.7

#### Problème 1 : Console noire dans GNS3

Symptôme : Console PuTTY complètement noire, aucun output au démarrage.

Diagnostic : Image qcow2 incorrecte (pas une image KVM native). GNS3 annonçait le port console sur 5002, mais l'image réelle mappait sur 5001 (QEMU).

Résolution :
1. Télécharger l'image officielle KVM depuis le portail Fortinet Support : FGT_VM64_KVM-v7.6.7.M-build3704-FORTINET.out.kvm.zip
2. Supprimer l'appliance incorrecte de GNS3
3. Importer via l'appliance fortigate.gns3a du marketplace GNS3
4. GNS3 gère automatiquement le mapping console et crée le disque data empty30G.qcow2
5. Console accessible immédiatement après le démarrage

Leçon : Ne pas télécharger l'image directement. Utiliser le marketplace GNS3 qui valide les appliances.

---

#### Problème 2 : Corruption du système de fichiers FortiGate

Symptôme : Avertissement disk au démarrage ("Disk warning: filesystem nearly full"). Puis comportements aléatoires : DHCP sur port1 perd l'adresse, configurations ne sauvegardent pas, redémarrages imprévisibles.

Cause : Redémarrages forcés répétés pendant les tests (ctrl+C dans la console, power off brutal depuis GNS3). FortiGate n'a pas le temps de flush les caches disque.

Diagnostic : Lors du démarrage, message explicite "Execute disk scan" suggéré par le système.

Résolution :
```
FortiGate console :
execute disk scan 17
```
Attend 2-3 minutes. Disque nettoyé et filesystème restauré. DHCP redevient stable, configurations se sauvegardent normalement.

Vérification post-résolution :
- show system disk status (confirme l'espace disque)
- show system ha status (confirme pas de corruption)

Leçon : Toujours arrêter proprement (shutdown) au lieu de forcer. Ou, sur VM, utiliser les snapshots avant test destructeur.

---

#### Problème 3 : Activation licence bloquée par double-NAT

Symptôme : execute update-now restait en attente indéfinie avec le message "Requesting FortiCare Trial license..."

Cause : Le lab est derrière un double-NAT : GNS3 VM est en NAT (VMnet8) + routeur réseau domestique aussi en NAT. FortiCare server ne peut pas faire de callback entrant pour valider la licence d'évaluation.

Diagnostic : Laissé en attente 10+ minutes. Pas d'erreur explicite, simplement pas de réponse du serveur FortiCare.

Résolution : Utiliser l'activation CLI directe avec identifiants FortiCare :
```
execute vm-license-options account-id <YOUR_ACCOUNT_ID>
execute vm-license-options account-password <YOUR_PASSWORD>
execute vm-license
```
Résultat : License Status: Valid, hostname changé en FGVMEVWVTDI-EMA5 (auto-généré Fortinet).

Vérification : show system info (confirme License Status: Valid)

Alternative : Demander une licence d'évaluation 60 jours directement au support Fortinet.

Leçon : Le double-NAT bloque les callbacks. Pour un lab, utiliser l'activation CLI ou accepter une licence limitée.

---

#### Problème 4 : Limitation 3 policies (vdom-max=3)

Symptôme : Tentative de créer la policy 4. Retour de l'erreur : "edit 4" → error code -4 (policy limit exceeded).

Cause : Licence d'évaluation FortiGate impose vdom-max=3 (maximum 3 policies ou 3 VDOMs).

Résolution : Condenser 6 besoins de sécurité en 3 policies via groupes d'adresses et exploitation du deny-all implicite.

Politique 1 : GRP-INTERNET-ALLOWED (NET-USERS + NET-SERVERS) → Internet (ALL services, log)
Politique 2 : NET-GUESTS → Internet (HTTP/HTTPS/DNS only, log)
Politique 3 : Implicite deny-all

Vérification : show firewall policy (confirme 2 policies explicites + deny implicite)

Note importante : Lors d'un test ultérieur, creation de la policy 4 n'a pas retourné d'erreur -4. La limite de 3 policies pourrait ne pas être appliquée sur cette build spécifique (7.6.7.M-build3704). Test interrompu par disk warning. A valider.

Leçon : Les limitations de licence doivent être contournées au design (groupes d'adresses, deny-all implicite).

---

### Phase 4 — Réseau de supervision

#### Problème 5 : Conflit de sous-réseau (192.168.50.0/24 duplication)

Symptôme : VM Ubuntu de supervision configurée initialement sur 192.168.50.0/24. Résultat : collisions ARP massives, communications erratiques. Ping 192.168.50.1 répond parfois via VLAN 50 (Switch), parfois via Ubuntu VM. Tables ARP incohérentes sur tous les équipements.

Cause : VLAN 50 (Guests) utilisait déjà 192.168.50.0/24 dans GNS3. Ubuntu VM utilisait la même plage sur VMnet2 (réseau supervision). Même si sur deux réseaux différents (GNS3 vs VMware), l'OS Windows de la machine physique voyait deux réseaux avec la même adresse, créant des collisions.

Diagnostic :
- arp -a sur Windows : même IP (192.168.50.x) avec MAC addresses différentes
- tcpdump sur eth2 (GNS3 VM) : ARP requests/replies entrecroisées
- ping 192.168.50.1 : latence incohérente, perte de paquets aléatoire

Résolution : Migrer le réseau de supervision de 192.168.50.0/24 vers 192.168.60.0/24. Modifications appliquées sur :

1. VMnet2 dans VMware Workstation (onglet Edit → Virtual Network Editor)
   - Désactiver DHCP
   - Définir subnet 192.168.60.0, netmask 255.255.255.0
   - Gateway 192.168.60.1

2. eth2 de la GNS3 VM (via Netplan)
   - Fichier /etc/netplan/90-gns3vm-static.yaml
   - Ajouter eth2 avec adresse 192.168.60.128/24

3. ens33 de l'Ubuntu VM (via NetworkManager)
   - Fichier /etc/netplan/00-installer-config.yaml
   - Changer adresse réseau à 192.168.60.x/24
   - Appliquer : netplan apply

4. Route statique FortiGate
   - config router static
   - edit N
   - set dst 192.168.60.0/24
   - set gateway 10.0.0.2
   - next
   - end

Vérification post-résolution :
- arp -a : addresses uniques pour chaque IP
- ping 192.168.60.128 : latence stable, 0% perte
- Graylog accessible sur http://192.168.60.x:9000

Impact : Supervision stable, Graylog/OpenSearch/Zabbix/LibreNMS tous opérationnels.

Leçon : Toujours planifier l'adressage IP de TOUS les réseaux au démarrage (GNS3, VMware, supervision). Éviter les doublons même sur réseaux distincts.

---

## Problèmes ouverts

### Bug A : Asymmetric bridge (GNS3 Cloud node / ubridge)

Sévérité : Moyen - Workaround stable actif

Symptôme : Depuis la GNS3 VM, les paquets sortants passent via eth1 (lié au Cloud node GNS3) et atteignent l'extérieur. Mais les réponses ARP/IP de retour n'arrivent jamais sur eth1. Confirmé par tcpdump :
- eth1 sortant : ARP requests visibles
- eth1 entrant : AUCUNE ARP reply

Le comportement survit aux reboots complets (VM GNS3 + GNS3 application).

Diagnostic détaillé :

1. Capture tcpdump sur eth1 :
   tcpdump -i eth1 -n arp
   Résultat : ARP requests sortants visibles, zéro ARP replies entrants

2. Vérification des instances ubridge (le bridge utilisateur de GNS3) :
   ps aux | grep ubridge
   Résultat : 4 instances distinctes, sur ports séparés (4008, 4128, 3904, 4400)

Chaque instance ubridge crée un bridge virtuel isolé. Les paquets entrent dans une instance et ne peuvent pas atteindre une autre.

3. Causes éliminées (non le problème) :
   - Tables de routage : correctes sur tous les équipements (R1, Switch, FortiGate, Windows)
   - Cache ARP : vidé manuellement (arp -d *), bug reproduit à chaque reboot
   - Santé VMnet1 : bridge VMware opérationnel par ailleurs (VMs Windows communiquent)
   - Windows Firewall : désactivé entièrement pour test, bug persistant
   - Driver Npcap : réinstallé, aucun changement

Cause racine confirmée : Architecture multi-instance de ubridge dans GNS3. Quand plusieurs Cloud nodes sont attachés à une même GNS3 VM, chaque node crée sa propre instance ubridge. Ces instances ne se parlent pas — elles forment des îlots isolés.

Workaround actif : Tout l'accès au FortiGate se fait via le lien interne 10.0.0.0/30 (R1 Gi2/0 ↔ FortiGate port2). Ce lien reste entièrement dans GNS3, zéro implication du Cloud node. SSH activé sur FortiGate port2 (allowaccess ping ssh).

Supervision (SIEM, monitoring) déployée dans VMware directement (VMnet2), sans dépendre d'aucun Cloud node GNS3.

Résolution définitive (non testée) : Remplacer le Cloud node GNS3 par un bridge VMware direct vers une interface réseau physique dédiée. S'assurer qu'une seule instance ubridge est active pour ce bridge.

---

### Bug B : Syslog R1 → FortiGate → SIEM (non résolu)

Sévérité : Élevé - Télémétrie réseau R1 n'atteint pas le SIEM

Symptôme : R1 envoie ses logs syslog à 10.0.0.1:514 (IP de port2 du FortiGate). Les paquets arrivent bien sur port2 (confirmé par sniffer FortiGate). Mais ne sortent jamais vers syslog-ng à 192.168.66.128:514.

Diagnostic détaillé (FortiGate) :

1. Sniffer sur port2 (entrée) :
   diagnose sniffer packet port2 "udp port 514" 4
   Résultat : Paquets syslog de 10.0.0.2 visibles, source :10.0.0.2 dest :10.0.0.1

2. Sniffer sur port1 (sortie) :
   diagnose sniffer packet port1 "udp port 514" 4
   Résultat : AUCUN paquet correspondant

3. Debug flow complet :
   diagnose debug flow filter addr 10.0.0.2
   diagnose debug flow show function-name enable
   diagnose debug enable

   Pour chaque paquet syslog 10.0.0.2 → 192.168.66.128:514 :
   - Nouvelle session créée (session-00000131, 132, 134...) : OK
   - Route trouvée (dst 192.168.66.128, via port1) : OK
   - Trace s'arrête après __vf_ip_route_input_rcu : BLOQUE
   - Aucune ligne policy_id, accept ou deny n'apparaît jamais
   - Pas de "NEW_SESSION" qui se termine par "accept" ou "deny"

Conclusion : Le drop est interne au FortiGate, AVANT le moteur de policy. Les couches inférieures (RPF anti-spoofing, kernel local-in handler, ou RPF) bloquent le paquet avant qu'il atteigne le moteur de policy.

Tentatives de résolution (toutes échouées, car elles agissent sur la couche policy) :

1. Créer un objet service SYSLOG (TCP+UDP/514)
2. Créer un objet HOST-R1 (10.0.0.2/32) et l'ajouter à GRP-INTERNET-ALLOWED
3. Créer une local-in-policy dédiée (port2 entrante → port1 sortante)
4. Réordonnancer les policies
5. Vérifier les routes asymétriques (route 192.168.60.0/24 via 10.0.0.2)

Aucune n'a fonctionné car elles traitent toutes le symptôme de policy — une couche que le paquet n'atteint jamais.

Piste de résolution (non testée) :

Changer la destination syslog sur R1 pour pointer directement vers syslog-ng, au lieu de l'IP du FortiGate :

Sur R1 :
no logging host 10.0.0.1
logging host 192.168.66.128

Dans ce cas, le FortiGate voit le paquet 10.0.0.2 → 192.168.66.128:514. Cette destination n'est pas sa propre IP. Il le traite comme du trafic à forwarder et l'évalue contre ses policies. Le paquet passera alors normalement.

Prérequis : Confirmer que 192.168.66.128 est bien l'adresse IP actuelle de la GNS3 VM.

Impact actuel : Les logs de R1 n'atteignent pas Graylog. Mais les équipements FortiGate eux-mêmes (dont le syslog pointe vers le SIEM via VMnet2) ne sont pas affectés. La supervision SNMP (Zabbix/LibreNMS) fonctionne normalement.

---

## Résumé

Problèmes résolus : 5 (Phase 3 FortiGate × 4, Phase 4 Supervision × 1)
Problèmes ouverts : 2 (Bug A workaround, Bug B investigation)

Total documenté : 7 problèmes

Note : Cette liste couvre les incidents explicitement documentés dans le journal de déploiement. Tu mentionnes environ 15 problèmes résolus. Les autres peuvent être ajoutés à cette page au fur et à mesure.
