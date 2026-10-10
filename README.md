# RKE2 Lab – Mandanten mit Terraform

Ein Mandant wird durch `tenants/<name>.json` beschrieben. Terraform verwaltet seine
Keycloak-Gruppe im Realm `berger`, sein Rancher-Projekt mit Gruppenberechtigung,
Kubernetes-Namespaces, optional ein privates Harbor-Projekt sowie den isolierten
OpenBao-Namespace mit KV-v2, Kubernetes-Authentifizierung und ESO-Anbindung.
Die zentrale Plattform bleibt im separaten Repository `rke2-platform-lab`.

Lokaler Pfad: `/home/tanzu/manifest/fleet/rke2-tenants-lab`.
Git-Remote: `git@github.com:steph76k/rke2-tenants-lab.git`.

## Stand 10.10.2026

Mandant A wurde übernommen, nicht neu erstellt. Bestehendes Rancher-Projekt
`c-m-prkskj2p:p-9nh78`, Keycloak-Gruppe, drei Namespaces und OpenBao-/ESO-Ressourcen
sind importiert. Ergänzt wurden die Rolle `project-member` für
`keycloakoidc_group://mandant-a` und das private Harbor-Projekt `mandant-a`.
Der abschließende Terraform-Plan meldet **No changes**.
Ein zusätzlicher Mandant wurde nur geplant: 16 neue Ressourcen, keine Änderungen
an Mandant A, kein Apply. Details: [Validierung](docs/validation.md).

## Neuen Mandanten hinzufügen

```bash
python3 scripts/new-tenant.py mandant-b --name 'Mandant B'
terraform -chdir=terraform init -lockfile=readonly
terraform -chdir=terraform fmt -check -recursive
terraform -chdir=terraform validate
umask 077
terraform -chdir=terraform plan -out=tenant.tfplan
terraform -chdir=terraform apply tenant.tfplan
```

Vor `plan`/`apply` die [Zugänge und Voraussetzungen](docs/operations.md) einrichten.
Der Generator erzeugt ausschließlich eine lokale Datei. Benutzer werden anschließend
in Keycloak der Gruppe des Mandanten zugewiesen; Passwörter und Benutzerkonten sind
bewusst kein Bestandteil des Terraform-States.

`project-member` ist die Vorgabe; `read-only` und `project-owner` sind auswählbar.
Harbor-Projekte sind privat und haben standardmäßig 10 GiB Quota und automatische
Scans. Harbor-Benutzerrechte/OIDC, MinIO-Buckets, Netzwerkpolicies, Ressourcenquoten,
OpenSearch-Leserollen und interaktive OpenBao-OIDC-Zugänge werden hier nicht automatisch
vergeben. Die bestehende OpenBao-OIDC-Konfiguration von Mandant A bleibt erhalten.
Das ist eine Lab-Grundstruktur, keine vollständige Sicherheitsisolation der Anwendungen.

## State und Lebenszyklus

Aktuell lokaler State `terraform/terraform.tfstate`, Dateirechte 0600, ein einzelner
Schreiber. State, Backups, Pläne und Zugangsdaten sind aus Git ausgeschlossen.
Die Provider-Versionen und Prüfsummen stehen in `terraform/.terraform.lock.hcl`.
Vor Arbeiten den State geschützt sichern. Keine parallelen Applies aus anderen Kopien.
Ein gemeinsames Backend mit Sperrung und separatem S3-Zugang ist noch nicht eingerichtet;
der neue MinIO-Lab-Dienst wird nicht automatisch als Terraform-Backend verwendet.

Bestehende Ressourcen vor dem ersten Apply importieren. Niemals eine Mandantendatei
zur Löschung entfernen: Das Modul setzt `prevent_destroy` für Gruppe, Projekt,
Namespaces und OpenBao-Datenspeicher. Entfernen der gesamten Modulkonfiguration kann
diesen Schutz entfernen; deshalb jeden Plan auf Löschungen prüfen. Offboarding erfordert
einen eigenen, datenbewussten Ablauf.

Das bestehende Git-Repository enthält auch die bisherigen lokalen Commits.
Der lokale Terraform-State wurde beim Umzug mitgenommen und bleibt von Git ausgeschlossen.
Das Git-Remote ist kein Terraform-State-Backend.
