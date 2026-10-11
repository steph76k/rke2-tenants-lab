# Rancher und Keycloak gemeinsam abmelden

Rancher 2.14.3 ist für OIDC Single Logout im Realm `berger` konfiguriert.
`terraform/rancher-oidc-logout.tf` verwaltet den bestehenden Keycloak-Client
`rancher` und Ranchers bestehenden OIDC-Authentifizierungsanbieter.

| Einstellung | Wert |
| --- | --- |
| `logoutAllEnabled` | `true` |
| `logoutAllForced` | `true` |
| `endSessionEndpoint` | `https://idp.berger.ph/realms/berger/protocol/openid-connect/logout` |

Beim Abmelden sendet Rancher den Browser an Keycloak und beendet dort die
zugehörige SSO-Sitzung. Der erneute OIDC-Login verlangt wieder Zugangsdaten.
Die zuvor angezeigte Meldung, dass die SSO-Sitzung möglicherweise noch aktiv sei,
gehörte zur früheren Einstellung „nur Rancher abmelden“.

Der Keycloak-Client erlaubt folgende Rücksprünge, ohne Host-Wildcards:

- `https://rancher.berger.ph`
- `https://rancher.berger.ph/dashboard/auth/verify?is-slo&logged-out`

Die zweite URL einschließlich Query entspricht der eingesetzten Dashboard-Version.
Bei einem Rancher-Upgrade ist der Logout-Browsertest erneut auszuführen.

## Verwaltung und Rückfall

Der native Rancher-Terraform-Provider besitzt für diese Ressource keinen Importer.
Sein erster Apply übernimmt den vorhandenen Singleton mit einem API-Update.
Er deaktiviert den Anbieter dabei nicht. `prevent_destroy` verhindert ein
versehentliches Abschalten durch Terraform. Authentifizierungsanbieter nie zum
Ändern der Logout-Einstellung löschen und neu anlegen.

Ein Vergleich mit der verschlüsselten Sicherung bestätigt, dass auf dem
Rancher-AuthConfig nur die drei oben genannten Felder verändert wurden.
PKCE `S256`, Clientsecret, Claims, Zugangseinstellung und Principal-IDs blieben
erhalten. Der Keycloak-Client behält seine bisherigen Login-Redirects, Mapper
und Scopes; Refresh-Tokens werden explizit aktiviert, entsprechend Keycloaks
vorherigem Standard bei fehlendem Attribut.

Für einen Rückfall `logout_all_forced` und `logout_all_enabled` auf `false`
setzen, Plan prüfen und anwenden. Lokale Notfallzugänge bleiben verfügbar.
Der OIDC-Clientsecret liegt nur im verschlüsselten administrativen State und
in den bestehenden Secret-Speichern. Er gehört weder in Git noch in Plan-Logs.

Single Logout beendet die Keycloak-SSO-Sitzung. Bereits ausgegebene Tokens und
eigene Sitzungen anderer Anwendungen können abhängig von deren Logout- und
Tokenprüfung noch bis zu ihrem Ablauf gelten. Eine sofortige Abmeldung jeder
offenen Anwendung wird dadurch nicht pauschal zugesichert.

## Browserprüfung

Das Plattformrepo enthält `scripts/afi-isolation/verify-rancher-logout.py`.
Es meldet einen temporären Mandantenbenutzer über OIDC an, ruft Ranchers echten
UI-Logout auf und prüft:

- Rancher-Logout und Weiterleitung an Keycloak erfolgreich;
- keine verbleibende Keycloak-Sitzung für diesen Testbenutzer;
- erneuter Login im selben Browser zeigt die Anmeldemaske;
- der alte Rancher-Token wird mit HTTP 401 abgelehnt.

Ergebnis: `tests/results/platform-admins/logout-20261011.json`.
Testidentitäten werden anschließend entfernt. TLS wird über die Lab-CA geprüft.

Offizielle Grundlage:
[Rancher 2.14: OIDC Single Logout](https://ranchermanager.docs.rancher.com/v2.14/how-to-guides/new-user-guides/authentication-permissions-and-global-configuration/authentication-config/configure-keycloak-oidc#_configuring_oidc_single_logout_slo).
