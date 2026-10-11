# Plattformadministration über Keycloak

Die folgenden flachen Gruppen im Realm `berger` sind unabhängig von den
Mandantengruppen. `terraform/platform-admins.tf` verwaltet sie und die
Dienstzuordnungen im gemeinsamen verschlüsselten State.

| Gruppe | Berechtigung |
| --- | --- |
| `rancher-platform-admins` | Rancher Global Role `admin`, einschließlich aller verwalteten Cluster |
| `harbor-platform-admins` | OIDC-Systemadministration in Harbor |
| `opensearch-platform-admins` | `all_access` und `security_rest_api_access` |
| `argocd-platform-admins` | Argo CD `role:admin` |
| `openbao-platform-admins` | Bestehende OIDC-Rolle und ACL `platform-admin` im Root-Namespace |

OpenBao verwendet im Token den vollständigen Gruppenpfad
`/openbao-platform-admins`; die anderen Dienste verwenden Gruppennamen ohne `/`.
Die OpenBao-ACL enthält `sudo`, erzeugt aber kein Root-Token. OpenSearch-Zugriffe,
die ausdrücklich ein Admin-Zertifikat erfordern, bleiben zertifikatsgebunden.
Die bisherigen lokalen Notfallzugänge bleiben erhalten. Das lokale OpenSearch-
Backend-Rollenmapping `admin` wird ausdrücklich beibehalten.

## Benutzer und Mitgliedschaften

Auf ausdrücklichen Wunsch ist `berger/admin` Mitglied aller fünf Gruppen.
Terraform verwaltet diese Mitgliedschaften additiv mit `exhaustive = false`;
andere Mitgliedschaften werden nicht entfernt. Weitere Betreiber können in
Keycloak gezielt nur den benötigten Dienstgruppen zugeordnet werden.
Mandanten-Admins werden nicht automatisch zu Plattform-Admins.

Das Profil von `berger/admin` wurde auf die angegebenen Werte `admin admin` und
`admin@berger.ph` ergänzt. Seine Anmeldung bleibt `admin`. In Harbor wird dieser
OIDC-Benutzer einmalig als **`berger-admin`** geführt, weil `admin` dort bereits
der lokale Notfallbenutzer ist. Die Zuordnung erfolgt über den unveränderten
OIDC-Subject. Für dieses Onboarding wurde die automatische Registrierung kurz
ausgeschaltet und anschließend wieder eingeschaltet. Das Passwort wurde nicht
geändert. Die administrative Keycloak-Impersonation-Sitzung wurde danach beendet.

`bergers` wurde nicht verändert. Bei der Abnahme war er weiterhin Mitglied der
bereits vorhandenen Gruppe `openbao-platform-admins`; für einen ausschließlich
mandantenberechtigten Testaccount muss diese Mitgliedschaft in Keycloak entfernt
werden. Neue Plattformgruppen wurden diesem Account nicht zugewiesen.

`master/admin` ist ein separater, derzeit noch temporärer Keycloak-Bootstrap-
Administrator. Die fünf Dienstgruppen ersetzen dessen Keycloak-Verwaltungsrechte
nicht. Vor einer späteren Entfernung müssen ein dauerhafter Verwaltungszugang
und die Umstellung der Lab-Automation eingerichtet und geprüft sein.

## Terraform und Zugangsdaten

Die bestehende OpenBao-Gruppe, OpenBao-Rolle und ACL sowie das OpenSearch-Mapping
`all_access` und Harbors Authentifizierung wurden ohne Neuerstellung übernommen.
Der erste Apply erzeugte sieben Ressourcen, änderte drei und löschte keine.

Harbors OIDC-Clientsecret wird vom Lab-Runner aus
`secret/platform/oidc/afi-harbor` ausschließlich in den Prozessspeicher geladen.
`harbor_oidc_client_secret` ist `sensitive` und `ephemeral`; die Ressource verwendet
`oidc_client_secret_wo`. Terraform >= 1.11 ist deshalb erforderlich. Bei bewusster
Secretrotation ist auch `oidc_client_secret_wo_version` zu erhöhen. Ohne Lab-Runner
muss `TF_VAR_harbor_oidc_client_secret` sicher bereitgestellt werden.

Der ursprüngliche OIDC-Bootstrap im Plattformrepo setzt `oidc_admin_group` nicht
mehr zurück. Fleet installiert Argo CD weiterhin ohne eigene RBAC-ConfigMap;
Terraform verwaltet die Mandantenregeln und die zusätzliche Plattformgruppe.

## Abnahme

Frische OIDC-Anmeldungen mit temporären Benutzern prüfen Plattformzugriff und
Ablehnung für einen Benutzer, der nur `mandant-a-admins` besitzt:

| Prüfung | Plattformgruppe | Nur Mandanten-Admin |
| --- | --- | --- |
| Rancher: ClusterRoleBindings erstellen, SelfSubjectAccessReview | erlaubt | abgelehnt |
| Harbor: Konfiguration lesen | HTTP 200 | HTTP 403 |
| OpenSearch: Security-Rollenmappings lesen | HTTP 200 | HTTP 403 |
| Argo CD: bestehendes AppProject unverändert aktualisieren | HTTP 200 | HTTP 403 |
| OpenBao: OIDC-Plattformrolle anmelden | HTTP 200 | HTTP 400, Gruppenbedingung nicht erfüllt |

Die Testkonten und ausgegebenen OpenBao-Token wurden danach entfernt bzw.
widerrufen. Prüfskript im Plattformrepo:
`scripts/afi-isolation/verify-platform-admins.py`; Ergebnisdatei in diesem Repo:
`tests/results/platform-admins/authorization-20261011.json`.

Monitoring bleibt entsprechend der eigenen Freigabe zentral und für
Mandantengruppen lesbar. Es wurde kein Federator eingerichtet. MinIO und der
Terraform-State bleiben technische Verwaltungsdienste mit separaten Credentials.
