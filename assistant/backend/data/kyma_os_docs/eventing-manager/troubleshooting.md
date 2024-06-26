# Troubleshooting

This document contains tips and tricks for common problems with Eventing Manager and will be updated continuously.

If you cannot find your issue described here, take a look at the [Eventing Troubleshooting](https://github.com/kyma-project/eventing-manager/blob/main/docs/user/troubleshooting/README.md)

## Troubleshooting: Installing Eventing Manager Using a Docker Image

### Error While Deploying Eventing Manager

**Symptom:** The `make deploy` step fails with the following error message:

`Error from server (NotFound): error when creating "STDIN": namespaces kyma-system not found`

**Cause:** The namespace of the Deployment does not exist yet.

**Remedy:** Create the namespace.

   ```sh
   kubectl create ns kyma-system
   ```

## Reach Out to Us

If you encounter an issue or want to report a bug, please create a [GitHub issue](https://github.com/kyma-project/nats-manager/issues) with background information and
steps on how to reproduce.

If you want to contact the eventing team directly, you can reach us in Slack [Eventing channel](https://kyma-community.slack.com/archives/CD1C9GZMK)
or tag us `@kyma-eventing` in the Slack [Kyma Tech channel](https://sap-ti.slack.com/archives/C0140PCSJ5Q).

# NATS server is unavailable

## Symptom

Eventing CR will be in Warning state and events cannot be published as the Eventing Publisher Proxy (EPP) will not be deployed.

## Cause

Missing NATS module, which is not enabled yet.

## Check

To check whether the NATS module is enabled or not, the following command can be used:
kubectl -n kcp-system kyma -ocustom-columns=modules:.spec.modules

If the output gives not nats module, then it is certainly missing.

## Remedy

The NATS module can be enabled with the following command:
kyma alpha enable module nats -n kyma-system