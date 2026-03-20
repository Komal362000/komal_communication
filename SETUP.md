# Setup

Prerequisites:
- Bazel (Instructions for installing here: https://bazel.build/install)

## Integration Tests

Prerequisites:
- Docker 
  - Instructions for installing here: https://docs.docker.com/engine/install/ 
  - Note. Running Docker in rootless mode is not yet officially supported but may work. See https://docs.docker.com/engine/security/rootless/ for more information.

## Workarounds 

### Linux-Sandbox Ubuntu24.04 Workaround

Ubuntu 24.04 introduced the security framework apparmor. The standard configuration of apparmor which also includes unprivileged user namespaces interferes with the bazel sandboxing mechanism and inhibits the linux-sandbox. This affects all bazel tests and potentially any bazel runnables. 

To work around this issue, you can run the following bash script:

```bash
bash actions/unblock_user_namespace_for_linux_sandbox/action_callable.sh
```

Note. This must be rerun whenever the bazel version is updated.
