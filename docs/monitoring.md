# Gemeinsamer Monitoring-Viewer im Lab

Auf ausdrücklichen Betreiberwunsch erhalten alle bestehenden Mandantengruppen
lesenden Zugriff auf das zentrale Rancher Monitoring auf Cluster 2:
`<mandant>`, `<mandant>-admins`, `<mandant>-developers`, `<mandant>-logs-readers`.
Die Daten sind dabei clusterweit sichtbar, einschließlich anderer Mandanten und
der Infrastruktur. Das ist eine bewusste Lab-Freigabe, keine mandantengetrennte Ansicht.
Prometheus Federator wird vorerst nicht installiert.

`terraform/monitoring.tf` verwaltet eine Role im Namespace `cattle-monitoring-system`
und eine RoleBinding pro Mandant. Neue Tenant-Deklarationen ergänzen beim Apply
automatisch ihre Gruppen. Keine Bindung an einzelne Benutzer oder alle authentifizierten Nutzer.

Die Rolle erlaubt das Lesen der Monitoring-Objekte und Endpoints, damit Rancher
das Monitoring-Menü und die Links anzeigt. Über den Service-Proxy sind Prometheus,
Alertmanager und Grafana erreichbar. Nur Grafana darf POST-Anfragen für lesende
Datasource-Abfragen empfangen; die bestehende Grafana-Viewer-Rolle begrenzt dort
die Bedienung. Kein Schreibzugriff auf Monitoring-CRDs, Secrets, ConfigMaps oder
Workloads; keine POST-Freigabe zum Erstellen von Alertmanager-Silences.

Zugang: Rancher → rke2-cluster2 → Monitoring. Nach erstmaliger Änderung die Rancher-
Seite vollständig neu laden, damit die API-Schemas und das Menü neu geladen werden.

Die UI-Anforderungen sind gegen Rancher Dashboard v2.14.3 geprüft:
[Monitoring-Erkennung und Linkfreigabe](https://github.com/rancher/dashboard/blob/v2.14.3/shell/utils/monitoring.js).

## Live-Abnahme am 11.10.2026

Drei zusätzliche RBAC-Ressourcen angewendet, keine Änderungen oder Löschungen an
bestehenden Ressourcen. Abschließender Terraform-Plan ohne Änderungen.
Alle acht Gruppen von A/B mit positiven Lese-/Abfrageprüfungen und negativen
Secret-/Konfigurations-/Workload-Schreibprüfungen getestet. Eine fremde Gruppe bleibt gesperrt.

Frische OIDC-Anmeldungen für A-Admin und B-Developer bestätigten im echten Browser
Monitoring-Menü und Grafana-Link. Grafana gesund (200), zentrale Prometheus-Abfrage
zeigt erwartungsgemäß beide Mandanten; Grafana-Ordneranlage und fremde Workload-Abfragen
jeweils 403. Grafana verwendet `Viewer`, kein bekanntes Standard-Adminpasswort.
Alle temporären Testidentitäten entfernt. `bergers` besitzt die erforderlichen Rechte
über `mandant-a-admins`. [Prüfergebnisse](../tests/results/monitoring/viewer-20261011.json).
