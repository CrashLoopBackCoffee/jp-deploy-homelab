import atexit
import enum
import os
import socket
import subprocess
import tempfile
import time

import pulumi as p
import pulumi_kubernetes as k8s


class PortForwardError(RuntimeError):
    pass


class ResourceType(enum.StrEnum):
    DEPLOYMENT = 'deployment'
    POD = 'pod'
    SERVICE = 'service'
    STATEFULSET = 'statefulset'


def ensure_port_forward(
    local_port: p.Input[int],
    namespace: p.Input[str],
    resource_type: ResourceType,
    resource_name: p.Input[str],
    target_port: p.Input[int | str],
    k8s_provider: k8s.Provider,
    skip_on_dry_run: bool = True,
    silent: bool = True,
) -> p.Output[int]:
    """
    Ensure that a port forward is established to the specified resource.

    Args:
        local_port: The local port to forward to the resource.
        namespace: The namespace of the resource.
        resource_type: The type of the resource to forward to.
        resource_name: The name of the resource to forward
        target_port: The target port (or port name) of the resource.
        k8s_provider: The Kubernetes provider to use.
        skip_on_dry_run: Whether to skip the port forward when running in dry-run mode.
        silent: Whether to suppress stdout.

    Returns:
        The local port given in local_port.
    """

    def callback(args) -> int:
        local_port = args['local_port']
        namespace = args['namespace']
        resource_type = args['resource_type']
        resource_name = args['resource_name']
        target_port = args['target_port']
        kubeconfig = args['kubeconfig']
        skip_on_dry_run = args['skip_on_dry_run']
        silent = args['silent']

        if skip_on_dry_run and p.runtime.is_dry_run():
            return local_port

        # Create a temporary kubeconfig file to use for the port forward.
        # Note that we delete the tempfile after the program exits to give
        # kubectl enough time to read the file.
        tmp_kubeconfig_file = tempfile.NamedTemporaryFile(delete=False)
        atexit.register(os.unlink, tmp_kubeconfig_file.name)

        # Write the kubeconfig file, then close so kubectl can read it on all
        # platforms (avoids locked-handle issues on Windows-like environments).
        tmp_kubeconfig_file.write(kubeconfig.encode())
        tmp_kubeconfig_file.flush()
        tmp_kubeconfig_file.close()

        # Perform the port forward. Always capture stderr so we can include it
        # in error messages even when stdout is suppressed.
        extra_args: dict = {'stderr': subprocess.PIPE}
        if silent:
            extra_args['stdout'] = subprocess.DEVNULL
        process = subprocess.Popen(
            [
                'kubectl',
                '--namespace',
                namespace,
                'port-forward',
                f'{resource_type}/{resource_name}',
                f'{local_port}:{target_port}',
            ],
            env={**os.environ, 'KUBECONFIG': tmp_kubeconfig_file.name},
            **extra_args,
        )

        def _terminate_process() -> None:
            """Terminate the kubectl process and drain its pipes."""
            process.terminate()
            try:
                process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait()
            if process.stderr:
                process.stderr.close()
            if process.stdout:
                process.stdout.close()

        # Wait for the port forward to be established.
        start = time.monotonic()
        try:
            while True:
                process.poll()
                if process.returncode is not None:
                    stderr_raw = process.stderr.read() if process.stderr else b''
                    stderr_output = (
                        stderr_raw
                        if isinstance(stderr_raw, str)
                        else stderr_raw.decode(errors='replace')
                    )
                    raise PortForwardError(
                        f'Port forward process exited unexpectedly'
                        f' (rc={process.returncode}): {stderr_output.strip()}'
                    )
                try:
                    with socket.create_connection(('localhost', local_port), timeout=1.0):
                        pass
                    break
                except OSError:
                    if time.monotonic() - start > 30:
                        raise PortForwardError(
                            'Timed out waiting for port forward to be established'
                        )
                    time.sleep(0.1)
        except Exception:
            _terminate_process()
            raise

        # Note: We don't handle termination of the process because the pulumi-language-python
        # process will be terminated before resource deletion is done by pulumi. Therefore we need
        # to just let the process run. Pulumi in the end will terminate all child processes anyway.
        return local_port

    return p.Output.all(
        local_port=local_port,
        namespace=namespace,
        resource_type=resource_type,
        resource_name=resource_name,
        target_port=target_port,
        kubeconfig=k8s_provider.kubeconfig,  # type: ignore
        skip_on_dry_run=skip_on_dry_run,
        silent=silent,
    ).apply(callback)
