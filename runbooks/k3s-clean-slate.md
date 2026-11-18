# Runbook: k3s clean slate

A repeatable teardown and rebuild, so each hardware experiment starts from a known-good
cluster instead of accumulating state. Verified end-to-end on 2026-11-17.

## 0. Pre-flight

Capture a backup and **verify it before touching anything**:

- All resources as YAML, per namespace per api-resource (`kubectl get <r> -o yaml`)
- Node objects and the full label set (labels drive all placement)
- Datastore copy: `sqlite3 state.db ".backup out.db"` for an online copy. If `sqlite3` is
  absent, the fallback is `systemctl stop k3s` + `cp -a`, which is a real outage — install
  sqlite3 first if that matters.
- Server TLS, cred, cluster token, `/etc/rancher/k3s/*`, the systemd unit and its env
- **Each agent's join config**: `/etc/systemd/system/k3s-agent.service` and `/etc/rancher/node`.
  Run this from a workstation, not from the server over SSH — root on the server may have no
  SSH keys to the agents, which silently produces empty archives.
- **Container images.** `k3s-uninstall.sh` wipes containerd's image store. Any image with
  `imagePullPolicy: Never` is gone unless its tarball is saved. Export with
  `k3s ctr images export`.
- Preserve `/usr/local/bin/k3s` and the install script; uninstall deletes both.

Verify with `sha256sum -c` using **relative** paths, `PRAGMA integrity_check` on the datastore
opened read-only (`file:state.db?immutable=1` — opening it read-write checkpoints the WAL and
mutates the backup), `tar tzf` on archives, and `kubectl apply --dry-run=client` on manifests.

## 1. Teardown

Agents first, so they do not thrash against a dying API server:

```
# on each agent
sudo /usr/local/bin/k3s-agent-uninstall.sh
# then on the server
sudo /usr/local/bin/k3s-uninstall.sh
```

A custom `--data-dir` is **not** removed by uninstall. Move it aside rather than deleting it —
it still holds the old containerd image store, which is a recovery path:
`sudo mv /mnt/nvme/k3s /mnt/nvme/k3s.old-<date>`

Confirm bulk data survived before continuing. Uninstall does not touch paths outside the
data-dir, so a shared directory such as `/mnt/nvme/share` should be intact.

## 2. Fresh server

```
sudo env INSTALL_K3S_SKIP_DOWNLOAD=true INSTALL_K3S_VERSION=v1.36.4+k3s1 \
  sh k3s-install.sh server \
  --data-dir /mnt/nvme/k3s \
  --cluster-cidr 10.52.0.0/16 --service-cidr 10.53.0.0/16 --cluster-dns 10.53.0.10 \
  --disable traefik --disable servicelb \
  --node-ip 10.43.0.1 --write-kubeconfig-mode 644 \
  --node-label studio/role=coordinator
```

`--node-ip` pins the API to the backplane rather than the WiFi address. A fresh token and CA
are minted; the old ones remain only as a rollback artifact.

## 3. Rejoin agents

The agent uninstall removes `/usr/local/bin/k3s`, so place the binary first:

```
sudo install -m 0755 k3s /usr/local/bin/k3s
sudo env INSTALL_K3S_SKIP_DOWNLOAD=true INSTALL_K3S_VERSION=v1.36.4+k3s1 \
  K3S_URL=https://10.43.0.1:6443 K3S_TOKEN="<new token>" \
  sh k3s-install.sh agent --node-ip 10.43.0.12 --node-label studio/gpu=nx
```

Verify the `nvidia` RuntimeClass appears and `/var/run/cdi/nvidia.yaml` exists on each GPU
node — without the CDI spec, GPU pods fail at admission.

## 4. Restore workloads

Exported YAML carries live-cluster fields that block `apply`. Strip `resourceVersion`, `uid`,
`creationTimestamp`, `generation`, `selfLink`, the last-applied annotation, and the `status`
block. Re-import images on **every** node that runs them, then apply.

`kube-root-ca.crt` and the `default` ServiceAccount will conflict; that is expected — k3s
manages them and recreates them itself.

## 5. Validate

Three nodes `Ready`, labels present, DaemonSet pods `Running` on all nodes, deployments at
their intended replica counts. Host-level services outside k3s (for example a Tailscale Serve
guard unit) are untouched by the rebuild but worth confirming.

## Timing

Full cycle measured at roughly 12 minutes of wall clock, excluding the backup.
