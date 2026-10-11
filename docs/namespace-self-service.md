# Namespace Self-Service auf Cluster 2

Admins und Developers dürfen Namespaces im eigenen Rancher-Projekt erstellen.
Pflicht ist der Mandanten-Präfix: `mandant-a-…` im Projekt A, `mandant-b-…` im Projekt B.
Empfohlenes Schema: `<mandant>-<anwendung>-<umgebung>`, z. B. `mandant-a-shop-dev`.
Die bestehenden `dev/test/prod`-Namespaces bleiben gültig und Terraform-verwaltet.
Zusätzliche Namespaces gehören dem Nutzer/Rancher und benötigen keinen Terraform-Import.

## Einen Namespace erstellen

In Rancher: Cluster 2 → Projects/Namespaces → eigenes Projekt → Create Namespace.
Rancher setzt die Projektannotation; anschließend ergänzt sein Controller das Projektlabel
und die RBAC-/NetworkPolicy-Zuordnung. Erst danach dürfen Pods im Namespace starten.
Bei einer unmittelbaren Pod-Erstellung vor Abschluss erscheint eine verständliche
Admission-Ablehnung; Deployment-/Job-Controller versuchen die Erstellung erneut.

Für kubectl muss die eigene Rancher-Kubeconfig verwendet und das Projekt angegeben werden:

```yaml
apiVersion: v1
kind: Namespace
metadata:
  name: mandant-a-shop-dev
  annotations:
    field.cattle.io/projectId: c-44q9v:p-p2q7n
```

Für B lautet die Projekt-ID `c-44q9v:p-j79sh`. Das Label muss der Benutzer nicht setzen.
Es dürfen keine fremden Projekt-IDs verwendet werden. Ein Namespace wird anhand seiner
geprüften Projektzuordnung berechtigt; sein Name allein verleiht keine Rechte.

## Automatische Anbindungen

| Bereich | Automatische Auswahl |
| --- | --- |
| Rancher | Projekt-RBAC und generierte `np-default`/`hn-nodes` |
| Egress | Cilium-Namespace-Identitätslabel `io.cilium.k8s.namespace.labels.field.cattle.io/projectId` |
| Logging | ClusterFlow `namespace_labels.field.cattle.io/projectId` |
| OpenBao/ESO | ClusterSecretStore `conditions[].namespaceSelector.matchLabels` |
| OpenSearch | Weiterhin feste eigene Indexpräfixe und bestehende Logs-Reader-Gruppe |
| Harbor | Weiterhin eigenes privates Mandantenprojekt und bestehende Gruppen |

A verwendet `.200/.201`, B `.202/.203`, abhängig vom Worker. Ein zusätzlicher Namespace
benötigt keine zusätzliche Egress-IP, keine neue Logging-Queue und keine neue IdP-Gruppe.
Logleserechte erfordern weiterhin die Gruppe `<mandant>-logs-readers`; Namespace-Erstellung
verleiht nicht automatisch Logleserechte oder andere zusätzliche Umsystem-Rechte.
Der ESO-Store heißt `openbao-<mandant>` und erlaubt die vorhandenen Secrets des eigenen
OpenBao-Mandanten. Die dortige Policy bleibt mandantenweit (`secret/data/*`).

## Admission und Vertrauensgrenze

Fleet verwaltet `afi-project-label-integrity`: Ein Projektlabel muss zur Annotation passen;
ein vorhandenes Label darf nicht entfernt werden. Ranchers vorhandener Webhook prüft,
ob der Benutzer die Projektannotation setzen darf. Vor dieser Ergänzung wurde ein
fremdes Label im Dry-Run akzeptiert, eine fremde Annotation jedoch abgewiesen.

Terraform verwaltet `afi-tenant-namespaces` und `afi-tenant-pods` samt Bindings. Ihre
Projekt-/Gruppen-Zuordnung wird aus allen Mandantendeklarationen berechnet. Regeln:

- Passender Mandanten-Präfix für jedes registrierte Projekt, auch bei Admin-API-Aufrufen.
- Reservierte Tenant-Präfixe benötigen eine registrierte Projektzuordnung.
- Tenant-Gruppen dürfen Namespaces nur ihren eigenen registrierten Projekten zuordnen.
- Eine bestehende Mandanten-Projektannotation ist unveränderlich. Projektwechsel sind
  eine gesonderte Migration; vorhandene Secrets und gepufferte Log-Metadaten beachten.
- Pods benötigen eine vollständige gültige Namespace-Zuordnung und dürfen die reservierten
  Cilium-Namespace-Identitätslabels nicht selbst setzen.

Alle Policies verwenden `failurePolicy: Fail` und aktive `Deny`-Bindings. Sie benötigen
keinen eigenen Controller/Webhook-Pod. Die Anwendung darf normale Pod-/Namespace-Labels
setzen; diese entscheiden nicht über Mandantenrechte. Plattformadministratoren mit
Rechten auf Admission-Konfiguration und privilegierte Hostzugänge liegen außerhalb
dieser Grenze. Vollständige Pod-Security-Härtung ist ein separater Plattformbaustein.

Fluent Bit übermittelt Namespace-Labels (`namespace_labels: On`, Namespace-Cache 30 s).
Anwendungs-JSON bleibt Text (`Merge_Log: Off`), Parser-/Exclude-Annotationen bleiben aus.
Jeder Tenant-Output setzt einen festen Indexpräfix; unbekannte Metadaten gelangen nur
zum administrativen Plattform-Output. Namespace-/Projektwechsel werden nicht automatisch
zugelassen, sodass Cache-Inhalte nicht nachträglich zu einem anderen Mandanten gehören.
Ciliums dokumentierte Verzögerung der Policy-Aktivierung bei neuen Pods bleibt bestehen;
die Admission-Prüfung bestätigt Namespace-Zuordnung, nicht eine atomare Cilium-Bereitschaft.

## Ownership und neuer Mandant

Terraform besitzt alle Cluster-2-AFI-ClusterFlows/ClusterOutputs einschließlich der
Plattform-Auffangregel. Neue Mandanten erhalten diese beim normalen zentralen Apply.
Ein Namespace-Katalog ist für das Cluster-2-Routing nicht mehr erforderlich.
Fleet besitzt Collector, Ingest-Zugänge, Monitoring und die allgemeine Label-Schutzregel.
Cluster-1-Plattformlogging bleibt unverändert Fleet-verwaltet.

Zusätzliche Namespaces erfordern keinen Apply. Bei neuen Mandanten weiterhin Plan/Apply
prüfen und Benutzergruppen zuweisen. Dashboards-Index-Patterns werden wie bisher durch
die Plattformadministration angelegt; die Indexrechte selbst verwaltet Terraform.
`render-logging.py` im Plattformrepo rendert nur noch Cluster 1. Alte vorbereitete
Cluster-2-Routen sind historische Vorlagen und dürfen nicht erneut angewendet werden.

Logging-Puffer: 4 GiB pro Ausgang, derzeit 12 GiB auf einem 20-GiB-PVC. Terraform begrenzt
das konfigurierte Gesamtbudget auf 16 GiB. Damit passt noch ein weiterer Mandant; darüber
muss das Storage-/Pufferbudget bewusst angepasst werden. Mehr Namespaces eines bestehenden
Mandanten erhöhen dessen Budget nicht. Neue Mandanten müssen unabhängig davon in den
verfügbaren Egress-IP-Pool passen.

## Logging-Übernahme und Rücknahme

Vor der Übernahme wurden Shared State, Backend-Zugänge und Kubernetes-Konfigurationen
SOPS-verschlüsselt unter `/home/tanzu/manifest/backups/afi-selfservice-2026-10-11/` gesichert.
Der frühere Fleet-Bundle erhielt `keepResources: true` und die sechs Ressourcen zusätzlich
`helm.sh/resource-policy: keep`. Erst nach Live-Prüfung wurden die Ressourcen importiert
und der Bundle entfernt. Alle sechs UIDs, Output-Namen und Pufferpfade blieben erhalten.
Mit `logging_takeover=true` wurde einmalig die Feldzuständigkeit des entfernten
Fleet-Controllers übernommen, einschließlich explizitem Leeren der alten Namespace-Listen.
Normale Läufe verwenden `logging_takeover=false`; erzwungene Feldübernahme ist kein Dauerbetrieb.

Ein Rückbau muss zusätzliche Self-Service-Namespaces berücksichtigen: nicht blind auf
alte feste Listen zurückschalten. Zuerst aktuelle Namespaces inventarisieren und gültige
statische Zuordnungen vorbereiten. Danach dynamische Selector kontrolliert ersetzen,
Queues abarbeiten lassen und Ownership gezielt zurückgeben. Label-Schutz erst entfernen,
wenn kein sicherheitsrelevanter Selector mehr davon abhängt. Kein altes State-Backup blind
über den aktuellen Shared State schreiben.

## Verifikation

```bash
python3 scripts/verify-namespace-selfservice.py \
  --kubeconfig=/pfad/zur/cluster2-admin-kubeconfig \
  --listen=192.168.1.60 \
  --output-dir=/tmp/namespace-selfservice-results
```

Benötigt Python-Abhängigkeiten des benachbarten Plattformrepos, kubectl, OpenBao CLI,
administrativen Lab-Zugang und den dokumentierten OpenSearch-Tunnel.
Der Test erstellt vier zufällige Namespaces unter exakten Admin-/Developer-Gruppen
mittels Kubernetes-Impersonation, testet verbotene Änderungen, eigene/fremde ESO-Stores,
Egress und Netzwerkisolation. Zusätzlich erfolgen echte Rancher-OIDC-Anmeldungen und
OpenSearch-OIDC-Leseprüfungen für Logs aus neuen Namespaces. Synthetische Keys, Benutzer,
Pods/Namespaces und eigene Log-Testdokumente werden anschließend entfernt.
