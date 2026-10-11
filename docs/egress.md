# Terraform Egress-Verwaltung

Stand 11.10.2026: Cilium Egress Gateway und Terraform-Verwaltung sind aktiv.
Alle vier Quell-IPs wurden nach Aktivierung der Rancher-Projekt-Isolation an einem
externen LAN-Empfänger nachgewiesen; `terraform plan` meldet keine Änderungen.
Worker 1 hat vier vCPU, Rancher und OpenBao sind nach dem VM-Umzug wieder erreichbar.

Jede Deklaration unter `tenants/` reserviert dauerhaft zwei `egress_ips`: je eine
für `worker1` und `worker2`. `scripts/new-tenant.py` vergibt die ersten zwei freien
Adressen aus `192.168.1.200–220` und schreibt sie in die neue Deklaration. Bestehende
Mandanten werden nicht neu nummeriert. Der Pool reicht für zehn Mandanten; eine
Adresse bleibt übrig. Eine lokale Dateisperre verhindert parallele Doppelvergabe
durch dieses Werkzeug. Git-Änderungen anderer Arbeitskopien müssen vor Apply
zusammengeführt und geprüft werden. Terraform weist Doppelbelegungen zurück.

| Mandant | Worker 1 | Worker 2 |
| --- | --- | --- |
| A | 192.168.1.200 | 192.168.1.201 |
| B | 192.168.1.202 | 192.168.1.203 |

`terraform/egress.tf` verwaltet die Reservierungsprüfung, vier persistente
Node-Adressen und vier CiliumEgressGatewayPolicies im gemeinsamen administrativen
State. Neue Mandanten erhalten automatisch zwei weitere Adressen und Policies.
Die Gateway-Zuordnung steht in `config/egress-gateways.json`.

Terraform richtet die Adressen per SSH über den vorhandenen Operator-Schlüssel
ein. Voraussetzung sind bekannte SSH-Hostschlüssel, Benutzer `ansible`, sudo ohne
Passwort sowie NetworkManager, Python 3 und arping auf den Gateways. Private
Schlüssel werden nicht in Terraform oder Git gespeichert. Der Helfer prüft Host,
primäre Adresse, aktives Netzwerkprofil und ARP-Konflikte; er ergänzt ausschließlich
reservierte `/32`-Adressen. Änderungen am selben Node sind über eine Dateisperre
serialisiert. Ein Eigentumsnachweis unter `/var/lib/afi-tenant-egress` schützt
fremde Adressen vor Übernahme oder Entfernung. Policies werden erst nach erfolgreicher
Adresskonfiguration angelegt und vor deren Entfernung gelöscht.

Die SSH-Provisioner werden bei Anlage beziehungsweise Ersetzung ausgeführt;
Terraform erkennt manuelle Änderungen am NetworkManager-Profil nicht automatisch.
`gateway-address.py --check` prüft die Bindung aus `AFI_EGRESS_BINDING` lesend.
Bei festgestelltem Drift kann die betroffene `terraform_data.egress_address`
gezielt mit `-replace` wiederhergestellt werden; Plan vorher prüfen, da dabei die
Adresse kurz entfernt und neu angelegt wird. Cilium-Policies werden regulär vom
Kubernetes-Provider auf Drift geprüft.

Die clusterweite Aktivierung von Cilium Egress Gateway ist eine Plattform-
Voraussetzung: Das CRD muss vor einem vollständigen Terraform-Plan vorhanden sein.
Fleet/Ansible dürfen keine mandantenspezifischen Egress-Policies oder Node-Adressen
parallel verwalten. Mandantenspezifische Policies und Adressen haben ausschließlich Terraform als Eigentümer.

Worker-1-Pods verwenden das Gateway auf Worker 1; alle übrigen Quell-Nodes das
Gateway auf Worker 2. Selektiert wird das geschützte Rancher-Projektlabel über Ciliums
Namespace-Identität `io.cilium.k8s.namespace.labels.field.cattle.io/projectId`.
Damit erhalten auch zusätzliche Self-Service-Namespaces automatisch die Mandanten-IP. Bei Ausfall eines Workers müssen Anwendungen auf dem
anderen Worker neu gestartet werden; die zweite IP muss extern ebenfalls erlaubt
sein. Bestehende Verbindungen und die ursprüngliche IP werden nicht übernommen.
HostNetwork-Pods und die Verzögerung der Policy-Aktivierung bei neuen Pods bleiben
gesonderte Sicherheitsgrenzen.

## Rancher-Projekt-Isolation

Cluster 2 (`c-44q9v`) ist importiert. Die Plattformadministration aktiviert
`spec.enableNetworkPolicy: true` am `clusters.management.cattle.io`-Objekt im
Rancher-Management-Cluster. Der Betreiber hat dies am 11.10.2026 gesetzt;
`status.appliedEnableNetworkPolicy` und die Networking-Annotation sind ebenfalls true.
Das Provisioning-Objekt ist bei diesem importierten Cluster nicht die maßgebliche Quelle.

Rancher erzeugt `np-default` und `hn-nodes` in den Projekt-Namespaces. Terraform ordnet die Basis-Namespaces zu; zusätzliche Namespaces können Admins und
Developers im eigenen Projekt erstellen. Rancher verwaltet die
zugehörigen NetworkPolicies. Terraform erzeugt deshalb keine konkurrierenden Kopien.
`np-default` erlaubt Ingress aus dem eigenen Projekt und dem System-Projekt.
Nicht zugeordnete Infrastruktur-Namespaces werden dadurch nicht automatisch isoliert.
Dies ist keine Egress-Firewall; die EgressGatewayPolicy bestimmt die Quell-IP.
Privilegierte/HostNetwork-Workloads benötigen zusätzliche Pod-Security-Grenzen.

Nachweise und wiederholbare Tests:

- `scripts/verify-project-isolation.py`: 16 erlaubte/gesperrte Verbindungen zwischen
  dev/test von A/B über beide Worker, Ergebnis `tests/results/project-isolation-cluster2.json`.
- `scripts/verify-rancher-access.py`: echte OIDC-Anmeldung mit PKCE S256,
  eigene Projekte/Namespace-Podlisten HTTP 200, fremde HTTP 403;
  Ergebnis `tests/results/rancher-access-cluster2.json`.
- `scripts/verify-egress.py`: vier tatsächlich beobachtete LAN-Quell-IPs,
  Ergebnis `tests/results/egress-cluster2.json`.

Die Tests benötigen administrative Lab-Zugänge, erzeugen ausschließlich eigene
kurzlebige Prüfobjekte und entfernen sie anschließend. Für Rancher-OIDC wird zusätzlich
das benachbarte Plattformrepo mit seinen Python-Abhängigkeiten benötigt.
