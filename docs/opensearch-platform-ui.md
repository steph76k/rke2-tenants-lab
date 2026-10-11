# OpenSearch: Plattformansicht und Keycloak-Logout

`admin` besitzt über `opensearch-platform-admins` die Rollen `all_access` und
`security_rest_api_access`. Eine frische Anmeldung wurde am 11.10.2026 mit dem
tatsächlichen Account geprüft: Logs von Mandant A, Mandant B und beiden
Plattformclustern waren lesbar. Die eingeschränkte Discover-Auswahl war keine
fehlende Indexberechtigung, sondern eine tenantbezogene gespeicherte Indexansicht.

## Plattformansicht öffnen

[Globales Discover](https://opensearch.berger.ph/app/discover?security_tenant=global)
öffnet den Bereich **Global**. Dort stehen zwei durch Terraform verwaltete
Indexansichten bereit:

- `logs-*`: alle zugänglichen Logindizes; Standardansicht mit 24-Stunden-Zeitfenster.
- `*`: alle zugänglichen Indizes ohne vorgeschriebenes Zeitfeld.

Die vollständige Indexübersicht findet sich auch unter Index Management. Geschützte
Security-Systemindizes behalten ihre besonderen Schutzregeln.

Fleet setzt die bevorzugte Tenant-Reihenfolge auf `Global`, danach `Private`.
Eine vorhandene Browserauswahl kann weiterhin Mandant A auswählen; über das
Benutzermenü unter **Switch tenants → Global** oder den Link oben umschalten.
Diese Auswahl betrifft gespeicherte Dashboards und Indexansichten, nicht die
Indexrechte des Benutzers. Die Mandantenrollen erhalten keine zusätzlichen Rechte
auf Global oder fremde Indizes.

## Logout

OpenSearch Dashboards verwendet den von Keycloak veröffentlichten
`end_session_endpoint` automatisch. Die fehlende erlaubte Post-Logout-URI führte
zuvor nach der Weiterleitung zu Keycloak zu HTTP 400 „Invalid redirect URI“;
dadurch blieb die SSO-Sitzung bestehen.

Terraform übernimmt den vorhandenen Client `afi-opensearch` und erlaubt jetzt
genau `https://opensearch.berger.ph` als Rücksprungadresse. Logout beendet damit
die zugehörige Keycloak-Sitzung. Die nächste OIDC-Anmeldung fragt wieder nach
Zugangsdaten. Wie bei Rancher bleiben bereits ausgegebene Tokens anderer
Anwendungen von deren eigener Ablauf- und Logout-Verarbeitung abhängig.

## Verwaltung

`terraform/opensearch-platform-ui.tf` verwaltet den bestehenden Keycloak-Client
und drei Saved Objects im vorhandenen globalen Alias `.kibana`:

- `index-pattern:afi-platform-logs`
- `index-pattern:afi-platform-all`
- `config:3.9.0`

Diese IDs waren vor dem Apply nicht vorhanden. Bestehende Mandantenobjekte wurden
nicht verändert. Der Provider schreibt Saved Objects direkt; ihr Format wurde
gegen Dashboards 3.9.0 verifiziert. Bei einem Dashboards-Upgrade müssen insbesondere
Config-ID, Buildnummer und Migration-Versionen überprüft werden. Die globale
Standardkonfiguration bleibt zentral über Terraform verwaltet.

`terraform_data.platform_index_fields` initialisiert anschließend mit
`scripts/refresh-platform-index-fields.py` den berechneten Feldcache über die
Dashboards-API. Der OpenSearch-Provider nimmt diesen Cache bewusst nicht in den
State auf; ohne ihn kann Discover beim ersten Histogramm das Zeitfeld nicht
auflösen. Das Skript liest das bestehende lokale Dienstpasswort aus OpenBao nur
in den Arbeitsspeicher. Es benötigt wie der Terraform-Wrapper Python, `requests`
und einen gültigen OpenBao-Zugang. Nach Änderungen an den Indexansichten läuft
es automatisch erneut; bei Bedarf lässt es sich separat aufrufen.

Die Fleet-Einstellung liegt im Plattformrepo in
`bundles/infrastructure/applications/opensearch-dashboards/values.yaml`.
Der Chart rollt ConfigMap-Änderungen über seinen Konfigurations-Checksum aus.

Browserprüfung im Plattformrepo:
`scripts/afi-isolation/verify-opensearch-platform-ui.py`.
Sie prüft Plattform- und Mandantenanmeldung, Indexzugriffe, globale Discover-
Darstellung und Logout mit anschließender Passwortabfrage. Temporäre
Keycloak-Prüfbenutzer werden wieder entfernt.
