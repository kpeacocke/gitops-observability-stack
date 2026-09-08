# Home observability stack

Central metrics, logs, dashboards and alert routing for the AmbitiousCake home
infrastructure. Deploy through Portainer from `stack/compose.yml`.

Only Grafana is published. Prometheus, Loki, Alertmanager and collectors remain
on the private Compose network.

## Portainer variables

| Variable | Required | Default |
| --- | --- | --- |
| `OBSERVABILITY_DATA_ROOT` | no | `/volume1/docker/observability` |
| `GRAFANA_VERSION` | no | `latest` |
| `PROMETHEUS_VERSION` | no | `latest` |
| `ALERTMANAGER_VERSION` | no | `latest` |
| `LOKI_VERSION` | no | `latest` |
| `ALLOY_VERSION` | no | `latest` |
| `NODE_EXPORTER_VERSION` | no | `latest` |
| `CADVISOR_VERSION` | no | `latest` |

Grafana's one-time bootstrap password is generated on the NAS at
`/volume1/docker/observability/secrets/grafana_admin_password` and mounted with
Grafana's `__FILE` configuration. Change the interactive admin password in
Grafana after first login; never place it in Portainer stack variables.

Create a Synology reverse-proxy rule from
`https://grafana.ambitiouscake.com` to `http://127.0.0.1:13000`. Enable WebSocket
headers on that rule.

Logs are retained for seven days. Metrics are retained for 30 days and capped
at 5 GB. Those limits are intentional because Alexandria has limited capacity.
