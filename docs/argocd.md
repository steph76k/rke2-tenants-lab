# GitOps für Mandanten mit Argo CD

Zentrale Plattform: https://argocd.berger.ph, Cluster 2, Keycloak-Realm `berger`.
Installation und technischer OIDC-Client gehören zum Fleet-Plattformrepo.
Terraform verwaltet alle fachlichen Argo-CD-Projekte und Rechte im gemeinsamen State.
Die Live-Abnahme wird im Plattformrepo unter `docs/monitoring-argocd-rollout.md` geführt.

## Rechte

| Gruppe | Im eigenen AppProject |
| --- | --- |
| `<mandant>-developers` | Apps sehen, erstellen, ändern, synchronisieren und Logs lesen |
| `<mandant>-admins` | Zusätzlich Apps löschen |
| `<mandant>-logs-readers` / bisherige Stammgruppe | Keine automatische Argo-CD-Berechtigung |

Benutzer können explizit mehrere Gruppen besitzen. OIDC-Gruppen werden ohne Realm-Pfad
abgeglichen. Keine fremden Projekte, globalen Administrationsrechte, interaktiven
Pod-Shells oder lokalen Manifest-Overrides. AppProject-Konfiguration und globale
RBAC-ConfigMap `argocd-rbac-cm` gehören ausschließlich Terraform. Fleet erzeugt diese
ConfigMap ausdrücklich nicht. Ein neuer Mandant ergänzt sämtliche Zuordnungen beim Apply.

## Repository und Namespace

In `tenants/<mandant>.json` stehen exakte öffentliche HTTPS-URLs:

```json
"argocd_repositories": ["https://github.com/steph76k/rke2-argocd-lab-mandant-a.git"],
"argocd_demo": true
```

`argocd_demo` ist optional und nur für A/B aktiviert. Es erzeugt die anfängliche
Application `<mandant>-demo`: Branch `main`, Pfad `apps/demo`, Ziel `<mandant>-dev`,
Auto-Sync, Prune und Self-Heal. Fachbereiche pflegen die Anwendungsmanifeste in ihren
Repositories. Keine parallele Fleet-Verwaltung derselben Anwendungsobjekte.

Für neue Mandanten:

```bash
python3 scripts/new-tenant.py mandant-c --name 'Mandant C' \
  --argocd-repository https://github.com/example/mandant-c-apps.git
python3 scripts/lab-terraform.py plan -out=tenants.tfplan
python3 scripts/lab-terraform.py apply tenants.tfplan
```

Das Repo ist zunächst nur eine Freigabe; das Werkzeug erstellt dort keine Inhalte.
Ohne Repository-Angabe bleibt das Projekt gesperrt für Anwendungsquellen, bis die Liste
ergänzt wird. Private Repositories benötigen später eigene, projektgebundene ESO-
Zugangsdaten. Keine gemeinsamen Git-Administrationsschlüssel im Cluster hinterlegen.

Argo erlaubt nur Ziele `<mandant>-*` im lokalen Cluster 2. Neue Namespaces zuerst über
das eigene Rancher-Projekt anlegen; die bestehenden Admission-Regeln sichern Namen
und Projektlabel. Danach kann Argo ohne Änderung der Namespace-Liste dorthin deployen.
Überlappende Tenant-Präfixe wie `mandant-a` und `mandant-a-team` sind nicht zulässig.

Die erlaubten Ressourcentypen stehen explizit in `terraform/argocd.tf`: normale
Anwendungsworkloads, Services/Ingress, ConfigMaps/Secrets, PVCs und ExternalSecrets.
Keine Namespace-/Clusteranlage, RBAC-Bindungen, Netzwerk-/Admission-Policies oder
Argo-Kontrollobjekte aus Tenant-Repositories. Erweiterungen benötigen eine gezielte
Änderung dieser administrativen Allowlist.

## Demo sichtbar machen

Die beiden Demo-READMEs enthalten Browser-/Port-Forward-Anleitung und GitOps-Testablauf.
Für Browser-DNS zeigen `mandant-a-demo.berger.ph` und `mandant-b-demo.berger.ph` auf
`192.168.1.195`. Es sind einfache HTTP-Testseiten ohne Zugangsdaten. Die Argo-Anmeldung
selbst verwendet ausschließlich HTTPS.

Die HTTP-Freigabe gehört ebenfalls zur Terraform-Verwaltung: je Demo-Mandant eine
`CiliumClusterwideNetworkPolicy` für Ciliums reservierte Ingress-Identität, ausschließlich
TCP 8080 und die Labels `app.kubernetes.io/name=tenant-demo` sowie
`app.kubernetes.io/part-of=<mandant>-demo`. Das geschützte Rancher-Projektlabel wählt die
zugehörigen Namespaces dynamisch aus. Direkter Verkehr zwischen den Mandanten bleibt gesperrt.
Weitere Anwendungen benötigen eine passende, bewusst konfigurierte Ingress-Freigabe.

## Abnahme am 11.10.2026

Beide Apps Synced/Healthy, jeweils zwei Pods auf unterschiedlichen Workern. Beide DNS-Namen
liefern HTTP 200. OIDC mit A/B-Admins/-Developern und Benutzer ohne Gruppe geprüft; erlaubte
Create/Update/Sync-Operationen sowie negative Fremdzugriffe getestet. Löschen bleibt Admins
vorbehalten. Alle 16 Pod-Verbindungstests und die vier Egress-IP-Prüfungen bestanden.

Neun neue Terraform-Ressourceninstanzen angewendet; abschließender Plan ohne Änderungen.
Ein zusätzlicher Mandant C wurde nur geplant: 36 neue Ressourcen, fünf Aktualisierungen,
keine Löschungen. Dazu gehören AppProject, projektgebundenes Repository, dynamisches Logging,
Admission und zwei Egress-IPs (.204/.205). Die temporäre Deklaration wurde entfernt.
Sanitisierte Belege stehen unter [tests/results/argocd](../tests/results/argocd).

## Betriebsgrenzen

Eine zentrale Lab-Instanz; keine zugesagte Argo-HA. Das AppProject schützt normale
Sync-Operationen, nicht gegen einen kompromittierten privilegierten Controller.
Pod-Security-Härtung bleibt ein separates Plattformthema. Fachbereiche dürfen keine
Plattform-, Monitoring- oder Tenant-Verwaltungsobjekte in ihre App-Repositories aufnehmen.
Ein Tenant-Offboarding muss auch selbst angelegte Namespaces und Apps inventarisieren;
nicht nur die JSON-Datei entfernen oder einen alten Terraform-State zurückspielen.
